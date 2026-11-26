const fuelFields = {
  Gazole: 'gazole_prix', SP95: 'sp95_prix', SP98: 'sp98_prix', E10: 'e10_prix', E85: 'e85_prix', GPLc: 'gplc_prix',
};

async function stationsFor(alert) {
  const {lat, lon, rayon} = alert;
  const url = new URL('https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records');
  url.searchParams.set('limit', '100');
  url.searchParams.set('where', `within_distance(geom,geom'POINT(${lon} ${lat})',${rayon * 1000}m)`);
  const response = await fetch(url, {signal: AbortSignal.timeout(8000)});
  if (!response.ok) return [];
  return (await response.json()).results || [];
}

export async function deliverExtraAlerts(env, sendNotification, loadStations = stationsFor) {
  if (env.PLUS_ALERTS_DELIVERY !== '1' || !env.PLUS || !env.PLUS_ADMIN_TOKEN) return;
  async function call(path, data) {
    const response = await env.PLUS.fetch('https://plus.internal/scheduled/' + path, {
      method: 'POST', headers: {authorization: 'Bearer ' + env.PLUS_ADMIN_TOKEN, 'content-type': 'application/json'},
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('PLUS extra alerts: ' + response.status);
    return response.json();
  }

  let cursor = null;
  const zones = new Map();
  do {
    const page = await call('alerts', {cursor});
    for (const alert of page.alerts) {
      const key = [alert.lat, alert.lon, alert.rayon].join(',');
      if (!zones.has(key)) zones.set(key, Promise.resolve().then(() => loadStations(alert)).catch(() => []));
      const field = fuelFields[alert.carburant];
      const rows = (await zones.get(key)).map(station => ({station, price: Number(station[field])}))
        .filter(row => Number.isFinite(row.price) && row.price > 0);
      if (rows.length < 2) continue;
      const average = rows.reduce((total, row) => total + row.price, 0) / rows.length;
      const best = rows.reduce((min, row) => row.price < min.price ? row : min);
      const percent = (average - best.price) * 100 / average;
      if (percent < alert.seuil || !best.station.id ||
          !Number.isFinite(best.station.geom?.lat) || !Number.isFinite(best.station.geom?.lon)) continue;
      const {account, id} = alert;
      if (!(await call('reserve', {account, id})).reserved) continue;
      const {station} = best;
      const result = await sendNotification(alert.sub, '⛽ ' + alert.name,
        `${alert.carburant} · ${best.price.toFixed(3).replace('.', ',')} €/L · ${station.adresse || station.ville || 'Station-service'}`,
        env, {stationId: String(station.id), lat: station.geom.lat, lon: station.geom.lon,
          carburant: alert.carburant, country: 'france'});
      if (result?.expire) await call('remove', {account, id});
    }
    cursor = page.cursor;
  } while (cursor);
}
