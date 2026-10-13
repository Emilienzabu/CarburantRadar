// Service Worker CarburantRadar — gère le cache, les notifications push et le clic dessus.
// Version du cache : à incrémenter à chaque modification majeure pour forcer la mise à jour
const CACHE_NAME = 'carburant-radar-v2.2.0';
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

// Interception des requêtes.
// - Pages HTML (navigation) : network-first, pour toujours avoir la dernière version quand il y a du réseau.
// - Reste (icônes, manifest...) : cache-first, comme avant, pour la rapidité et le mode hors-ligne.
self.addEventListener('fetch', function(event) {
  // Ne pas intercepter les requêtes vers des domaines externes (API, etc.)
  if (event.request.url.startsWith('http://') || event.request.url.startsWith('https://')) {
    if (new URL(event.request.url).origin !== self.location.origin) {
      return;
    }
  }

  var estNavigation = event.request.mode === 'navigate' ||
    (event.request.method === 'GET' && event.request.headers.get('accept') && event.request.headers.get('accept').indexOf('text/html') !== -1);

  if (estNavigation) {
    // Network-first : on tente toujours le réseau d'abord pour avoir la dernière version du site.
    event.respondWith(
      fetch(event.request)
        .then(function(networkResponse) {
          var responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, responseClone);
          });
          return networkResponse;
        })
        .catch(function() {
          // Hors ligne : on retombe sur le cache.
          return caches.match(event.request).then(function(cached) {
            return cached || caches.match('./index.html');
          });
        })
    );
    return;
  }

  // Cache-first pour le reste (icônes, manifest, etc.)
  event.respondWith(
    caches.match(event.request)
      .then(function(response) {
        if (response) {
          return response;
        }
        return fetch(event.request)
          .then(function(networkResponse) {
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

// Gestion du clic sur les notifications : ouvre l'app du pays qui a reçu la notification, directement sur la station concernée.
// (Avant, l'URL relative './' pointait vers la racine du site /CarburantRadar/ et non vers /france/, /espagne/ ou /italie/ :
// la station n'était jamais affichée quand l'app était fermée.)
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var d = event.notification.data || {};
  var stationId = d.stationId || null;
  // Le scope de ce service worker est l'app du pays concerné (…/france/, …/espagne/ ou …/italie/)
  var scope = self.registration.scope;
  var hash = stationId
    ? '#station=' + encodeURIComponent(stationId) + ((d.lat != null && d.lon != null) ? ('&lat=' + d.lat + '&lon=' + d.lon) : '')
    : '';
  // Le paramètre ?notif=1 force un vrai rechargement : un simple changement de #fragment ne relancerait pas la lecture de la station par l'app
  var url = stationId ? (scope + '?notif=1' + hash) : scope;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      var c = null;
      for (var i = 0; i < clientList.length; i++) {
        if (clientList[i].url.indexOf(scope) === 0 && 'focus' in clientList[i]) { c = clientList[i]; break; }
      }
      if (c) {
        // App déjà ouverte : on la recharge sur la station ; si le navigateur refuse, repli sur un message à la page
        var nav = (stationId && 'navigate' in c) ? c.navigate(url) : Promise.reject(new Error('no navigate'));
        return nav.then(function(w) { return (w || c).focus(); }, function() {
          c.postMessage({ type: 'NOTIFICATION_CLICK', stationId: stationId, lat: d.lat, lon: d.lon });
          return c.focus();
        });
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
