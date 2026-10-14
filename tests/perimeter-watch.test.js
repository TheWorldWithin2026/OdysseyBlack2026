// node tests/perimeter-watch.test.js  (isolated logic tests; no network)
const path = require('path');
const mod = require(path.join(__dirname, '..', 'netlify', 'functions', 'perimeter-watch.js'));
const { parseRSS, normaliseItems, safeUrl } = mod._test;
let fails = 0;
function t(name, cond) { console.log((cond ? 'PASS: ' : 'FAIL: ') + name); if (!cond) fails++; }

const xml = `<rss><channel>
<item><title><![CDATA[Acme to relocate headquarters to Sandy Springs]]></title><link>https://example.com/a</link><pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate><source url="x">Atlanta Biz</source><description>&lt;p&gt;350 jobs&lt;/p&gt;</description></item>
<item><title>Acme to relocate headquarters to Sandy Springs</title><link>https://example.com/a2</link><pubDate>Tue, 06 Oct 2026 12:00:00 GMT</pubDate><source>Dup</source><description></description></item>
<item><title>Dunwoody bake sale raises money</title><link>https://example.com/b</link><pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Beta signs lease at Perimeter Summit</title><link>javascript:alert(1)</link><pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Gamma expands office in Brookhaven</title><link>https://example.com/g</link><pubDate>garbage</pubDate></item>
<item><title>Delta Co signs lease in Alpharetta's North Point</title><link>https://example.com/al</link><pubDate>Tue, 06 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Both Co relocates headquarters between Dunwoody and Alpharetta</title><link>https://example.com/both</link><pubDate>Tue, 06 Oct 2026 13:00:00 GMT</pubDate></item>
<item><title>Cobbco opens new headquarters in Cumberland</title><link>https://example.com/cobb</link><pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Gwinco expands office lease in Peachtree Corners</title><link>https://example.com/gw</link><pubDate>Wed, 07 Oct 2026 13:00:00 GMT</pubDate></item>
<item><title>Zeta signs lease at Concourse Office Park</title><link>https://example.com/zeta</link><pubDate>Wed, 07 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Houston company moves HQ</title><link>https://example.com/h</link></item>
</channel></rss>`;

const raw = parseRSS(xml);
t('parses 11 items', raw.length === 11);
t('CDATA decoded', raw[0].title === 'Acme to relocate headquarters to Sandy Springs');
t('description tags stripped', raw[0].desc === '350 jobs');
const out = normaliseItems(raw);
t('keeps only area+move matches, dedupes, drops unsafe URL (7 left)', out.length === 7);
t('Concourse item tagged concourse and perimeter', JSON.stringify(out.find(i => i.title.startsWith('Zeta')).areas) === '["perimeter","concourse"]');
t('Cobb item tagged cobb', JSON.stringify(out.find(i => i.title.startsWith('Cobbco')).areas) === '["cobb"]');
t('Gwinnett item tagged gwinnett', JSON.stringify(out.find(i => i.title.startsWith('Gwinco')).areas) === '["gwinnett"]');
t('Alpharetta item tagged alpharetta only', JSON.stringify(out.find(i => i.title.startsWith('Delta')).areas) === '["alpharetta"]');
t('Perimeter item tagged perimeter only', JSON.stringify(out.find(i => i.title.startsWith('Acme')).areas) === '["perimeter"]');
t('item naming both areas tagged with both', out.find(i => i.title.startsWith('Both')).areas.length === 2);
t('unsafe javascript: URL dropped', !out.some(i => i.url.startsWith('javascript')));
t('bad date -> null', out.find(i => i.title.startsWith('Gamma')).publishedAt === null);
t('status is unverified_lead', out.every(i => i.status === 'unverified_lead'));
t('safeUrl rejects non-http', safeUrl('data:text/html,x') === '' && safeUrl('https://a.com/x') !== '');

// handler: fail-closed behaviour
(async () => {
  delete process.env.ALLOWED_ORIGINS;
  let r = await mod.handler({ httpMethod: 'GET', headers: { origin: 'https://odysseyblack2026.netlify.app' } });
  t('no ALLOWED_ORIGINS -> 500 server_not_configured', r.statusCode === 500 && JSON.parse(r.body).error === 'server_not_configured');
  process.env.ALLOWED_ORIGINS = 'https://odysseyblack2026.netlify.app';
  r = await mod.handler({ httpMethod: 'GET', headers: { origin: 'https://evil.example' } });
  t('wrong origin -> 403, no CORS header', r.statusCode === 403 && !r.headers['Access-Control-Allow-Origin']);
  r = await mod.handler({ httpMethod: 'GET', headers: {} });
  t('missing origin -> 403', r.statusCode === 403);
  const OK = 'https://odysseyblack2026.netlify.app';
  global.fetch = async () => ({ ok: true, text: async () => xml });
  r = await mod.handler({ httpMethod: 'GET', headers: { 'sec-fetch-site': 'same-origin', 'x-nf-client-connection-ip': '9.9.9.1' } });
  t('same-origin browser GET with NO Origin header is allowed (real-browser behaviour)', r.statusCode === 200 && !r.headers['Access-Control-Allow-Origin']);
  r = await mod.handler({ httpMethod: 'GET', headers: { 'sec-fetch-site': 'cross-site' } });
  t('cross-site request without Origin is refused', r.statusCode === 403);
  r = await mod.handler({ httpMethod: 'GET', headers: { 'sec-fetch-site': 'none' } });
  t('direct navigation (sec-fetch-site none) is refused', r.statusCode === 403);
  r = await mod.handler({ httpMethod: 'GET', headers: { referer: OK + '/index.html', 'x-nf-client-connection-ip': '9.9.9.2' } });
  t('no Origin / no sec-fetch but allowed Referer is allowed', r.statusCode === 200);
  r = await mod.handler({ httpMethod: 'GET', headers: { referer: 'https://evil.example/x' } });
  t('foreign Referer is refused', r.statusCode === 403);
  r = await mod.handler({ httpMethod: 'GET', headers: {} });
  t('no headers at all is refused', r.statusCode === 403);
  r = await mod.handler({ httpMethod: 'POST', headers: { origin: 'https://odysseyblack2026.netlify.app' } });
  t('POST -> 405 with exact-origin CORS (not *)', r.statusCode === 405 && r.headers['Access-Control-Allow-Origin'] === 'https://odysseyblack2026.netlify.app');
  // upstream failure surfaces as 502, not empty 200
  global.fetch = async () => { throw new Error('net'); };
  r = await mod.handler({ httpMethod: 'GET', headers: { origin: 'https://odysseyblack2026.netlify.app', 'x-nf-client-connection-ip': '1.1.1.1' } });
  t('all upstream failing -> 502 upstream_unavailable', r.statusCode === 502);
  global.fetch = async () => ({ ok: true, text: async () => xml });
  r = await mod.handler({ httpMethod: 'GET', headers: { origin: 'https://odysseyblack2026.netlify.app', 'x-nf-client-connection-ip': '2.2.2.2' } });
  const b = JSON.parse(r.body);
  t('success path returns normalised unverified items', r.statusCode === 200 && b.items.length === 7 && b.queriesFailed === 0);
  for (let i = 0; i < 12; i++) r = await mod.handler({ httpMethod: 'GET', headers: { origin: 'https://odysseyblack2026.netlify.app', 'x-nf-client-connection-ip': '3.3.3.3' } });
  t('rate limit trips -> 429', r.statusCode === 429);
  console.log(fails ? fails + ' failure(s)' : 'All perimeter-watch tests passed.');
  process.exit(fails ? 1 : 0);
})();
