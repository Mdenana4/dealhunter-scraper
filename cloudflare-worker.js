/**
 * DealHunter Egypt - Cloudflare Worker (Edge API Layer)
 * ======================================================
 * Handles: CORS, rate limiting, caching, request forwarding to Cloud Run
 * Flutter App -> Cloudflare Worker -> Cloud Run (Flask) -> Supabase/TimescaleDB
 *
 * @version 1.0.0
 */

const CLOUDRUN_API_URL = "https://dealhunter-api-PLACEHOLDER.a.run.app";

// ---- Configuration ----
const CONFIG = {
  RATE_LIMIT: 100,           // requests per minute per IP
  RATE_WINDOW: 60,           // window in seconds
  CACHE_TTL: 60,             // cache duration in seconds
  MAX_BODY_SIZE: 1024 * 1024, // 1MB body limit
  ROUTES: {
    HEALTH: "/",
    API: "/api/",
  },
};

// ---- Security Headers ----
const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "X-XSS-Protection": "1; mode=block",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()",
  "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
  "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
};

// ---- In-Memory Rate Limit Store (per Colo) ----
// For production: replace with KV or Durable Objects for global consistency
const rateLimitStore = new Map();

/**
 * Clean expired rate limit entries periodically
 */
function cleanupExpiredRateLimits() {
  const now = Math.floor(Date.now() / 1000);
  for (const [key, data] of rateLimitStore.entries()) {
    if (now > data.windowEnd) {
      rateLimitStore.delete(key);
    }
  }
}

// Run cleanup every 60 seconds
let lastCleanup = Math.floor(Date.now() / 1000);

/**
 * Check rate limit for a given client IP
 * @param {string} clientIP
 * @returns {{allowed: boolean, remaining: number, resetAt: number}}
 */
function checkRateLimit(clientIP) {
  const now = Math.floor(Date.now() / 1000);

  // Periodic cleanup
  if (now - lastCleanup > 60) {
    cleanupExpiredRateLimits();
    lastCleanup = now;
  }

  const windowStart = Math.floor(now / CONFIG.RATE_WINDOW) * CONFIG.RATE_WINDOW;
  const windowEnd = windowStart + CONFIG.RATE_WINDOW;
  const key = `${clientIP}:${windowStart}`;

  const record = rateLimitStore.get(key);
  if (!record) {
    rateLimitStore.set(key, { count: 1, windowEnd });
    return { allowed: true, remaining: CONFIG.RATE_LIMIT - 1, resetAt: windowEnd };
  }

  if (record.count >= CONFIG.RATE_LIMIT) {
    return { allowed: false, remaining: 0, resetAt: record.windowEnd };
  }

  record.count += 1;
  return { allowed: true, remaining: CONFIG.RATE_LIMIT - record.count, resetAt: record.windowEnd };
}

/**
 * Build CORS headers for preflight and actual requests
 * @param {Request} request
 * @returns {Object}
 */
function getCorsHeaders(request) {
  const origin = request.headers.get("Origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-Client-Version, X-Device-ID",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Max-Age": "86400",
  };
}

/**
 * Add security headers to a response
 * @param {Response} response
 * @returns {Response}
 */
function addSecurityHeaders(response) {
  const newHeaders = new Headers(response.headers);
  for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
    newHeaders.set(key, value);
  }
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}

/**
 * Add rate limit headers to a response
 * @param {Response} response
 * @param {{remaining: number, resetAt: number}} rateData
 * @returns {Response}
 */
function addRateLimitHeaders(response, rateData) {
  const newHeaders = new Headers(response.headers);
  newHeaders.set("X-RateLimit-Limit", String(CONFIG.RATE_LIMIT));
  newHeaders.set("X-RateLimit-Remaining", String(Math.max(0, rateData.remaining)));
  newHeaders.set("X-RateLimit-Reset", String(rateData.resetAt));
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
}

/**
 * Create a JSON error response
 * @param {number} status
 * @param {string} message
 * @param {string} code
 * @param {Object} extra
 * @returns {Response}
 */
