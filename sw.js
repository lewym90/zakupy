// Service worker: aplikacja działa offline. Pliki aplikacji: najpierw pamięć podręczna, odświeżanie w tle.
const VER = 'zakupy-v0.4.1';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'css/app.css',
  'js/app.js', 'js/util.js', 'js/cats.js', 'js/db.js', 'js/calc.js', 'js/gemini.js', 'js/offers.js',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-180.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VER).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VER).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;
  e.respondWith(caches.open(VER).then(async c => {
    const hit = await c.match(e.request, { ignoreSearch: true });
    const net = fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
    return hit || net;
  }));
});
