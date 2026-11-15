// CarburantRadar — mise à jour fiable sans suppression des données utilisateur.
// Ce worker est commun aux pays et conserve les notifications push.
const CACHE_NAME = 'carburant-radar-v3.0.0';
const CACHE_PREFIX = 'carburant-radar-';
const ASSETS_TO_CACHE = [
  './manifest.json', './icons/icon-192.png', './icons/icon-512.png',
  './icons/icon-512-maskable.png', './icons/icon-96.png'
];

self.addEventListener('install', event => {
  // Ne pas pré-cacher l'HTML : une nouvelle publication ne doit jamais rester
  // bloquée derrière une ancienne page stockée au moment de l'installation.
  event.waitUntil(caches.open(CACHE_NAME).then(cache =>
    Promise.allSettled(ASSETS_TO_CACHE.map(url => cache.add(url)))
  ));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME)
      .map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const navigation = request.mode === 'navigate' ||
    (request.headers.get('accept') || '').includes('text/html');
  if (navigation) {
    event.respondWith((async () => {
      try {
        // cache:no-store contourne le cache HTTP et les anciennes copies de HTML.
        const fresh = await fetch(new Request(request, {cache: 'no-store'}));
        if (!fresh.ok) throw new Error('HTTP ' + fresh.status);
        // Sauvegarde uniquement pour un véritable usage hors ligne.
        const cache = await caches.open(CACHE_NAME);
        await cache.put(request, fresh.clone()).catch(() => {});
        return fresh;
      } catch (error) {
        const cached = await caches.match(request);
        if (cached) return cached;
        const fallback = await caches.match(new URL('france/index.html', self.registration.scope).href);
        if (fallback) return fallback;
        return Response.error();
      }
    })());
    return;
  }
  // Les scripts, CSS et autres ressources non HTML suivent le réseau d'abord
  // afin que les changements publiés ne soient pas masqués par un cache ancien.
  event.respondWith((async () => {
    try {
      const fresh = await fetch(request);
      if (!fresh.ok) throw new Error('HTTP ' + fresh.status);
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, fresh.clone()).catch(() => {});
      return fresh;
    } catch (error) {
      return (await caches.match(request)) || Response.error();
    }
  })());
});

self.addEventListener('push', event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; }
  catch (e) { data = {title:'CarburantRadar',body:event.data ? event.data.text() : ''}; }
  const title = data.title || 'CarburantRadar';
  const options = {
    body: data.body || '', icon:'icons/icon-192.png', badge:'icons/icon-192.png',
    vibrate:[100,50,100],
    data:{stationId:data.stationId || null,lat:data.lat ?? null,lon:data.lon ?? null}
  };
  event.waitUntil(self.registration.showNotification(title,options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const d = event.notification.data || {};
  const stationId = d.stationId || null;
  const scope = self.registration.scope;
  const hash = stationId ? '#station=' + encodeURIComponent(stationId) +
    (d.lat != null && d.lon != null ? '&lat=' + d.lat + '&lon=' + d.lon : '') : '';
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(async list => {
    const client = list.find(c => c.url.startsWith(scope) && 'focus' in c);
    // Respecter le pays déjà ouvert ; sinon le pays transmis par la notification.
    const countryFromClient = client && /\/(france|espagne|italie)\//.exec(new URL(client.url).pathname);
    const country = countryFromClient ? countryFromClient[1] :
      (['france','espagne','italie'].includes(d.country) ? d.country : 'france');
    const url = scope + country + '/' + (stationId ? '?notif=1' + hash : '');
    if (client) {
      if (stationId && 'navigate' in client) {
        try { const navigated = await client.navigate(url); return (navigated || client).focus(); }
        catch (e) { /* message fallback below */ }
      }
      if (stationId) client.postMessage({type:'NOTIFICATION_CLICK',stationId,lat:d.lat,lon:d.lon});
      return client.focus();
    }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});