function jsonError(status, message, code = "ERROR", extra = {}) {
  const body = JSON.stringify({
    success: false,
    error: {
      code,
      message,
      timestamp: new Date().toISOString(),
      ...extra,
    },
  });
  return new Response(body, {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Create a JSON success response
 * @param {Object} data
 * @param {number} status
 * @returns {Response}
 */
function jsonSuccess(data, status = 200) {
  const body = JSON.stringify({
    success: true,
    data,
    timestamp: new Date().toISOString(),
  });
  return new Response(body, {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Handle CORS preflight (OPTIONS)
 * @param {Request} request
 * @returns {Response}
 */
function handleCorsPreflight(request) {
  const corsHeaders = getCorsHeaders(request);
  return new Response(null, {
    status: 204,
    headers: corsHeaders,
  });
}

/**
 * Check Cloudflare Cache for a GET request
 * @param {Request} request
 * @returns {Promise<Response|null>}
 */
async function checkCache(request) {
  try {
    const cache = caches.default;
    const cached = await cache.match(request);
    if (cached) {
      console.log("[OK] Cache hit for:", request.url);
      return cached;
    }
    return null;
  } catch (e) {
    console.error("[ERROR] Cache check failed:", e.message);
    return null;
  }
}

/**
 * Store response in Cloudflare Cache
 * @param {Request} request
 * @param {Response} response
 * @param {number} ttl
 */
async function storeCache(request, response, ttl) {
  try {
    const cache = caches.default;
    // Clone response since it can only be read once
    const responseClone = response.clone();

    // Create a cacheable response with proper headers
    const cacheHeaders = new Headers(responseClone.headers);
    cacheHeaders.set("Cache-Control", `public, max-age=${ttl}`);
    cacheHeaders.set("CF-Cache-Status", "HIT");

    const cacheableResponse = new Response(responseClone.body, {
      status: responseClone.status,
      statusText: responseClone.statusText,
      headers: cacheHeaders,
    });

    await cache.put(request, cacheableResponse);
    console.log("[OK] Cached response for:", request.url, "TTL:", ttl);
  } catch (e) {
    console.error("[ERROR] Cache store failed:", e.message);
  }
}

/**
 * Forward request to Cloud Run backend
 * @param {Request} request
 * @param {string} path
 * @param {string} clientIP
 * @returns {Promise<Response>}
 */
async function forwardToCloudRun(request, path, clientIP) {
  const targetUrl = `${CLOUDRUN_API_URL}${path}`;

  // Build forwarded request headers
  const forwardHeaders = new Headers(request.headers);
  forwardHeaders.set("X-Forwarded-For", clientIP);
  forwardHeaders.set("X-Forwarded-Proto", "https");
  forwardHeaders.set("X-Real-IP", clientIP);
  forwardHeaders.set("X-Edge-Provider", "cloudflare");
  forwardHeaders.set("CF-Worker", "dealhunter-edge");

  // Remove problematic headers
  forwardHeaders.delete("Host");

  // Build request init
  /** @type {RequestInit} */
  const init = {
    method: request.method,
    headers: forwardHeaders,
    redirect: "manual",
  };

  // Forward body for non-GET/HEAD requests
  if (request.method !== "GET" && request.method !== "HEAD") {
    const contentLength = request.headers.get("Content-Length");
    if (contentLength && parseInt(contentLength) > CONFIG.MAX_BODY_SIZE) {
      return jsonError(413, "Request body too large", "BODY_TOO_LARGE", {
        max: CONFIG.MAX_BODY_SIZE,
      });
    }
    init.body = request.body;
  }

  console.log("[OK] Forwarding", request.method, path, "->", targetUrl);

  try {
    const response = await fetch(targetUrl, init);

    // Build response with CORS headers
    const corsHeaders = getCorsHeaders(request);
    const responseHeaders = new Headers(response.headers);

    // Merge CORS headers
    for (const [key, value] of Object.entries(corsHeaders)) {
      responseHeaders.set(key, value);
    }

    // Handle Cloud Run redirects
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("Location");
      if (location) {
        responseHeaders.set("Location", location);
      }
    }

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("[ERROR] Cloud Run forwarding failed:", error.message);
    return jsonError(502, "Backend service unavailable", "BACKEND_ERROR", {
      detail: error.message,
    });
  }
}

/**
 * Main request handler
 * @param {Request} request
 * @param {Object} env
 * @param {Object} ctx
 * @returns {Promise<Response>}
 */
async function handleRequest(request, env, ctx) {
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;
  const clientIP =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("X-Forwarded-For") ||
    "unknown";

  console.log(`[OK] ${method} ${path} from ${clientIP}`);

  // ---- CORS Preflight ----
  if (method === "OPTIONS") {
    return handleCorsPreflight(request);
  }

  // ---- Rate Limiting ----
  const rateResult = checkRateLimit(clientIP);
  if (!rateResult.allowed) {
    console.warn(`[WARN] Rate limit exceeded for ${clientIP}`);
    const err = jsonError(429, "Rate limit exceeded. Try again later.", "RATE_LIMITED", {
      retryAfter: rateResult.resetAt - Math.floor(Date.now() / 1000),
    });
    const errWithHeaders = addRateLimitHeaders(err, rateResult);
    return addSecurityHeaders(errWithHeaders);
  }

  // ---- Health Check ----
  if (path === CONFIG.ROUTES.HEALTH) {
    const healthData = {
      status: "healthy",
      service: "DealHunter Edge",
      version: "1.0.0",
      region: request.cf?.colo || "unknown",
      timestamp: new Date().toISOString(),
    };
    let response = jsonSuccess(healthData);
    response = addRateLimitHeaders(response, rateResult);
    response = addSecurityHeaders(response);
    return response;
  }

  // ---- API Routes -> Forward to Cloud Run ----
  if (path.startsWith(CONFIG.ROUTES.API)) {
    // Check cache for GET requests
    if (method === "GET" && path.startsWith("/api/deals")) {
      const cached = await checkCache(request);
      if (cached) {
        let response = addRateLimitHeaders(cached, rateResult);
        response = addSecurityHeaders(response);
        return response;
      }

      // Forward and cache
      let response = await forwardToCloudRun(request, path + url.search, clientIP);

      if (response.status >= 200 && response.status < 300) {
        ctx.waitUntil(storeCache(request, response.clone(), CONFIG.CACHE_TTL));
      }

      response = addRateLimitHeaders(response, rateResult);
      response = addSecurityHeaders(response);
      return response;
    }

    // Forward all other API requests (no caching)
    let response = await forwardToCloudRun(request, path + url.search, clientIP);
    response = addRateLimitHeaders(response, rateResult);
    response = addSecurityHeaders(response);
    return response;
  }

  // ---- 404 for undefined paths ----
  console.warn(`[WARN] Unknown path: ${method} ${path}`);
  let notFound = jsonError(404, "Not found", "NOT_FOUND", {
    path,
    method,
  });
  notFound = addRateLimitHeaders(notFound, rateResult);
  notFound = addSecurityHeaders(notFound);
  return notFound;
}

// ---- Cloudflare Worker Event Listener ----
addEventListener("fetch", (event) => {
  event.respondWith(
    handleRequest(event.request, {}, event).catch((error) => {
      console.error("[ERROR] Unhandled exception:", error);
      const err = jsonError(500, "Internal server error", "INTERNAL_ERROR", {
        detail: error.message,
      });
      return addSecurityHeaders(err);
    })
  );
});

// ---- ES Module Export (for module format) ----
export default {
  async fetch(request, env, ctx) {
    return handleRequest(request, env, ctx).catch((error) => {
      console.error("[ERROR] Unhandled exception:", error);
      const err = jsonError(500, "Internal server error", "INTERNAL_ERROR", {
        detail: error.message,
      });
      return addSecurityHeaders(err);
    });
  },
};
