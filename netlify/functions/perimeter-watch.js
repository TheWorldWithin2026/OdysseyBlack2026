// netlify/functions/perimeter-watch.js
//
// Headline monitor for companies relocating to / expanding in the Perimeter
// Center submarket (Dunwoody, Sandy Springs, Brookhaven). Pulls public Google
// News RSS results for FIXED server-side queries (no client input reaches the
// query string), filters by keyword, de-duplicates and returns a normalised
// list.
//
// DEPLOY: commit with index.html, set ALLOWED_ORIGINS in Netlify env vars
// (comma-separated, same value style as places.js). With no value set every
// request is rejected (server_not_configured) — fail closed.
//
// HONEST LIMITS
//  - Output is UNVERIFIED headlines, not a company directory. Coverage depends
//    on what news outlets publish; it cannot guarantee it sees every move.
//  - The Origin check only stops other websites' pages from using a visitor's
//    browser against this endpoint; it is not protection against direct curl.
//  - Rate limit is instance-local and best effort.
//  - Google News RSS is an unofficial, unauthenticated feed; it may change or
//    throttle. Failures surface as structured errors, never silent empties.

const QUERIES = [
  '"Perimeter Center" headquarters relocate',
  '"Sandy Springs" headquarters relocating',
  'Dunwoody headquarters relocation lease',
  'Brookhaven Georgia headquarters relocating',
  '"Central Perimeter" office lease new headquarters',
  '"Perimeter Summit" OR "North Terraces" OR "Concourse" office lease'
];

const AREA_TERMS = ['perimeter', 'dunwoody', 'sandy springs', 'brookhaven', 'north terraces', 'perimeter summit', 'ravinia', 'concourse'];
const MOVE_TERMS = ['headquarters', 'hq', 'relocat', 'moving', 'moves', 'lease', 'expand', 'new office', 'opens office', 'consolidat', 'sq. ft', 'square feet', 'square-foot'];

// Browsers omit the Origin header on same-site GET requests, so "no Origin" must not mean "reject".
// Allowed when: Origin is on the list; OR no Origin and the browser says Sec-Fetch-Site: same-origin;
// OR no Origin / no Sec-Fetch-Site and the Referer's origin is on the list. Everything else is refused.
function requestAllowed(headers, origin, allowed) {
  if (origin) return allowed.indexOf(origin) !== -1;
  const h = headers || {};
  const site = String(h['sec-fetch-site'] || h['Sec-Fetch-Site'] || '').toLowerCase();
  if (site) return site === 'same-origin';
  const ref = h.referer || h.Referer || '';
  try { return allowed.indexOf(new URL(ref).origin) !== -1; } catch (e) { return false; }
}

const RATE_LIMIT_WINDOW_MS = 60000;
const RATE_LIMIT_MAX = 10;
const rateMap = new Map();
function checkRateLimit(key) {
  const now = Date.now();
  const r = rateMap.get(key) || { count: 0, start: now };
  if (now - r.start > RATE_LIMIT_WINDOW_MS) { r.count = 0; r.start = now; }
  r.count += 1;
  rateMap.set(key, r);
  if (rateMap.size > 5000) rateMap.clear();
  return r.count <= RATE_LIMIT_MAX;
}

