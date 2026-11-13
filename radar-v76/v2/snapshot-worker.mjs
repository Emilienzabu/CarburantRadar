// CarburantRadar radar V2 — snapshot France immuable et versionné.
// CANDIDAT : NON DÉPLOYÉ, NON TESTÉ SUR CLOUDFLARE RÉEL (voir docs/INTEGRATION_V2.md).
// Fichier unique, sans import, ESM + WebCrypto uniquement (compatible Workers sans nodejs_compat).
// Liaisons attendues : DB_RADAR (D1, migrations/0001), SNAPSHOTS (R2), RADAR_ADMIN_SECRET (secret),
// ALLOWED_ORIGINS (variable facultative, liste séparée par des virgules).
// Ce Worker est NOUVEAU et séparé de carburant-proxy : il ne touche ni aux comptes ni aux routes existantes.

export const FUELS = Object.freeze({ Gazole: 'gazole', SP95: 'sp95', SP98: 'sp98', E10: 'e10', E85: 'e85', GPLc: 'gplc' });
export const DATASET = 'https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2';
export const DEFAULTS = Object.freeze({
  minStations: 5000, maxDropRatio: 0.1, maxRejectedRatio: 0.01, retain: 3,
  leaseMs: 10 * 60 * 1000, staleAfterMs: 24 * 3600 * 1000, maxPrice: 20,
  maxRadiusKm: 50, maxLimit: 100, fetchTimeoutMs: 60000,
  allowedOrigins: ['https://emilienzabu.github.io', 'https://carburantradar.fr', 'https://www.carburantradar.fr']
});
const VERSION_RE = /^[\w.-]{1,100}$/;

export class SnapshotError extends Error {
  constructor(code, detail) { super(detail ? `${code}: ${detail}` : code); this.code = code; }
}

const finite = (n) => typeof n === 'number' && Number.isFinite(n);
const str = (v) => (v === undefined || v === null ? '' : String(v));
const isoOrNull = (v) => (typeof v === 'string' && /^\d{4}-\d\d-\d\d/.test(v) && Number.isFinite(Date.parse(v)) ? v : null);

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function haversineKm(a, b) {
  const rad = Math.PI / 180, dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(x)));
}

function coord(row) {
  const lat = row?.geom?.lat !== undefined ? Number(row.geom.lat) : Number(row?.latitude) / 100000;
  const lon = row?.geom?.lon !== undefined ? Number(row.geom.lon) : Number(row?.longitude) / 100000;
  if (!finite(lat) || !finite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180 || (lat === 0 && lon === 0)) return null;
  return { lat, lon };
}

// Normalisation TOLÉRANTE : une ligne invalide est mise de côté et comptée (jamais silencieusement),
// elle ne fait plus échouer tout le snapshot. Un identifiant dupliqué reste fatal (intégrité de la source).
export function normalizeRows(rows, { maxPrice = DEFAULTS.maxPrice } = {}) {
  if (!Array.isArray(rows)) throw new SnapshotError('invalid_dataset');
  const ids = new Set(), stations = [], rejected = [];
  let invalidPrices = 0;
  for (const row of rows) {
    const rawId = row && typeof row === 'object' ? row.id : undefined;
    if (rawId === undefined || rawId === null || String(rawId).trim() === '') { rejected.push({ id: null, reason: 'missing_id' }); continue; }
    const id = String(rawId);
    if (ids.has(id)) throw new SnapshotError('duplicate_id', id);
    ids.add(id);
    const c = coord(row);
    if (!c) { rejected.push({ id, reason: 'invalid_coordinates' }); continue; }
    const prices = {};
    for (const [fuel, key] of Object.entries(FUELS)) {
      const raw = row[`${key}_prix`];
      if (raw === undefined || raw === null || raw === '') { prices[fuel] = null; continue; }
      const p = Number(raw);
      if (!finite(p) || p <= 0 || p > maxPrice) { invalidPrices++; prices[fuel] = null; continue; }
      prices[fuel] = [p, isoOrNull(row[`${key}_maj`])];
    }
    stations.push({ id, lat: c.lat, lon: c.lon, address: str(row.adresse), city: str(row.ville), postalCode: str(row.cp), prices });
  }
  stations.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return { stations, rejected, invalidPrices };
}

