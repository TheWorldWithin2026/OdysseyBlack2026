// netlify/functions/distance.js
//
// Driving distance between two addresses, for the Quote Builder. Uses the Google
// Routes API with the same server-side key as places.js (GOOGLE_PLACES_KEY). The key
// never reaches the browser. The Routes API must be enabled for that key in Google
// Cloud; if it is not, the app says so and the person types the miles instead.
//
// Same guard rails as places.js: fail-closed ALLOWED_ORIGINS, instance-local rate
// limit (best effort, not a distributed limit), strict input checks, no raw upstream
// output forwarded.

function requestAllowed(headers, origin, allowed) {
  if (origin) return allowed.indexOf(origin) !== -1;
  const h = headers || {};
  const site = String(h['sec-fetch-site'] || h['Sec-Fetch-Site'] || '').toLowerCase();
  if (site) return site === 'same-origin';
  const ref = h.referer || h.Referer || '';
  try { return allowed.indexOf(new URL(ref).origin) !== -1; } catch (e) { return false; }
}

const rateLimitMap = new Map();
const RATE_LIMIT_WINDOW_MS = 60000;
const RATE_LIMIT_MAX_REQUESTS = 20;
function checkRateLimit(clientKey) {
  const now = Date.now();
  const record = rateLimitMap.get(clientKey) || { count: 0, windowStart: now };
  if (now - record.windowStart > RATE_LIMIT_WINDOW_MS) { record.count = 0; record.windowStart = now; }
  record.count += 1;
  rateLimitMap.set(clientKey, record);
  if (rateLimitMap.size > 5000) { rateLimitMap.clear(); }
  return record.count <= RATE_LIMIT_MAX_REQUESTS;
}

function validAddress(s) {
  return typeof s === 'string' && s.length >= 5 && s.length <= 200 && /^[a-zA-Z0-9 ,.#'\/&()\-]+$/.test(s);
}

// Routes API returns distanceMeters and a duration string like "1234s".
function parseRoute(data) {
  const r = data && Array.isArray(data.routes) ? data.routes[0] : null;
  if (!r || typeof r.distanceMeters !== 'number' || !(r.distanceMeters > 0)) return null;
  const secs = parseInt(String(r.duration || '').replace(/s$/, ''), 10);
  return {
    miles: Math.round(r.distanceMeters / 1609.344 * 10) / 10,
    minutes: isFinite(secs) ? Math.round(secs / 60) : null
  };
}

function makeRequestId() { return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8); }

exports.handler = async function (event) {
  const requestId = makeRequestId();
  const origin = (event.headers && (event.headers.origin || event.headers.Origin)) || '';
  const allowedOrigins = (process.env.ALLOWED_ORIGINS || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean);
  const base = { 'Content-Type': 'application/json', 'X-Request-Id': requestId };
  if (allowedOrigins.length === 0) {
    return { statusCode: 500, headers: base, body: JSON.stringify({ error: 'server_not_configured', requestId }) };
  }
  const originAllowed = requestAllowed(event.headers, origin, allowedOrigins);
  const headers = Object.assign({ 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET, OPTIONS' }, base);
  if (originAllowed && origin) headers['Access-Control-Allow-Origin'] = origin;
  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers, body: '' };
  if (event.httpMethod !== 'GET') return { statusCode: 405, headers, body: JSON.stringify({ error: 'method_not_allowed', requestId }) };
  if (!originAllowed) return { statusCode: 403, headers, body: JSON.stringify({ error: 'origin_not_allowed', requestId }) };
  const clientKey = (event.headers && (event.headers['x-nf-client-connection-ip'] || event.headers['client-ip'])) || origin || 'unknown';
  if (!checkRateLimit(clientKey)) return { statusCode: 429, headers, body: JSON.stringify({ error: 'rate_limited', requestId }) };
  if (!process.env.GOOGLE_PLACES_KEY) return { statusCode: 500, headers, body: JSON.stringify({ error: 'server_not_configured', requestId }) };

  const p = event.queryStringParameters || {};
  const from = (p.from || '').trim(), to = (p.to || '').trim();
  if (!validAddress(from) || !validAddress(to)) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: 'invalid_input', requestId }) };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(function () { controller.abort(); }, 8000);
    const response = await fetch('https://routes.googleapis.com/directions/v2:computeRoutes', {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': process.env.GOOGLE_PLACES_KEY,
        'X-Goog-FieldMask': 'routes.distanceMeters,routes.duration'
      },
      body: JSON.stringify({
        origin: { address: from }, destination: { address: to },
        travelMode: 'DRIVE', units: 'IMPERIAL', regionCode: 'US'
      })
    });
    clearTimeout(timeout);
    if (!response.ok) {
      console.log('[distance][' + requestId + '] upstream HTTP ' + response.status);
      return { statusCode: 502, headers, body: JSON.stringify({ error: response.status === 403 ? 'routes_not_enabled' : 'upstream_error', requestId }) };
    }
    const route = parseRoute(await response.json());
    if (!route) return { statusCode: 404, headers, body: JSON.stringify({ error: 'no_route', requestId }) };
    return { statusCode: 200, headers, body: JSON.stringify({ status: 'OK', miles: route.miles, minutes: route.minutes, requestId }) };
  } catch (err) {
    const isTimeout = err && err.name === 'AbortError';
    console.log('[distance][' + requestId + '] error: ' + (isTimeout ? 'timeout' : (err && err.message)));
    return { statusCode: isTimeout ? 504 : 500, headers, body: JSON.stringify({ error: isTimeout ? 'timeout' : 'internal_error', requestId }) };
  }
};

exports._test = { requestAllowed, validAddress, parseRoute, checkRateLimit };