function decodeEntities(s) {
  return String(s || '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, '&');
}
function stripTags(s) { return decodeEntities(s).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim(); }
function tag(block, name) {
  const m = new RegExp('<' + name + '[^>]*>([\\s\\S]*?)</' + name + '>', 'i').exec(block);
  return m ? m[1] : '';
}

// Parse RSS <item> blocks. Pure function (unit-tested).
function parseRSS(xml) {
  const items = [];
  const re = /<item>([\s\S]*?)<\/item>/gi;
  let m;
  while ((m = re.exec(String(xml || ''))) !== null) {
    const block = m[1];
    const title = stripTags(tag(block, 'title'));
    const link = stripTags(tag(block, 'link'));
    const pub = stripTags(tag(block, 'pubDate'));
    const source = stripTags(tag(block, 'source'));
    const desc = stripTags(tag(block, 'description'));
    items.push({ title, link, pub, source, desc });
  }
  return items;
}

function safeUrl(u) {
  try { const p = new URL(u); return (p.protocol === 'https:' || p.protocol === 'http:') ? p.toString() : ''; }
  catch (e) { return ''; }
}

// Keyword filter + normalise. An item must mention an area term AND a move term.
function normaliseItems(raw) {
  const out = [];
  const seen = new Set();
  raw.forEach(function (it) {
    const hay = (it.title + ' ' + it.desc).toLowerCase();
    const area = AREA_TERMS.filter(function (t) { return hay.indexOf(t) !== -1; });
    const move = MOVE_TERMS.filter(function (t) { return hay.indexOf(t) !== -1; });
    if (!area.length || !move.length) return;
    const url = safeUrl(it.link);
    if (!url || !it.title) return;
    const id = it.title.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 120);
    if (seen.has(id)) return;
    seen.add(id);
    const d = new Date(it.pub);
    out.push({
      id: id,
      title: it.title.slice(0, 300),
      source: (it.source || '').slice(0, 100),
      url: url,
      publishedAt: isNaN(d.getTime()) ? null : d.toISOString(),
      matchedKeywords: area.concat(move),
      status: 'unverified_lead'
    });
  });
  out.sort(function (a, b) { return String(b.publishedAt || '').localeCompare(String(a.publishedAt || '')); });
  return out;
}

async function fetchQuery(q) {
  const url = 'https://news.google.com/rss/search?q=' + encodeURIComponent(q + ' when:90d') + '&hl=en-US&gl=US&ceid=US:en';
  const ctrl = new AbortController();
  const t = setTimeout(function () { ctrl.abort(); }, 8000);
  try {
    const res = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': 'OdysseyBlack-PerimeterWatch/1.0' } });
    if (!res.ok) throw new Error('upstream_' + res.status);
    return parseRSS(await res.text());
  } finally { clearTimeout(t); }
}

exports.handler = async function (event) {
  const requestId = Math.random().toString(36).slice(2, 10);
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
  const reply = function (code, body, origin) {
    const h = Object.assign({}, headers);
    if (origin) { h['Access-Control-Allow-Origin'] = origin; h['Vary'] = 'Origin'; h['Access-Control-Allow-Methods'] = 'GET, OPTIONS'; h['Access-Control-Allow-Headers'] = 'Content-Type'; }
    return { statusCode: code, headers: h, body: JSON.stringify(Object.assign({ requestId: requestId }, body)) };
  };

  const allowed = (process.env.ALLOWED_ORIGINS || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  if (allowed.length === 0) return reply(500, { error: 'server_not_configured' });

  const h = event.headers || {};
  const origin = h.origin || h.Origin || '';
  if (!requestAllowed(h, origin, allowed)) return reply(403, { error: 'origin_not_allowed' });

  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: Object.assign({}, headers, { 'Access-Control-Allow-Origin': origin, 'Vary': 'Origin', 'Access-Control-Allow-Methods': 'GET, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }), body: '' };
  if (event.httpMethod !== 'GET') return reply(405, { error: 'method_not_allowed' }, origin);

  const ip = h['x-nf-client-connection-ip'] || h['x-forwarded-for'] || 'unknown';
  if (!checkRateLimit(String(ip).split(',')[0].trim())) return reply(429, { error: 'rate_limited' }, origin);

  const results = await Promise.allSettled(QUERIES.map(fetchQuery));
  const ok = results.filter(function (r) { return r.status === 'fulfilled'; });
  if (ok.length === 0) {
    console.error('[perimeter-watch][' + requestId + '] all upstream queries failed');
    return reply(502, { error: 'upstream_unavailable' }, origin);
  }
  const raw = [].concat.apply([], ok.map(function (r) { return r.value; }));
  const items = normaliseItems(raw).slice(0, 60);
  return reply(200, {
    items: items,
    queriesRun: QUERIES.length,
    queriesFailed: QUERIES.length - ok.length,
    fetchedAt: new Date().toISOString(),
    notice: 'Headlines only. Every item is an unverified lead - confirm the company and the move before any outreach.'
  }, origin);
};

exports._test = { requestAllowed, parseRSS, normaliseItems, safeUrl, checkRateLimit, QUERIES };