export async function buildSnapshot({ stations, rejected = [], invalidPrices = 0, sourceTotal, createdAt }) {
  if (!Number.isFinite(Date.parse(createdAt))) throw new SnapshotError('invalid_timestamp');
  const contentHash = await sha256Hex(JSON.stringify(stations));
  const stamp = createdAt.replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  const version = `${stamp}-${contentHash.slice(0, 8)}`;
  const byReason = {};
  for (const r of rejected) byReason[r.reason] = (byReason[r.reason] || 0) + 1;
  const body = JSON.stringify({ schemaVersion: 2, version, createdAt, source: { total: sourceTotal }, rejected: { count: rejected.length, byReason, invalidPrices }, stations });
  const sha256 = await sha256Hex(body);
  return { version, createdAt, body, sha256, stationCount: stations.length, rejectedCount: rejected.length, sourceTotal };
}

// ---------- Stockage ----------
export function r2Objects(bucket) {
  return {
    // R2 renvoie null quand la condition onlyIf échoue : création seulement si l'objet n'existe pas.
    async putIfAbsent(key, body) {
      const r = await bucket.put(key, body, { onlyIf: { etagDoesNotMatch: '*' }, httpMetadata: { contentType: 'application/json' } });
      return r !== null && r !== undefined;
    },
    async get(key) { const o = await bucket.get(key); return o ? await o.text() : null; },
    async delete(key) { await bucket.delete(key); }
  };
}
const objectKey = (version) => `france/snapshots/${version}.json`;

const ACTIVE_SQL = `SELECT a.version, a.revision, a.switched_at, v.created_at, v.sha256, v.station_count, v.rejected_count, v.source_total, v.status
  FROM snapshot_active a JOIN snapshot_versions v ON v.version = a.version WHERE a.id = 1`;
export const getActive = (db) => db.prepare(ACTIVE_SQL).first();
export const getVersion = (db, version) => db.prepare('SELECT * FROM snapshot_versions WHERE version = ?').bind(version).first();

export async function logEvent(db, kind, version, detail, at) {
  try { await db.prepare('INSERT INTO snapshot_events(at, kind, version, detail) VALUES(?,?,?,?)').bind(at, kind, version ?? null, detail ? String(detail).slice(0, 300) : null).run(); } catch { /* journal au mieux, jamais bloquant */ }
}

export async function acquireLease(db, holder, now, ttlMs) {
  const r = await db.prepare(`INSERT INTO snapshot_lock(id, holder, expires_at) VALUES(1, ?, ?)
    ON CONFLICT(id) DO UPDATE SET holder = excluded.holder, expires_at = excluded.expires_at WHERE snapshot_lock.expires_at <= ?`).bind(holder, now + ttlMs, now).run();
  return r.meta.changes === 1;
}
export async function releaseLease(db, holder) {
  await db.prepare('UPDATE snapshot_lock SET expires_at = 0 WHERE id = 1 AND holder = ?').bind(holder).run();
}

// Bascule du pointeur : comparaison-et-échange sur la révision. Renvoie false en cas de conflit ou de cible refusée.
export async function activate(db, version, expectedRevision, now) {
  try {
    const r = expectedRevision === null
      ? await db.prepare('INSERT INTO snapshot_active(id, version, revision, switched_at) VALUES(1, ?, 1, ?)').bind(version, now).run()
      : await db.prepare('UPDATE snapshot_active SET version = ?, revision = revision + 1, switched_at = ? WHERE id = 1 AND revision = ?').bind(version, now, expectedRevision).run();
    return r.meta.changes === 1;
  } catch (e) {
    if (/UNIQUE|PRIMARY|constraint/i.test(String(e?.message)) && !/snapshot_target_invalid|snapshot_revision_step/.test(String(e?.message))) return false;
    throw e;
  }
}

async function prune(db, objects, retain) {
  const { results } = await db.prepare(`SELECT version FROM snapshot_versions WHERE status <> 'pruned' AND version NOT IN (SELECT version FROM snapshot_active)
    ORDER BY created_at DESC, version DESC`).all();
  for (const { version } of results.slice(Math.max(0, retain - 1))) {
    try { await db.prepare("UPDATE snapshot_versions SET status = 'pruned' WHERE version = ?").bind(version).run(); await objects.delete(objectKey(version)); } catch { /* sera retenté au prochain passage */ }
  }
}

