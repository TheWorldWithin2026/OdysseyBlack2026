// netlify/functions/claude.js
//
// Server-side proxy to the Anthropic Messages API so the API key never reaches
// the browser.
//
// DEPLOY: needs ANTHROPIC_API_KEY and ALLOWED_ORIGINS (comma-separated exact
// origins, e.g. https://odysseyblack2026.netlify.app) in Netlify env vars.
// With no ALLOWED_ORIGINS every request is rejected (fail closed).
//
// WHAT THIS PROTECTS
//  - Other websites cannot use a visitor's browser to spend your API credit:
//    a request must come from an allowed origin.
//  - Only a fixed set of fields is forwarded, with size and token caps, so a
//    caller cannot enable tools, huge outputs or other models' settings.
//  - Errors never include stack traces.
// HONEST LIMITS
//  - The Origin check is not protection against someone calling the endpoint
//    directly with curl and a forged Origin header. For that you would need
//    real sign-in on the endpoint. The caps and the rate limit bound the cost.
//  - The rate limit is instance-local and best effort.

const MAX_BODY_BYTES = 200000;
const MAX_TOKENS_CAP = 4000;
const MAX_MESSAGES = 20;
const MAX_TEXT_CHARS = 60000;
const RATE_LIMIT_WINDOW_MS = 60000;
const RATE_LIMIT_MAX = 20;
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

// Allowed when: Origin is on the list; OR no Origin and Sec-Fetch-Site is same-origin;
// OR no Origin / no Sec-Fetch-Site and the Referer's origin is on the list.
function requestAllowed(headers, origin, allowed) {
  if (origin) return allowed.indexOf(origin) !== -1;
  const h = headers || {};
  const site = String(h['sec-fetch-site'] || h['Sec-Fetch-Site'] || '').toLowerCase();
  if (site) return site === 'same-origin';
  const ref = h.referer || h.Referer || '';
  try { return allowed.indexOf(new URL(ref).origin) !== -1; } catch (e) { return false; }
}

// Returns { ok:true, body } with only whitelisted, capped fields, or { ok:false, error }.
function buildUpstreamBody(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { ok: false, error: 'invalid_body' };
  if (typeof raw.model !== 'string' || !/^claude-[a-z0-9.\-]{1,60}$/.test(raw.model)) return { ok: false, error: 'invalid_model' };
  if (!Array.isArray(raw.messages) || raw.messages.length < 1 || raw.messages.length > MAX_MESSAGES) return { ok: false, error: 'invalid_messages' };
  let chars = 0;
  const messages = [];
  for (const m of raw.messages) {
    if (!m || typeof m !== 'object' || (m.role !== 'user' && m.role !== 'assistant') || typeof m.content !== 'string') return { ok: false, error: 'invalid_messages' };
    chars += m.content.length;
    messages.push({ role: m.role, content: m.content });
  }
  if (typeof raw.system === 'string') chars += raw.system.length;
  if (chars > MAX_TEXT_CHARS) return { ok: false, error: 'too_large' };
  const body = { model: raw.model, messages: messages };
  const mt = Number(raw.max_tokens);
  body.max_tokens = Number.isFinite(mt) && mt > 0 ? Math.min(Math.floor(mt), MAX_TOKENS_CAP) : 1000;
  if (typeof raw.system === 'string' && raw.system) body.system = raw.system;
  if (typeof raw.temperature === 'number' && raw.temperature >= 0 && raw.temperature <= 1) body.temperature = raw.temperature;
  return { ok: true, body: body };
}

exports.handler = async function (event) {
  const requestId = Math.random().toString(36).slice(2, 10);
  const baseHeaders = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Request-Id': requestId };
  const reply = function (code, obj, origin) {
    const h = Object.assign({}, baseHeaders);
    if (origin) { h['Access-Control-Allow-Origin'] = origin; h['Vary'] = 'Origin'; h['Access-Control-Allow-Methods'] = 'POST, OPTIONS'; h['Access-Control-Allow-Headers'] = 'Content-Type'; }
    return { statusCode: code, headers: h, body: JSON.stringify(Object.assign({ requestId: requestId }, obj)) };
  };

  const allowed = (process.env.ALLOWED_ORIGINS || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  if (allowed.length === 0) return reply(500, { error: 'server_not_configured' });

  const h = event.headers || {};
  const origin = h.origin || h.Origin || '';
  if (!requestAllowed(h, origin, allowed)) return reply(403, { error: 'origin_not_allowed' });
  const corsOrigin = origin || '';

  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: Object.assign({}, baseHeaders, corsOrigin ? { 'Access-Control-Allow-Origin': corsOrigin, 'Vary': 'Origin', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' } : {}), body: '' };
  if (event.httpMethod !== 'POST') return reply(405, { error: 'method_not_allowed' }, corsOrigin);

  if (!process.env.ANTHROPIC_API_KEY) return reply(500, { error: 'ANTHROPIC_API_KEY is not set in Netlify' }, corsOrigin);

  const ip = String(h['x-nf-client-connection-ip'] || h['x-forwarded-for'] || 'unknown').split(',')[0].trim();
  if (!checkRateLimit(ip)) return reply(429, { error: 'rate_limited' }, corsOrigin);

  const rawBody = event.isBase64Encoded ? Buffer.from(event.body || '', 'base64').toString('utf8') : String(event.body || '');
  if (rawBody.length > MAX_BODY_BYTES) return reply(413, { error: 'too_large' }, corsOrigin);
  let parsed;
  try { parsed = JSON.parse(rawBody); } catch (e) { return reply(400, { error: 'invalid_json' }, corsOrigin); }
  const built = buildUpstreamBody(parsed);
  if (!built.ok) return reply(400, { error: built.error }, corsOrigin);

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify(built.body)
    });
    const data = await response.json();
    return { statusCode: response.ok ? 200 : response.status, headers: Object.assign({}, baseHeaders, corsOrigin ? { 'Access-Control-Allow-Origin': corsOrigin, 'Vary': 'Origin' } : {}), body: JSON.stringify(data) };
  } catch (err) {
    console.error('[claude][' + requestId + '] upstream failure:', err && err.message);
    return reply(502, { error: 'upstream_unavailable' }, corsOrigin);
  }
};

exports._test = { requestAllowed, buildUpstreamBody, checkRateLimit };
