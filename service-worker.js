// Service Worker CarburantRadar — gère le cache, les notifications push et le clic dessus.
// Version du cache : à incrémenter à chaque modification majeure pour forcer la mise à jour
const CACHE_NAME = 'carburant-radar-v2.1.0';
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './manifest.json',
  './service-worker.js',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png',
  './icons/icon-96.png'
];

// Installation : mise en cache des assets statiques
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
  // Passer directement à l'état "activating" pour éviter les attentes
  self.skipWaiting();
});

// Activation : suppression des anciens caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          // Supprimer tous les caches qui ne correspondent pas à la version actuelle
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  // Prendre le contrôle des clients immédiatement
  self.clients.claim();
});

// Interception des requêtes : stratégie cache-first avec fallback réseau
self.addEventListener('fetch', function(event) {
  // Ne pas intercepter les requêtes vers des domaines externes (API, etc.)
  if (event.request.url.startsWith('http://') || event.request.url.startsWith('https://')) {
    if (new URL(event.request.url).origin !== self.location.origin) {
      return;
    }
  }

  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        // Si trouvé dans le cache, retourner la réponse
        if (response) {
          return response;
        }

        // Sinon, faire la requête réseau
        return fetch(event.request)
          .then(function(networkResponse) {
            // Mettre à jour le cache avec la nouvelle réponse (si c'est une requête GET)
            if (event.request.method === 'GET') {
              const responseClone = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then(function(cache) {
                  cache.put(event.request, responseClone);
                });
            }
            return networkResponse;
          })
          .catch(function() {
            // Si réseau échoue et pas dans le cache, retourner une réponse par défaut
            return caches.match('./index.html');
          });
      })
  );
});

// Gestion des notifications push (inchangé)
self.addEventListener('push', function(event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'CarburantRadar', body: event.data ? event.data.text() : '' };
  }
  var title = data.title || 'CarburantRadar';
  var options = {
    body: data.body || '',
    icon: 'icons/icon-192.png',
    badge: 'icons/icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      stationId: data.stationId || null,
      lat: (typeof data.lat !== 'undefined') ? data.lat : null,
      lon: (typeof data.lon !== 'undefined') ? data.lon : null
    }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Gestion du clic sur les notifications (inchangé, mais avec gestion du cache)
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var d = event.notification.data || {};
  var stationId = d.stationId || null;
  var url = './';
  if (stationId) {
    url = './#station=' + stationId + ((d.lat != null && d.lon != null) ? ('&lat=' + d.lat + '&lon=' + d.lon) : '');
  }
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        if ('focus' in clientList[i]) {
          // Envoyer un message au client pour lui dire quelle station afficher
          clientList[i].postMessage({
            type: 'NOTIFICATION_CLICK',
            stationId: stationId,
            lat: d.lat,
            lon: d.lon
          });
          return clientList[i].focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