// ---------- Lecture d'une version (intégrité vérifiée, mise en cache par isolat) ----------
const memo = new Map();
export function clearCache() { memo.clear(); }
export async function loadSnapshot(objects, meta) {
  const key = `${meta.version}|${meta.sha256}`;
  if (memo.has(key)) return memo.get(key);
  const body = await objects.get(objectKey(meta.version));
  if (typeof body !== 'string') throw new SnapshotError('snapshot_missing');
  if ((await sha256Hex(body)) !== meta.sha256) throw new SnapshotError('integrity_failure');
  let decoded;
  try { decoded = JSON.parse(body); } catch { throw new SnapshotError('corrupt_snapshot'); }
  if (decoded.version !== meta.version || !Array.isArray(decoded.stations) || decoded.stations.length !== meta.station_count) throw new SnapshotError('integrity_failure');
  if (memo.size >= 2) memo.delete(memo.keys().next().value);
  memo.set(key, decoded);
  return decoded;
}

export function queryStations(snapshot, { lat, lon, radiusKm, fuel, offset, limit }) {
  const origin = { lat, lon }, eligible = [];
  const dLat = radiusKm / 111, dLon = radiusKm / (111 * Math.max(0.01, Math.cos(lat * Math.PI / 180)));
  for (const s of snapshot.stations) {
    const p = s.prices[fuel];
    if (!p || Math.abs(s.lat - lat) > dLat || Math.abs(s.lon - lon) > dLon) continue;
    const km = haversineKm(origin, s);
    if (km <= radiusKm) eligible.push({ id: s.id, lat: s.lat, lon: s.lon, price: p[0], updatedAt: p[1], distanceIndicativeKm: Math.round(km * 1000) / 1000, address: s.address, city: s.city, postalCode: s.postalCode });
  }
  eligible.sort((a, b) => a.distanceIndicativeKm - b.distanceIndicativeKm || (a.id < b.id ? -1 : 1));
  return { total: eligible.length, results: eligible.slice(offset, offset + limit), nextCursor: offset + limit < eligible.length ? offset + limit : null };
}

// ---------- Rafraîchissement ----------
async function getJson(fetchFn, url, timeoutMs) {
  const res = await fetchFn(url, { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(timeoutMs) });
  if (!res || !res.ok) throw new SnapshotError('source_http', String(res && res.status));
  try { return await res.json(); } catch { throw new SnapshotError('source_invalid_json'); }
}
async function fetchTotal(fetchFn, timeoutMs) {
  const j = await getJson(fetchFn, `${DATASET}/records?limit=1`, timeoutMs);
  if (!j || !Number.isInteger(j.total_count) || j.total_count < 0) throw new SnapshotError('source_invalid_total');
  return j.total_count;
}

