// Node tests for netlify/functions/distance.js (no network: fetch is mocked).
const assert = require('assert');
process.env.ALLOWED_ORIGINS = 'https://odysseyblack2026.netlify.app';
process.env.GOOGLE_PLACES_KEY = 'test-key';
const mod = require('../netlify/functions/distance.js');
let fails = 0;
function t(name, fn) { return Promise.resolve().then(fn).then(() => console.log('PASS: ' + name), (e) => { fails++; console.log('FAIL: ' + name + ' -> ' + e.message); }); }
const OK = { origin: 'https://odysseyblack2026.netlify.app' };
const q = (from, to) => ({ httpMethod: 'GET', headers: OK, queryStringParameters: { from, to } });
(async () => {
  await t('validAddress accepts normal US addresses', () => {
    assert(mod._test.validAddress('6 Concourse Pkwy, Sandy Springs, GA 30328'));
    assert(mod._test.validAddress("Hartsfield-Jackson Atlanta Intl Airport (ATL), 6000 N Terminal Pkwy"));
  });
  await t('validAddress rejects short, long, and odd characters', () => {
    assert(!mod._test.validAddress('abc'));
    assert(!mod._test.validAddress('x'.repeat(201)));
    assert(!mod._test.validAddress('123 Main St; DROP TABLE'));
    assert(!mod._test.validAddress('<script>alert(1)</script>'));
    assert(!mod._test.validAddress('http://evil.example/?a=b'));
  });
  await t('parseRoute converts meters to miles and seconds to minutes', () => {
    const r = mod._test.parseRoute({ routes: [{ distanceMeters: 16093, duration: '1500s' }] });
    assert.strictEqual(r.miles, 10); assert.strictEqual(r.minutes, 25);
  });
  await t('parseRoute returns null for empty, zero, or junk', () => {
    assert.strictEqual(mod._test.parseRoute({}), null);
    assert.strictEqual(mod._test.parseRoute({ routes: [] }), null);
    assert.strictEqual(mod._test.parseRoute({ routes: [{ distanceMeters: 0 }] }), null);
    assert.strictEqual(mod._test.parseRoute({ routes: [{ distanceMeters: 'x' }] }), null);
  });
  await t('rejects a foreign origin with 403 and no CORS header', async () => {
    const r = await mod.handler({ httpMethod: 'GET', headers: { origin: 'https://evil.example' }, queryStringParameters: { from: '6 Concourse Pkwy', to: 'Atlanta Airport' } });
    assert.strictEqual(r.statusCode, 403); assert(!r.headers['Access-Control-Allow-Origin']);
  });
  await t('fails closed when ALLOWED_ORIGINS is empty', async () => {
    const keep = process.env.ALLOWED_ORIGINS; process.env.ALLOWED_ORIGINS = '';
    const r = await mod.handler(q('6 Concourse Pkwy', 'Atlanta Airport'));
    process.env.ALLOWED_ORIGINS = keep; assert.strictEqual(r.statusCode, 500);
  });
  await t('rejects POST with 405', async () => {
    const r = await mod.handler({ httpMethod: 'POST', headers: OK, queryStringParameters: {} });
    assert.strictEqual(r.statusCode, 405);
  });
  await t('bad input is 400 and never calls upstream', async () => {
    let called = false; global.fetch = async () => { called = true; return { ok: true, json: async () => ({}) }; };
    const r = await mod.handler(q('x', 'y'));
    assert.strictEqual(r.statusCode, 400); assert(!called);
  });
  await t('happy path returns miles and minutes only, key sent as header not URL', async () => {
    let seen;
    global.fetch = async (url, opts) => { seen = { url, opts }; return { ok: true, json: async () => ({ routes: [{ distanceMeters: 29632, duration: '1800s', secret: 'x' }] }) }; };
    const r = await mod.handler(q('6 Concourse Pkwy, Sandy Springs, GA', 'Hartsfield-Jackson Atlanta International Airport'));
    const b = JSON.parse(r.body);
    assert.strictEqual(r.statusCode, 200); assert.strictEqual(b.miles, 18.4); assert.strictEqual(b.minutes, 30);
    assert(!('secret' in b)); assert(!seen.url.includes('test-key')); assert.strictEqual(seen.opts.headers['X-Goog-Api-Key'], 'test-key');
    assert(r.headers['Access-Control-Allow-Origin'] === 'https://odysseyblack2026.netlify.app');
  });
  await t('Google 403 maps to routes_not_enabled (502), no key leak', async () => {
    global.fetch = async () => ({ ok: false, status: 403, json: async () => ({}) });
    const r = await mod.handler(q('6 Concourse Pkwy, Sandy Springs, GA', 'Atlanta Airport GA'));
    assert.strictEqual(r.statusCode, 502); assert(r.body.includes('routes_not_enabled')); assert(!r.body.includes('test-key'));
  });
  await t('no route is 404', async () => {
    global.fetch = async () => ({ ok: true, json: async () => ({}) });
    const r = await mod.handler(q('6 Concourse Pkwy, Sandy Springs, GA', 'Nowhere Land Zzzz'));
    assert.strictEqual(r.statusCode, 404);
  });
  await t('network failure is 500 with a generic error', async () => {
    global.fetch = async () => { throw new Error('boom with key test-key'); };
    const r = await mod.handler(q('6 Concourse Pkwy, Sandy Springs, GA', 'Atlanta Airport GA'));
    assert.strictEqual(r.statusCode, 500); assert(!r.body.includes('test-key')); assert(!r.body.includes('boom'));
  });
  await t('rate limit trips after 20 requests from one client', async () => {
    global.fetch = async () => ({ ok: true, json: async () => ({ routes: [{ distanceMeters: 1609, duration: '60s' }] }) });
    let last; for (let i = 0; i < 25; i++) { last = await mod.handler({ httpMethod: 'GET', headers: Object.assign({ 'x-nf-client-connection-ip': '9.9.9.9' }, OK), queryStringParameters: { from: '6 Concourse Pkwy, Sandy Springs', to: 'Atlanta Airport GA' } }); }
    assert.strictEqual(last.statusCode, 429);
  });
  console.log(fails ? fails + ' FAILED' : 'ALL PASSED'); process.exit(fails ? 1 : 0);
})();
