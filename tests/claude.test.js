// node tests/claude.test.js  (no network)
const path = require('path');
const mod = require(path.join(__dirname, '..', 'netlify', 'functions', 'claude.js'));
const { buildUpstreamBody } = mod._test;
let fails = 0;
function t(n, c) { console.log((c ? 'PASS: ' : 'FAIL: ') + n); if (!c) fails++; }
const O = 'https://odysseyblack2026.netlify.app';
const good = JSON.stringify({ model: 'claude-sonnet-5', max_tokens: 500, messages: [{ role: 'user', content: 'hi' }] });
function ev(o) { return Object.assign({ httpMethod: 'POST', headers: { origin: O, 'x-nf-client-connection-ip': '9.9.9.' + Math.floor(Math.random() * 250) }, body: good }, o); }
(async () => {
  process.env.ANTHROPIC_API_KEY = 'k';
  delete process.env.ALLOWED_ORIGINS;
  let r = await mod.handler(ev());
  t('no ALLOWED_ORIGINS -> 500 server_not_configured', r.statusCode === 500 && JSON.parse(r.body).error === 'server_not_configured');
  process.env.ALLOWED_ORIGINS = O;
  r = await mod.handler(ev({ headers: { origin: 'https://evil.example' } }));
  t('wrong origin -> 403 and no CORS header', r.statusCode === 403 && !r.headers['Access-Control-Allow-Origin']);
  r = await mod.handler(ev({ headers: {} }));
  t('no origin, no fetch-site, no referer -> 403', r.statusCode === 403);
  let sent = null;
  global.fetch = async (u, o) => { sent = JSON.parse(o.body); return { ok: true, status: 200, json: async () => ({ content: [{ text: 'ok' }] }) }; };
  r = await mod.handler(ev({ headers: { 'sec-fetch-site': 'same-origin', 'x-nf-client-connection-ip': '1.1.1.1' } }));
  t('same-origin GET-less POST (no Origin, sec-fetch-site same-origin) allowed', r.statusCode === 200);
  r = await mod.handler(ev({ headers: { 'sec-fetch-site': 'cross-site', 'x-nf-client-connection-ip': '1.1.1.2' } }));
  t('cross-site without Origin -> 403', r.statusCode === 403);
  r = await mod.handler(ev({ headers: { referer: O + '/page', 'x-nf-client-connection-ip': '1.1.1.3' } }));
  t('allowed Referer only -> 200', r.statusCode === 200);
  r = await mod.handler(ev());
  t('allowed origin -> 200 with exact-origin CORS (not *)', r.statusCode === 200 && r.headers['Access-Control-Allow-Origin'] === O);
  r = await mod.handler(ev({ httpMethod: 'OPTIONS' }));
  t('OPTIONS from allowed origin -> 204 with exact CORS', r.statusCode === 204 && r.headers['Access-Control-Allow-Origin'] === O);
  r = await mod.handler(ev({ httpMethod: 'OPTIONS', headers: { origin: 'https://evil.example' } }));
  t('OPTIONS from other origin -> 403', r.statusCode === 403);
  r = await mod.handler(ev({ httpMethod: 'GET' }));
  t('GET -> 405', r.statusCode === 405);
  r = await mod.handler(ev({ body: '{bad' }));
  t('bad JSON -> 400', r.statusCode === 400 && JSON.parse(r.body).error === 'invalid_json');
  r = await mod.handler(ev({ body: 'x'.repeat(250000) }));
  t('oversized body -> 413', r.statusCode === 413);
  // field whitelist and caps
  r = await mod.handler(ev({ body: JSON.stringify({ model: 'claude-sonnet-5', max_tokens: 999999, tools: [{ name: 'x' }], stream: true, metadata: { a: 1 }, messages: [{ role: 'user', content: 'hi', extra: 1 }] }) }));
  t('only whitelisted fields forwarded; tools/stream/metadata dropped', sent && !('tools' in sent) && !('stream' in sent) && !('metadata' in sent) && !('extra' in sent.messages[0]));
  t('max_tokens capped at 4000', sent.max_tokens === 4000);
  t('invalid model rejected', buildUpstreamBody({ model: 'gpt-4', messages: [{ role: 'user', content: 'x' }] }).error === 'invalid_model');
  t('non-string content rejected', buildUpstreamBody({ model: 'claude-x', messages: [{ role: 'user', content: [{ type: 'image' }] }] }).error === 'invalid_messages');
  t('too many chars rejected', buildUpstreamBody({ model: 'claude-x', messages: [{ role: 'user', content: 'a'.repeat(61000) }] }).error === 'too_large');
  t('system prompt forwarded when a string', buildUpstreamBody({ model: 'claude-x', system: 'be brief', messages: [{ role: 'user', content: 'x' }] }).body.system === 'be brief');
  // upstream error passes status and JSON, no stack
  global.fetch = async () => ({ ok: false, status: 429, json: async () => ({ error: { type: 'rate_limit_error' } }) });
  r = await mod.handler(ev());
  t('upstream error status passed through as JSON', r.statusCode === 429 && JSON.parse(r.body).error.type === 'rate_limit_error');
  global.fetch = async () => { throw new Error('boom secret detail'); };
  r = await mod.handler(ev());
  t('network failure -> 502 with no stack or message leak', r.statusCode === 502 && !/boom|stack/.test(r.body));
  delete process.env.ANTHROPIC_API_KEY;
  r = await mod.handler(ev());
  t('missing API key -> 500 clear message', r.statusCode === 500 && /ANTHROPIC_API_KEY/.test(r.body));
  process.env.ANTHROPIC_API_KEY = 'k';
  global.fetch = async () => ({ ok: true, status: 200, json: async () => ({}) });
  const e = ev(); e.headers['x-nf-client-connection-ip'] = '7.7.7.7';
  for (let i = 0; i < 25; i++) r = await mod.handler(e);
  t('rate limit trips -> 429', r.statusCode === 429);
  console.log(fails ? fails + ' failure(s)' : 'All claude proxy tests passed.');
  process.exit(fails ? 1 : 0);
})();