// Exhaustivité : trois mesures (total avant, export complet, total après) doivent être identiques.
// Un export complet en UNE requête évite la pagination par offset (plafond ODS, limite de sous-requêtes Workers).
export async function refreshSnapshot({ db, objects, fetchFn, now = Date.now, config = {}, holder = 'refresh' }) {
  const cfg = { ...DEFAULTS, ...config };
  const t0 = now();
  let leased = false;
  try {
    leased = await acquireLease(db, holder, t0, cfg.leaseMs);
    if (!leased) return { status: 'skipped', reason: 'lease_unavailable' };
    const before = await fetchTotal(fetchFn, cfg.fetchTimeoutMs);
    const rows = await getJson(fetchFn, `${DATASET}/exports/json`, cfg.fetchTimeoutMs);
    const after = await fetchTotal(fetchFn, cfg.fetchTimeoutMs);
    if (before !== after) throw new SnapshotError('source_total_changed');
    if (!Array.isArray(rows) || rows.length !== before) throw new SnapshotError('export_count_mismatch');
    const { stations, rejected, invalidPrices } = normalizeRows(rows, { maxPrice: cfg.maxPrice });
    if (stations.length < cfg.minStations) throw new SnapshotError('too_few_stations');
    if (rejected.length > rows.length * cfg.maxRejectedRatio) throw new SnapshotError('too_many_rejected');
    const active = await getActive(db);
    if (active && stations.length < active.station_count * (1 - cfg.maxDropRatio)) throw new SnapshotError('suspicious_station_drop');
    const createdAt = new Date(now()).toISOString();
    if (active && Date.parse(createdAt) < Date.parse(active.created_at)) throw new SnapshotError('stale_candidate');
    const snap = await buildSnapshot({ stations, rejected, invalidPrices, sourceTotal: before, createdAt });
    if (!(await objects.putIfAbsent(objectKey(snap.version), snap.body))) throw new SnapshotError('version_exists');
    const back = await objects.get(objectKey(snap.version));
    if (typeof back !== 'string' || (await sha256Hex(back)) !== snap.sha256) throw new SnapshotError('readback_mismatch');
    await db.prepare('INSERT INTO snapshot_versions(version, created_at, sha256, station_count, rejected_count, source_total) VALUES(?,?,?,?,?,?)')
      .bind(snap.version, snap.createdAt, snap.sha256, snap.stationCount, snap.rejectedCount, snap.sourceTotal).run();
    if (!(await activate(db, snap.version, active ? active.revision : null, now()))) throw new SnapshotError('publication_conflict');
    await prune(db, objects, cfg.retain);
    await logEvent(db, 'refresh_success', snap.version, `${snap.stationCount} stations, ${snap.rejectedCount} rejetées`, now());
    return { status: 'published', version: snap.version, count: snap.stationCount, rejected: snap.rejectedCount, checksum: snap.sha256 };
  } catch (e) {
    const code = e instanceof SnapshotError ? e.code : 'unexpected_error';
    if (leased) await logEvent(db, 'refresh_failed', null, e instanceof SnapshotError ? e.message : code, now());
    return { status: 'failed', reason: code, keptPrevious: true };
  } finally {
    if (leased) { try { await releaseLease(db, holder); } catch { /* le bail expirera seul */ } }
  }
}

// Retour arrière : repointe vers une version déjà publiée et conservée, après contrôle d'intégrité.
export async function rollbackSnapshot({ db, objects, version, now = Date.now }) {
  if (typeof version !== 'string' || !VERSION_RE.test(version)) throw new SnapshotError('invalid_version');
  const active = await getActive(db);
  if (!active) throw new SnapshotError('not_ready');
  if (active.version === version) throw new SnapshotError('already_active');
  const target = await getVersion(db, version);
  if (!target || target.status !== 'activated') throw new SnapshotError('version_not_restorable');
  await loadSnapshot(objects, target);
  if (!(await activate(db, version, active.revision, now()))) throw new SnapshotError('publication_conflict');
  await logEvent(db, 'rollback', version, `depuis ${active.version}`, now());
  return { status: 'rolled_back', from: active.version, to: version };
}

// ---------- HTTP ----------
function corsHeaders(request, cfg) {
  const origin = request.headers.get('Origin');
  const h = { Vary: 'Origin' };
  if (origin && cfg.allowedOrigins.includes(origin)) {
    h['Access-Control-Allow-Origin'] = origin;
    h['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS';
    h['Access-Control-Allow-Headers'] = 'Authorization, Content-Type';
    h['Access-Control-Max-Age'] = '600';
  }
  return h;
}
function json(body, status, request, cfg) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...corsHeaders(request, cfg) } });
}
export function constantTimeEqual(a, b) {
  const x = new TextEncoder().encode(str(a)), y = new TextEncoder().encode(str(b));
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}
export function parseQuery(url, cfg = DEFAULTS) {
  const p = new URL(url).searchParams;
  const num = (k) => (p.has(k) && p.get(k).trim() !== '' ? Number(p.get(k)) : NaN);
  const lat = num('lat'), lon = num('lon'), radiusKm = num('dist'), fuel = p.get('fuel');
  const offset = p.has('cursor') ? num('cursor') : 0, limit = p.has('limit') ? num('limit') : cfg.maxLimit;
  const snapshot = p.get('snapshot');
  if (!finite(lat) || Math.abs(lat) > 90 || !finite(lon) || Math.abs(lon) > 180 || !finite(radiusKm) || radiusKm <= 0 || radiusKm > cfg.maxRadiusKm
    || !Object.prototype.hasOwnProperty.call(FUELS, fuel || '') || !Number.isInteger(offset) || offset < 0 || !Number.isInteger(limit) || limit < 1 || limit > cfg.maxLimit
    || (snapshot !== null && !VERSION_RE.test(snapshot))) throw new SnapshotError('invalid_parameters');
  return { lat, lon, radiusKm, fuel, offset, limit, snapshot };
}

