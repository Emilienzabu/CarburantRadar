// CarburantRadar radar V2 — synchronisation du garage par compte (serveur + adaptateur client).
// CANDIDAT : NON DÉPLOYÉ. Fichier unique sans import (ESM).
// IMPORTANT : l'authentification n'est PAS implémentée ici. Le format réel des sessions de carburant-proxy
// (KV USERS) est INCONNU (code du Worker non disponible). Le module reçoit donc une fonction `authenticate`
// injectée ; sans elle, toutes les routes répondent 501. Voir docs/PROXY_WORKER_CHANGES.md.
// Contrat : authenticate(request) -> { userId: string } | null. userId vient du serveur, jamais du corps.

const FUELS = ['Gazole', 'SP95', 'SP98', 'E10', 'E85', 'GPLc'];
const ICONS = ['citadine_bleue', 'citadine_rouge', 'berline', 'suv', 'break', 'sportive', 'cabriolet', 'pickup', 'utilitaire', 'ancienne', 'tacot', 'brouette', 'fusee', 'kart', 'tracteur', 'licorne'];
const MAX_VEHICLES = 30, MAX_BODY = 32768;
const USER_RE = /^[\w:.@+-]{1,128}$/;
const isObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
const validId = (x) => typeof x === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(x);
function fail(m) { throw new TypeError(m); }

// Copie fidèle de garage.js (prototype V32). Un test différentiel vérifie l'équivalence.
export function validateVehicle(v) {
  if (!isObj(v)) fail('vehicle must be an object');
  if (!validId(v.id)) fail('invalid vehicle id');
  if (typeof v.name !== 'string' || !v.name.trim() || v.name.trim().length > 60) fail('invalid name');
  if (!FUELS.includes(v.fuel)) fail('invalid fuel');
  if (typeof v.consumption !== 'number' || !Number.isFinite(v.consumption) || v.consumption <= 0 || v.consumption > 100) fail('invalid consumption');
  if (typeof v.tankCapacity !== 'number' || !Number.isFinite(v.tankCapacity) || v.tankCapacity <= 0 || v.tankCapacity > 2000) fail('invalid tank capacity');
  if (!ICONS.includes(v.illustration)) fail('invalid illustration');
  if (!Number.isInteger(v.fillPercent) || v.fillPercent < 1 || v.fillPercent > 100) fail('invalid fill percentage');
  return { id: v.id, name: v.name.trim(), fuel: v.fuel, consumption: v.consumption, tankCapacity: v.tankCapacity, illustration: v.illustration, fillPercent: v.fillPercent };
}
export function validateGarage(g) {
  if (!isObj(g) || !Array.isArray(g.vehicles) || g.vehicles.length > MAX_VEHICLES) fail('invalid garage');
  if (!Number.isSafeInteger(g.revision) || g.revision < 0) fail('invalid revision');
  const vehicles = g.vehicles.map(validateVehicle);
  if (new Set(vehicles.map((v) => v.id)).size !== vehicles.length) fail('duplicate vehicle id');
  if (vehicles.length === 0 ? g.defaultVehicleId !== null : !vehicles.some((v) => v.id === g.defaultVehicleId)) fail('invalid default vehicle');
  return { schemaVersion: 1, revision: g.revision, defaultVehicleId: g.defaultVehicleId, vehicles };
}
export const emptyGarage = () => ({ schemaVersion: 1, revision: 0, defaultVehicleId: null, vehicles: [] });

function corsHeaders(request, allowedOrigins) {
  const origin = request.headers.get('Origin');
  const h = { Vary: 'Origin' };
  if (origin && allowedOrigins.includes(origin)) {
    h['Access-Control-Allow-Origin'] = origin;
    h['Access-Control-Allow-Methods'] = 'GET, PUT, OPTIONS';
    h['Access-Control-Allow-Headers'] = 'Authorization, Content-Type';
    h['Access-Control-Max-Age'] = '600';
  }
  return h;
}
const reply = (body, status, request, origins, extra = {}) => new Response(body === null ? null : JSON.stringify(body), {
  status, headers: { ...(body === null ? {} : { 'Content-Type': 'application/json; charset=utf-8' }), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...corsHeaders(request, origins), ...extra }
});

async function readGarage(db, userId) {
  const row = await db.prepare('SELECT revision, body FROM garages WHERE user_id = ?').bind(userId).first();
  if (!row) return emptyGarage();
  const garage = validateGarage(JSON.parse(row.body));
  if (garage.revision !== row.revision) fail('corrupt garage');
  return garage;
}

