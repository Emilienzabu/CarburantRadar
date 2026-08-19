// Service Worker CarburantRadar — reçoit les notifications push et gère le clic dessus.
// Ne gère PAS le cache/offline pour l'instant : uniquement le Web Push.

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
    vibrate: [100, 50, 100]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Au clic sur la notification : ramène l'app au premier plan si elle est déjà ouverte,
// sinon l'ouvre dans un nouvel onglet. Transmet aussi les données de la station.
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  var stationId = event.notification.data ? event.notification.data.stationId : null;
  var url = './';
  if (stationId) {
    url = './#station=' + stationId;
  }
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (var i = 0; i < clientList.length; i++) {
        if ('focus' in clientList[i]) {
          // Envoyer un message au client pour lui dire quelle station afficher
          clientList[i].postMessage({
            type: 'NOTIFICATION_CLICK',
            stationId: stationId
          });
          return clientList[i].focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
