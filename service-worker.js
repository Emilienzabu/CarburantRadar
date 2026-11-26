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
    data:{stationId:data.stationId || null,lat:data.lat ?? null,lon:data.lon ?? null,
      country:data.country ?? null,carburant:data.carburant ?? data.fuel ?? null}
  };
  event.waitUntil(self.registration.showNotification(title,options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const d = event.notification.data || {};
  const stationId = d.stationId || null;
  const scope = self.registration.scope;
  const hash = new URLSearchParams();
  if (stationId) {
    hash.set('station', stationId);
    if (d.lat != null && d.lon != null) {
      hash.set('lat', d.lat);
      hash.set('lon', d.lon);
    }
    if (d.carburant) hash.set('carburant', d.carburant);
  }
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(async list => {
    const windows = list.filter(c => c.url.startsWith(scope) && 'focus' in c);
    const countryOf = c => /\/(france|espagne|italie)\//.exec(new URL(c.url).pathname)?.[1];
    const explicitCountry = ['france','espagne','italie'].includes(d.country) ? d.country : null;
    const country = explicitCountry || windows.map(countryOf).find(Boolean) || 'france';
    const existing = windows.find(c => countryOf(c) === country);
    const client = existing || windows.find(c => typeof c.navigate === 'function');
    const target = new URL(country + '/', scope);
    if (stationId) {
      target.searchParams.set('notif', '1');
      target.hash = hash.toString();
    }
    if (client) {
      if (stationId && typeof client.navigate === 'function') {
        try {
          const navigated = await client.navigate(target.href);
          if (navigated) return navigated.focus();
        }
        catch (e) { /* message fallback below */ }
      }
      if (!stationId) return client.focus();
      if (existing) {
        existing.postMessage({type:'NOTIFICATION_CLICK',stationId,lat:d.lat,lon:d.lon,carburant:d.carburant});
        return existing.focus();
      }
    }
    if (clients.openWindow) return clients.openWindow(target.href);
  }));
});