export async function handleGarage(request, { db, authenticate, now = Date.now, allowedOrigins = [] } = {}) {
  if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders(request, allowedOrigins) });
  if (typeof authenticate !== 'function') return reply({ error: 'garage_auth_not_configured' }, 501, request, allowedOrigins);
  let user = null;
  try { user = await authenticate(request); } catch { user = null; }
  if (!user || typeof user.userId !== 'string' || !USER_RE.test(user.userId)) return reply({ error: 'unauthorized' }, 401, request, allowedOrigins);
  const userId = user.userId;
  try {
    if (request.method === 'GET') {
      const garage = await readGarage(db, userId);
      return reply({ revision: garage.revision, garage }, 200, request, allowedOrigins, { ETag: `"${garage.revision}"` });
    }
    if (request.method === 'PUT') {
      if (!/^application\/json\b/i.test(request.headers.get('Content-Type') || '')) return reply({ error: 'unsupported_media_type' }, 415, request, allowedOrigins);
      const declared = Number(request.headers.get('Content-Length'));
      if (Number.isFinite(declared) && declared > MAX_BODY) return reply({ error: 'payload_too_large' }, 413, request, allowedOrigins);
      const text = await request.text();
      if (text.length > MAX_BODY) return reply({ error: 'payload_too_large' }, 413, request, allowedOrigins);
      let input; try { input = JSON.parse(text); } catch { return reply({ error: 'invalid_json' }, 400, request, allowedOrigins); }
      if (!isObj(input) || !Number.isSafeInteger(input.baseRevision) || input.baseRevision < 0) return reply({ error: 'invalid_base_revision' }, 422, request, allowedOrigins);
      let candidate;
      try { candidate = validateGarage(input.garage); } catch (e) { return reply({ error: 'invalid_garage', reason: e.message }, 422, request, allowedOrigins); }
      // Même règle que prepareSave du prototype : plusieurs éditions hors ligne = une seule révision serveur.
      if (candidate.revision <= input.baseRevision) return reply({ error: 'stale_local_revision' }, 422, request, allowedOrigins);
      const next = { ...candidate, revision: input.baseRevision + 1 };
      const body = JSON.stringify(next);
      const t = now();
      const r = input.baseRevision === 0
        ? await db.prepare('INSERT INTO garages(user_id, revision, body, updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO NOTHING').bind(userId, next.revision, body, t).run()
        : await db.prepare('UPDATE garages SET revision = ?, body = ?, updated_at = ? WHERE user_id = ? AND revision = ?').bind(next.revision, body, t, userId, input.baseRevision).run();
      if (r.meta.changes === 1) return reply({ status: 'saved', revision: next.revision, garage: next }, 200, request, allowedOrigins, { ETag: `"${next.revision}"` });
      const server = await readGarage(db, userId);
      return reply({ error: 'conflict', revision: server.revision, server: { revision: server.revision, garage: server } }, 409, request, allowedOrigins);
    }
    return reply({ error: 'method_not_allowed' }, 405, request, allowedOrigins, { Allow: 'GET, PUT, OPTIONS' });
  } catch {
    return reply({ error: 'internal_error' }, 500, request, allowedOrigins);
  }
}

// Effacement d'un compte : à appeler par le flux de suppression de compte (aucune route publique).
export async function deleteGarageForUser(db, userId) {
  if (typeof userId !== 'string' || !USER_RE.test(userId)) throw new TypeError('invalid user id');
  const r = await db.prepare('DELETE FROM garages WHERE user_id = ?').bind(userId).run();
  return r.meta.changes;
}

// Adaptateur client compatible avec synchronizeGarage() du prototype (garage-sync.js).
export function createHttpGarageAdapter({ fetchFn, baseUrl, getToken }) {
  if (typeof fetchFn !== 'function' || typeof getToken !== 'function' || typeof baseUrl !== 'string') throw new TypeError('invalid adapter config');
  const headers = async (extra = {}) => ({ Authorization: `Bearer ${await getToken()}`, ...extra });
  return {
    async read() {
      const res = await fetchFn(baseUrl, { method: 'GET', headers: await headers() });
      if (!res.ok) throw new Error(`garage_http_${res.status}`);
      return validateGarage((await res.json()).garage);
    },
    async compareAndSwap(expectedRevision, next) {
      const res = await fetchFn(baseUrl, { method: 'PUT', headers: await headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ baseRevision: expectedRevision, garage: next }) });
      if (res.status === 409) return { status: 'conflict', server: validateGarage((await res.json()).server.garage) };
      if (!res.ok) throw new Error(`garage_http_${res.status}`);
      return { status: 'saved', server: validateGarage((await res.json()).garage) };
    }
  };
}
