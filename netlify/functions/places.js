// netlify/functions/places.js
//
// Server-side proxy for Google Places Text Search. The Google API key lives
// only here, as a Netlify environment variable (GOOGLE_PLACES_KEY) — never
// in the browser, never in localStorage, never routed through a third-party
// CORS proxy.
//
// DEPLOY STEPS (required before Market Expansion search will work):
//   1. Commit this file to netlify/functions/places.js in the repo.
//   2. In the Netlify dashboard: Site settings -> Environment variables ->
//      add GOOGLE_PLACES_KEY (your Google Places API key) and
//      ALLOWED_ORIGINS (comma-separated, e.g.
//      "https://odysseyblack2026.netlify.app,https://deploy-preview-12--odysseyblack2026.netlify.app").
//      This is REQUIRED — with no value set, every request is rejected with
//      server_not_configured rather than falling back to permissive/wildcard CORS.
//   3. Deploy.
//
// ============================================================================
// HONEST LIMITATIONS — read before relying on this for real quota protection
// ============================================================================
// 1. ORIGIN CHECK: the Origin header is sent by browsers and enforced by
//    browsers via CORS. It is NOT a security boundary against a determined
//    attacker — anyone calling this endpoint directly with curl/Postman can
//    set any Origin header they like, and this check will not stop them.
//    What it DOES stop: a browser page on some other website silently
//    making requests through your visitor's browser session. That's a real
//    but narrow protection, not "unauthorized access prevention."
// 2. RATE LIMITING: this uses an in-memory Map, local to a single warm
//    function instance. Netlify may run multiple instances concurrently and
//    recycles cold instances, so this limit is NOT a true distributed rate
//    limit — a determined caller spread across enough requests/instances
//    can exceed it. Real protection would need an external store (Upstash
//    Redis, a Netlify Blob store with atomic counters, or similar), which
//    is not configured here. This is the safest available Netlify-native
//    control without adding a new paid dependency, not a strong guarantee.
// ============================================================================

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

const ALLOWED_CATEGORIES = new Set([
  'hotel', 'hospital', 'event_venue', 'lawyer',
  'finance', 'real_estate_agency', 'spa', 'corporate_office'
]);

// Best-effort, instance-local rate limit — see limitation #2 above.
const rateLimitMap = new Map();
const RATE_LIMIT_WINDOW_MS = 60000;
const RATE_LIMIT_MAX_REQUESTS = 20;

function checkRateLimit(clientKey) {
  const now = Date.now();
  const record = rateLimitMap.get(clientKey) || { count: 0, windowStart: now };
  if (now - record.windowStart > RATE_LIMIT_WINDOW_MS) {
    record.count = 0;
    record.windowStart = now;
  }
  record.count += 1;
  rateLimitMap.set(clientKey, record);
  // Prevent unbounded memory growth from many distinct callers in one warm instance
  if (rateLimitMap.size > 5000) { rateLimitMap.clear(); }
  return record.count <= RATE_LIMIT_MAX_REQUESTS;
}

function makeRequestId() {
  return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
}

