/* Service worker ya Afya Smart USSD PWA.
 * Cache-first kwa shell (index + assets + icons) — app inafunguka hata offline.
 * Network-first kwa /api/ na /ussd-config — data ya foleni iwe fresh.
 */
const CACHE = "afya-ussd-v3";
const SHELL = [
  "/mobile/",
  "/mobile/manifest.webmanifest",
  "/mobile/pwa-192.png",
  "/mobile/pwa-512.png",
  "/mobile/pwa-maskable-512.png",
  "/mobile/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  // API / config: network-first (subiri mtandao, cache kama backup)
  if (url.pathname.startsWith("/api/") || url.pathname === "/ussd-config") {
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return resp;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Shell na assets: cache-first
  event.respondWith(
    caches.match(event.request).then(
      (hit) =>
        hit ||
        fetch(event.request).then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return resp;
        })
    )
  );
});
