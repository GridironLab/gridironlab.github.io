/* Gridiron Lab — service worker
   Un "service worker" es un programita que el navegador instala junto con la
   app y que se pone entre la app e internet. Dos estrategias:
   - La página (datos del día): RED PRIMERO. Siempre intenta bajar la versión
     nueva; si no hay señal, muestra la última que se guardó.
   - Íconos y fuentes (casi nunca cambian): CACHÉ PRIMERO, para abrir rápido. */
// El nombre del caché se sube cuando cambian los archivos que se guardan "caché primero" (íconos, manifiesto, fuentes):
// al activarse, el service worker nuevo borra los cachés con otro nombre y así los cels que ya tenían la app instalada
// reciben los archivos nuevos. v2 = etapa 7 del rediseño (21 nov 2026): íconos y manifiesto del logo "Balón partido".
// v3 = 21 nov 2026: favicon.svg con fondo negro (en una pestaña clara no se veía la mitad blanca del balón).
const CACHE = 'gridiron-v3';
// Las fuentes locales del diseño nuevo (interruptor ?diseno=2) se guardan desde la instalación:
// así la app nueva abre con su letra aunque no haya señal. Son ~50 KB.
const FUENTES = ['./fuentes/onest-latin-400-normal.woff2', './fuentes/onest-latin-500-normal.woff2', './fuentes/onest-latin-600-normal.woff2',
  './fuentes/escudo-barlow-condensed-700-mayusculas.woff2'];
const ICONOS = ['./iconos/icono-192.png', './iconos/icono-512.png', './iconos/icono-maskable-512.png', './iconos/icono-180.png', './iconos/favicon.svg'];
const BASICOS = ['./', './manifest.webmanifest', ...ICONOS, ...FUENTES];

self.addEventListener('install', (e) => {
  // cache: 'reload' = se bajan de la red, no del caché HTTP del navegador (que podría tener todavía el ícono anterior)
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(BASICOS.map((u) => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
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
