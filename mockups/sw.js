/* OpenOnco Service Worker — cache-first app shell */
const CACHE = 'openonco-v1';
const SHELL = [
  '/mockups/app.css',
  '/mockups/theme.js',
  '/mockups/manifest.json',
  '/mockups/patient-list.html',
  '/mockups/patient-detail.html',
  '/mockups/board.html',
  '/mockups/login.html',
  '/mockups/clinic.html',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  // Cache-first for app shell, network-first for API calls
  if (e.request.url.includes('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request))
    );
  }
});