exports.handler = async function (event) {
  const requestId = makeRequestId();
  const origin = (event.headers && (event.headers.origin || event.headers.Origin)) || '';

  // ALLOWED_ORIGINS: comma-separated list, e.g.
  //   "https://odysseyblack2026.netlify.app,https://deploy-preview-12--odysseyblack2026.netlify.app"
  // This supports both the production URL and Netlify's deploy-preview URLs in one setting.
  const allowedOriginsRaw = process.env.ALLOWED_ORIGINS || '';
  const allowedOrigins = allowedOriginsRaw.split(',').map(function (s) { return s.trim(); }).filter(Boolean);

  // Fail closed: if nothing is configured, this is a server misconfiguration, not
  // permission to serve everyone. Section 13 explicitly forbids a wildcard fallback here.
  if (allowedOrigins.length === 0) {
    console.log(`[places][${requestId}] rejected — ALLOWED_ORIGINS not configured`);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'X-Request-Id': requestId },
      body: JSON.stringify({ error: 'server_not_configured', requestId })
    };
  }

  const originAllowed = requestAllowed(event.headers, origin, allowedOrigins);

  // The CORS header is only ever set to the specific matched origin, never '*',
  // and never set at all for a rejected origin — an unapproved caller gets no
  // CORS header, which browsers already refuse to read cross-origin regardless.
  const headers = {
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Content-Type': 'application/json',
    'X-Request-Id': requestId
  };
  if (originAllowed && origin) {
    headers['Access-Control-Allow-Origin'] = origin;
  }

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers, body: '' };
  }

  if (event.httpMethod !== 'GET') {
    console.log(`[places][${requestId}] rejected method ${event.httpMethod}`);
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'method_not_allowed', requestId }) };
  }

  if (!originAllowed) {
    console.log(`[places][${requestId}] rejected origin: ${origin}`);
    return { statusCode: 403, headers, body: JSON.stringify({ error: 'origin_not_allowed', requestId }) };
  }

  const clientKey = (event.headers && (event.headers['x-nf-client-connection-ip'] || event.headers['client-ip'])) || origin || 'unknown';
  if (!checkRateLimit(clientKey)) {
    console.log(`[places][${requestId}] rate limited: ${clientKey}`);
    return { statusCode: 429, headers, body: JSON.stringify({ error: 'rate_limited', requestId }) };
  }

  if (!process.env.GOOGLE_PLACES_KEY) {
    console.log(`[places][${requestId}] missing GOOGLE_PLACES_KEY`);
    // Deliberately vague to the client — never expose which env var is missing.
    return { statusCode: 500, headers, body: JSON.stringify({ error: 'server_not_configured', requestId }) };
  }

  const params = event.queryStringParameters || {};
  const category = (params.category || '').trim();
  const area = (params.area || '').trim();

  if (!category || category.length > 100 || !area || area.length > 100) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: 'invalid_input', requestId }) };
  }
  if (!/^[a-zA-Z0-9_ ]+$/.test(category) || !/^[a-zA-Z0-9_,.'\- ]+$/.test(area)) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: 'invalid_characters', requestId }) };
  }
  if (!ALLOWED_CATEGORIES.has(category)) {
    return { statusCode: 400, headers, body: JSON.stringify({ error: 'invalid_category', requestId }) };
  }

  const query = encodeURIComponent(category + ' in ' + area);
  const url = 'https://maps.googleapis.com/maps/api/place/textsearch/json?query=' + query + '&key=' + process.env.GOOGLE_PLACES_KEY;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!response.ok) {
      console.log(`[places][${requestId}] upstream HTTP ${response.status}`);
      return { statusCode: 502, headers, body: JSON.stringify({ error: 'upstream_error', requestId }) };
    }

    const data = await response.json();

    if (data.status === 'REQUEST_DENIED' || data.status === 'INVALID_REQUEST') {
      console.log(`[places][${requestId}] google denied: ${data.status}`);
      return { statusCode: 502, headers, body: JSON.stringify({ error: 'google_' + data.status.toLowerCase(), requestId }) };
    }

    // Normalized, minimal result schema — never forward Google's full raw
    // response (which can include far more fields than the app needs, and
    // creates a wider surface than necessary).
    const results = (data.results || []).slice(0, 20).map(function (p) {
      return {
        name: p.name || '',
        address: p.formatted_address || '',
        rating: typeof p.rating === 'number' ? p.rating : null,
        reviewCount: typeof p.user_ratings_total === 'number' ? p.user_ratings_total : 0,
        placeId: p.place_id || '',
        businessStatus: p.business_status || 'UNKNOWN',
        types: Array.isArray(p.types) ? p.types.slice(0, 5) : []
      };
    });

    console.log(`[places][${requestId}] ok, ${results.length} results`);
    return { statusCode: 200, headers, body: JSON.stringify({ status: 'OK', results, requestId }) };

  } catch (err) {
    const isTimeout = err.name === 'AbortError';
    console.log(`[places][${requestId}] error: ${isTimeout ? 'timeout' : err.message}`);
    return { statusCode: isTimeout ? 504 : 500, headers, body: JSON.stringify({ error: isTimeout ? 'timeout' : 'internal_error', requestId }) };
  }
};
