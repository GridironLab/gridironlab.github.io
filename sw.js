/* Gridiron Lab — service worker
   Un "service worker" es un programita que el navegador instala junto con la
   app y que se pone entre la app e internet. Dos estrategias:
   - La página (datos del día): RED PRIMERO. Siempre intenta bajar la versión
     nueva; si no hay señal, muestra la última que se guardó.
   - Íconos y fuentes (casi nunca cambian): CACHÉ PRIMERO, para abrir rápido. */
const CACHE = 'gridiron-v1';
const BASICOS = ['./', './manifest.webmanifest', './iconos/icono-192.png', './iconos/icono-512.png', './iconos/favicon.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(BASICOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (req.mode === 'navigate') {                       // la página
    e.respondWith(
      fetch(req, { cache: 'no-store' })
        .then((r) => { const copia = r.clone(); caches.open(CACHE).then((c) => c.put('./', copia)); return r; })
        .catch(() => caches.match('./'))
    );
    return;
  }

  const estatico = url.origin === location.origin || /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (estatico) {                                      // íconos, manifiesto, fuentes
    e.respondWith(
      caches.match(req).then((guardado) => guardado || fetch(req).then((r) => {
        if (r.ok || r.type === 'opaque') { const copia = r.clone(); caches.open(CACHE).then((c) => c.put(req, copia)); }
        return r;
      }))
    );
  }
});
