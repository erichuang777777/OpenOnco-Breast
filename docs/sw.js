// OpenOnco bundle service worker (CSD-6E + CSD-11A swr)
// Two strategies in one SW:
//   1. Cache-first for engine bundle artifacts (large, infrequent).
//   2. Stale-while-revalidate for try.html + style.css — repeat visits
//      paint instantly from cache while a fresh copy fetches in the
//      background, so the dropdowns aren't gated on the HTML download.
// Cache name is stamped with the core bundle's SHA-256 prefix so a KB
// push automatically rotates the cache key.
const CACHE_NAME = 'openonco-bundle-l3-4ea16e8b3530';
const PRECACHE = [
  '/manifest.webmanifest',
  '/logo.svg',
  '/favicon.svg',
  '/openonco-engine-index.json',
  '/openonco-engine-core.zip',
  '/try.html',
  '/ukr/try.html',
  '/style.css',
];
// Routes that use stale-while-revalidate (instant from cache, refresh
// in background). HTML pages must be on this list — never cache-first,
// or the user gets stuck on an old build.
const SWR_PATHS = ['/try.html', '/ukr/try.html', '/about.html', '/ukr/about.html', '/style.css'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // Precache best-effort: don't fail the SW install if a single
      // file 404s (e.g. an old deploy that hasn't shipped the index yet).
      Promise.all(PRECACHE.map((u) => cache.add(u).catch(() => null)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k.startsWith('openonco-bundle-') && k !== CACHE_NAME)
            .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

function staleWhileRevalidate(event) {
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request, { ignoreSearch: true }).then((hit) => {
        const network = fetch(event.request).then((resp) => {
          if (resp && resp.ok) cache.put(event.request, resp.clone());
          return resp;
        }).catch(() => hit);
        return hit || network;
      })
    )
  );
}

function networkFirstNavigation(event) {
  event.respondWith(
    fetch(event.request, { cache: 'no-store' }).catch(() =>
      caches.match(event.request, { ignoreSearch: true })
    )
  );
}

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  if (event.request.mode === 'navigate') {
    return networkFirstNavigation(event);
  }

  // SWR for the small interactive shell (HTML + CSS).
  if (SWR_PATHS.indexOf(url.pathname) !== -1) {
    return staleWhileRevalidate(event);
  }

  // Cache-first for the heavy engine bundles.
  const cacheFirstMatch =
    url.pathname.endsWith('/openonco-engine-core.zip') ||
    url.pathname.endsWith('/openonco-engine-index.json') ||
    url.pathname.startsWith('/disease/openonco-');
  if (!cacheFirstMatch) return;
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request, { ignoreSearch: true }).then((hit) =>
        hit || fetch(event.request).then((resp) => {
          if (resp && resp.ok) {
            const clone = resp.clone();
            cache.put(event.request, clone);
          }
          return resp;
        })
      )
    )
  );
});
