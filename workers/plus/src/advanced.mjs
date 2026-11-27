import { LedgerError } from './features.mjs';

const dayMs = 86400000;
const live = 'https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records';
const history = 'https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/prix-des-carburants-j-1/records';
const demoRoute = 'https://router.project-osrm.org/route/v1/driving/';
const fuels = {Gazole: 'gazole', SP95: 'sp95', SP98: 'sp98', E10: 'e10', E85: 'e85', GPLc: 'gplc'};

function between(value, min, max) {
  return Number.isFinite(value) && value >= min && value <= max;
}

function location(point) {
  return between(point?.lat, -90, 90) && between(point.lon, -180, 180);
}

function fuelField(fuel) {
  if (!Object.hasOwn(fuels, fuel)) throw new LedgerError('advanced_input_invalid');
  return fuels[fuel];
}

async function get(url, load) {
  // Workers n’implémente pas redirect: 'error'. Les réponses 3xx restent refusées par response.ok.
  const response = await load(url, {headers: {accept: 'application/json'},
    signal: AbortSignal.timeout(7000), redirect: 'manual'});
  if (!response.ok) throw new LedgerError('advanced_service_unavailable', 503);
  return response.json();
}

export async function nearby(point, radius, load = fetch) {
  const url = new URL(live);
  url.searchParams.set('limit', '100');
  url.searchParams.set('where', `within_distance(geom,geom'POINT(${point.lon} ${point.lat})',${radius * 1000}m)`);
  const {results} = await get(url, load);
  if (!Array.isArray(results)) throw new LedgerError('advanced_service_unavailable', 503);
  return results;
}

async function aggregated(ids, field, since, load) {
  const url = new URL(history);
  const day = "date_format(update,'yyyy-MM-dd')";
  url.searchParams.set('limit', '100');
  url.searchParams.set('where', `id IN (${ids.map(id => '"' + id + '"').join(',')}) AND update >= "${since}" AND ${field} > 0`);
  url.searchParams.set('select', `avg(${field}) AS price`);
  url.searchParams.set('group_by', `${day} AS date`);
  url.searchParams.set('order_by', 'date asc');
  const out = [];
  for (let offset = 0; offset < 400; offset += 100) {
    url.searchParams.set('offset', String(offset));
    const {results} = await get(url, load);
    if (!Array.isArray(results)) throw new LedgerError('advanced_service_unavailable', 503);
    out.push(...results.filter(row => /^\d{4}-\d{2}-\d{2}$/.test(row.date) && row.date >= since &&
      Number.isFinite(row.price) && row.price > 0));
    if (results.length < 100) break;
  }
  return out;
}

export async function detailedAnalysis(params, now, load = fetch) {
  const {period, stationId, center, radius, fuel} = params || {};
  const field = 'price_' + fuelField(fuel);
  if (![30, 90, 365].includes(period) ||
      (stationId !== null && (typeof stationId !== 'string' || !/^\d{1,20}$/.test(stationId))) ||
      (stationId === null && !location(center)) ||
      ![5, 10, 20, 50].includes(radius)) throw new LedgerError('advanced_input_invalid');
  const since = new Date(now - (period - 1) * dayMs).toISOString().slice(0, 10);
  const today = new Date(now).toISOString().slice(0, 10);
  const ids = location(center) ? [...new Set((await nearby(center, radius, load))
    .map(row => String(row.id)).filter(id => /^\d{1,20}$/.test(id)))].slice(0, 60) : [];
  const [zone, station] = await Promise.all([
    ids.length ? aggregated(ids, field, since, load) : [],
    stationId === null ? [] : aggregated([stationId], field, since, load),
  ]);
  if (!(stationId === null ? zone : station).some(row => row.date <= today)) {
    throw new LedgerError('advanced_no_data', 422);
  }
  const byDay = rows => new Map(rows.map(row => [row.date, row.price]));
  const zonePrices = byDay(zone);
  const stationPrices = byDay(station);
  const dates = [], average = [], prices = [];
  for (let offset = period - 1; offset >= 0; offset--) {
    const date = new Date(now - offset * dayMs).toISOString().slice(0, 10);
    dates.push(date);
    average.push(zonePrices.get(date) ?? null);
    prices.push(stationPrices.get(date) ?? null);
  }
  return {dates, average, prices};
}

async function road(points, geometry, load, route) {
  const coordinates = points.map(p => p.lon + ',' + p.lat).join(';');
  const result = await get(route + coordinates + (geometry ? '?overview=simplified&geometries=geojson' : '?overview=false'), load);
  const best = result.routes?.[0];
  if (!best || !between(best.distance, 0, 3000000) || !between(best.duration, 0, 172800)) {
    throw new LedgerError('advanced_service_unavailable', 503);
  }
  return best;
}

export async function detailedTrip(params, route = demoRoute, load = fetch) {
  const {origin, destination, fuel, liters, consumption} = params || {};
  const field = fuelField(fuel) + '_prix';
  if (!location(origin) || !location(destination) || !between(liters, 0, 500) || !between(consumption, 0.1, 100)) {
    throw new LedgerError('advanced_input_invalid');
  }
  const direct = await road([origin, destination], true, load, route);
  const line = direct.geometry?.coordinates;
  if (!Array.isArray(line) || line.length < 2 || !line.every(point =>
    Array.isArray(point) && location({lon: point[0], lat: point[1]}))) {
    throw new LedgerError('advanced_service_unavailable', 503);
  }
  const count = Math.min(7, Math.max(2, Math.ceil(direct.distance / 20000) + 1));
  const points = Array.from({length: count}, (_, i) =>
    line[Math.round(i * (line.length - 1) / (count - 1))]);
  function cost(price, km) { return price * (liters + km * consumption / 100); }
  const responses = await Promise.allSettled(points.map(([lon, lat]) => nearby({lat, lon}, 9, load)));
  const candidates = new Map();
  for (const response of responses) {
    if (response.status !== 'fulfilled') continue;
    for (const row of response.value) {
      const {id, geom, adresse, ville} = row;
      const price = Number(row[field]);
      if (!id || !location(geom) || !between(price, 0.01, 10)) continue;
      candidates.set(String(id), {id: String(id), lat: geom.lat, lon: geom.lon, price,
        address: String(adresse || '').slice(0, 180), city: String(ville || '').slice(0, 100)});
    }
  }
  const verified = [];
  const selected = [...candidates.values()].sort((a, b) => a.price - b.price).slice(0, 12);
  for (let offset = 0; offset < selected.length; offset += 4) {
    const results = await Promise.allSettled(selected.slice(offset, offset + 4).map(async station => {
      const detour = await road([origin, station, destination], false, load, route);
      const km = Math.max(0, (detour.distance - direct.distance) / 1000);
      return {...station, km, minutes: Math.max(0, (detour.duration - direct.duration) / 60),
        total: cost(station.price, km)};
    }));
    verified.push(...results.filter(result => result.status === 'fulfilled').map(result => result.value));
  }
  if (verified.length < 2) throw new LedgerError('advanced_no_data', 422);
  const choices = [
    {label: 'Coût total le plus bas', station: [...verified].sort((a, b) => a.total - b.total)[0]},
    {label: 'Prix au litre le plus bas', station: [...verified].sort((a, b) => a.price - b.price)[0]},
    {label: 'Détour le plus court', station: [...verified].sort((a, b) => a.minutes - b.minutes || a.km - b.km)[0]},
  ];
  return {choices, verified: verified.length};
}