export async function handleRequest(request, { db, objects, env = {}, now = Date.now, fetchFn = fetch, config = {} }) {
  const cfg = { ...DEFAULTS, ...config, allowedOrigins: env.ALLOWED_ORIGINS ? env.ALLOWED_ORIGINS.split(',').map((s) => s.trim()).filter(Boolean) : (config.allowedOrigins || DEFAULTS.allowedOrigins) };
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(request, cfg) });
  try {
    if (url.pathname === '/v2/status' && request.method === 'GET') {
      const a = await getActive(db);
      const last = await db.prepare('SELECT at, kind FROM snapshot_events ORDER BY id DESC LIMIT 1').first();
      const ageMs = a ? Math.max(0, now() - Date.parse(a.created_at)) : null;
      return json({ schemaVersion: 2, ready: Boolean(a), active: a && { version: a.version, createdAt: a.created_at, count: a.station_count, checksum: a.sha256, ageMs, stale: ageMs > cfg.staleAfterMs }, lastEvent: last || null }, 200, request, cfg);
    }
    if (url.pathname === '/v2/france' && request.method === 'GET') {
      let q;
      try { q = parseQuery(request.url, cfg); } catch { return json({ error: 'invalid_parameters' }, 400, request, cfg); }
      const active = await getActive(db);
      if (!active) return json({ error: 'not_ready' }, 503, request, cfg);
      let target = active;
      if (q.snapshot && q.snapshot !== active.version) {
        target = await getVersion(db, q.snapshot);
        if (!target || target.status !== 'activated') return json({ error: 'snapshot_unavailable' }, 404, request, cfg);
      }
      const snap = await loadSnapshot(objects, target);
      const page = queryStations(snap, q);
      const ageMs = Math.max(0, now() - Date.parse(target.created_at));
      return json({ schemaVersion: 2, snapshot: target.version, checksum: target.sha256, createdAt: target.created_at, complete: true, ...page, stale: ageMs > cfg.staleAfterMs, ageMs }, 200, request, cfg);
    }
    if (url.pathname.startsWith('/admin/snapshot/') && request.method === 'POST') {
      if (!env.RADAR_ADMIN_SECRET) return json({ error: 'admin_disabled' }, 503, request, cfg);
      const auth = request.headers.get('Authorization') || '';
      if (!auth.startsWith('Bearer ') || !constantTimeEqual(auth.slice(7), env.RADAR_ADMIN_SECRET)) return json({ error: 'unauthorized' }, 401, request, cfg);
      if (url.pathname === '/admin/snapshot/refresh') return json(await refreshSnapshot({ db, objects, fetchFn, now, config: cfg, holder: 'manual' }), 200, request, cfg);
      if (url.pathname === '/admin/snapshot/rollback') {
        let body; try { body = await request.json(); } catch { return json({ error: 'invalid_body' }, 400, request, cfg); }
        try { return json(await rollbackSnapshot({ db, objects, version: body?.version, now }), 200, request, cfg); }
        catch (e) { if (e instanceof SnapshotError) return json({ error: e.code }, e.code === 'publication_conflict' ? 409 : 422, request, cfg); throw e; }
      }
    }
    return json({ error: 'not_found' }, 404, request, cfg);
  } catch (e) {
    return json({ error: e instanceof SnapshotError ? e.code : 'internal_error' }, 503, request, cfg);
  }
}

export default {
  async fetch(request, env) { return handleRequest(request, { db: env.DB_RADAR, objects: r2Objects(env.SNAPSHOTS), env }); },
  async scheduled(event, env, ctx) { ctx.waitUntil(refreshSnapshot({ db: env.DB_RADAR, objects: r2Objects(env.SNAPSHOTS), fetchFn: fetch, holder: 'cron' })); }
};
