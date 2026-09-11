const CACHE_NAME = "crew-mgr-v1";
const OFFLINE_URL = "/offline";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        "/",
        "/offline",
        "/manifest.json",
      ]);
    })
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      return fetch(event.request).then((fetchResponse) => {
        if (event.request.url.includes("/api/")) {
          return fetchResponse;
        }

        if (fetchResponse && fetchResponse.status === 200) {
          const cache = caches.open(CACHE_NAME);
          cache.put(event.request, fetchResponse.clone());
        }

        return fetchResponse;
      });
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    })
  );
});

self.addEventListener("online", () => {
  console.log("Back online - syncing data...");
});

self.addEventListener("offline", () => {
  console.log("Offline mode - working with cached data");
});