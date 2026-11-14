import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { handleGarage, validateGarage, createHttpGarageAdapter, deleteGarageForUser, emptyGarage } from '../garage-api.mjs';
import { makeD1, req } from './helpers.mjs';

const require = createRequire(import.meta.url);
const proto = require('../../prototype/garage.js');
const { synchronizeGarage } = require('../../prototype/garage-sync.js');

const ORIGINS = ['https://carburantradar.fr'];
const vehicle = (id = 'v1', extra = {}) => ({ id, name: 'Clio', fuel: 'Gazole', consumption: 5.5, tankCapacity: 45, illustration: 'citadine_bleue', fillPercent: 80, ...extra });
const garage = (revision, vehicles = [vehicle()], def) => ({ schemaVersion: 1, revision, defaultVehicleId: def ?? (vehicles[0]?.id ?? null), vehicles });
function setup() {
  const db = makeD1('0002_garage.sql');
  const tokens = { 'tok-a': 'user-a', 'tok-b': 'user-b', 'tok-e': 'user with spaces' };
  const authenticate = async (request) => {
    const t = (request.headers.get('Authorization') || '').replace('Bearer ', '');
    return tokens[t] ? { userId: tokens[t] } : null;
  };
  let t = 1000;
  const call = (method, token, body, headers = {}) => handleGarage(req('/v2/garage', {
    method, headers: { ...(token ? { Authorization: 'Bearer ' + token } : {}), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...headers },
    body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body)
  }), { db, authenticate, now: () => t++, allowedOrigins: ORIGINS });
  const json = async (p) => { const r = await p; return { status: r.status, body: r.status === 204 ? null : await r.json(), headers: r.headers }; };
  return { db, call, json, authenticate };
}

test('garage : authentification absente => 501 ; jeton invalide => 401 ; userId invalide => 401', async () => {
  const db = makeD1('0002_garage.sql');
  const r = await handleGarage(req('/v2/garage'), { db });
  assert.equal(r.status, 501); assert.equal((await r.json()).error, 'garage_auth_not_configured');
  const s = setup();
  assert.equal((await s.json(s.call('GET', undefined))).status, 401);
  assert.equal((await s.json(s.call('GET', 'faux'))).status, 401);
  const weird = await handleGarage(req('/v2/garage', { headers: { Authorization: 'x' } }), { db, authenticate: async () => ({ userId: "x'; DROP TABLE garages;--" }) });
  assert.equal(weird.status, 401);
  const throwing = await handleGarage(req('/v2/garage'), { db, authenticate: async () => { throw new Error('KV down'); } });
  assert.equal(throwing.status, 401);
});
test('garage : GET sans ligne => garage vide révision 0 ; PUT initial puis relecture', async () => {
  const s = setup();
  const g0 = await s.json(s.call('GET', 'tok-a'));
  assert.equal(g0.status, 200); assert.deepEqual(g0.body.garage, emptyGarage()); assert.equal(g0.headers.get('ETag'), '"0"');
  const put = await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  assert.equal(put.status, 200); assert.equal(put.body.status, 'saved'); assert.equal(put.body.revision, 1);
  const g1 = await s.json(s.call('GET', 'tok-a'));
  assert.equal(g1.body.revision, 1); assert.equal(g1.body.garage.vehicles[0].name, 'Clio');
});
test('garage : isolation entre comptes — le corps ne peut pas désigner un autre compte', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1, [vehicle('a1', { name: 'Voiture A' })]) }));
  const b = await s.json(s.call('GET', 'tok-b'));
  assert.equal(b.body.revision, 0); assert.deepEqual(b.body.garage.vehicles, []);
  // tentative d'injection d'un userId dans le corps : ignoré, écrit pour le compte authentifié uniquement
  await s.json(s.call('PUT', 'tok-b', { baseRevision: 0, userId: 'user-a', user_id: 'user-a', garage: garage(1, [vehicle('b1', { name: 'Voiture B' })]) }));
  const rows = s.db.raw.prepare('SELECT user_id, revision FROM garages ORDER BY user_id').all();
  assert.deepEqual(rows.map((r) => r.user_id), ['user-a', 'user-b']);
  assert.equal((await s.json(s.call('GET', 'tok-a'))).body.garage.vehicles[0].name, 'Voiture A');
});
test('garage : conflit => 409 avec l’état serveur, aucune écriture silencieuse', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 1, garage: garage(2, [vehicle('v1'), vehicle('v2', { name: 'Twingo' })]) }));
  const stale = await s.json(s.call('PUT', 'tok-a', { baseRevision: 1, garage: garage(2, [vehicle('v9', { name: 'Autre appareil' })]) }));
  assert.equal(stale.status, 409); assert.equal(stale.body.error, 'conflict'); assert.equal(stale.body.server.revision, 2);
  assert.equal(stale.body.server.garage.vehicles.length, 2);
  assert.equal((await s.json(s.call('GET', 'tok-a'))).body.garage.vehicles.length, 2);
  const onNew = await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  assert.equal(onNew.status, 409, 'base 0 alors qu’une ligne existe');
});
test('garage : 20 écritures simultanées sur la même base => une seule gagne', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  const out = await Promise.all(Array.from({ length: 20 }, (_, i) => s.json(s.call('PUT', 'tok-a', { baseRevision: 1, garage: garage(2, [vehicle('x' + i, { name: 'N' + i })]) }))));
  assert.equal(out.filter((o) => o.status === 200).length, 1);
  assert.equal(out.filter((o) => o.status === 409).length, 19);
  assert.equal(s.db.raw.prepare('SELECT revision FROM garages').get().revision, 2);
});
test('garage : plusieurs éditions hors ligne = une seule révision serveur (règle prepareSave)', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  const r = await s.json(s.call('PUT', 'tok-a', { baseRevision: 1, garage: garage(5, [vehicle('v1', { name: 'Modifié' })]) }));
  assert.equal(r.status, 200); assert.equal(r.body.revision, 2); assert.equal(r.body.garage.revision, 2);
  const stale = await s.json(s.call('PUT', 'tok-a', { baseRevision: 2, garage: garage(2) }));
  assert.equal(stale.status, 422); assert.equal(stale.body.error, 'stale_local_revision');
});
test('garage : entrées invalides => 400/413/415/422, rien d’écrit', async () => {
  const s = setup();
  const cases = [
    ['json cassé', '{pas', 400], ['pas un objet', '[]', 422], ['baseRevision manquant', { garage: garage(1) }, 422], ['baseRevision négatif', { baseRevision: -1, garage: garage(1) }, 422],
    ['baseRevision flottant', { baseRevision: 0.5, garage: garage(1) }, 422], ['garage absent', { baseRevision: 0 }, 422],
    ['carburant inconnu', { baseRevision: 0, garage: garage(1, [vehicle('v1', { fuel: 'Kérosène' })]) }, 422],
    ['conso négative', { baseRevision: 0, garage: garage(1, [vehicle('v1', { consumption: -1 })]) }, 422],
    ['id avec espace', { baseRevision: 0, garage: garage(1, [vehicle('a b')]) }, 422],
    ['défaut inexistant', { baseRevision: 0, garage: garage(1, [vehicle('v1')], 'zz') }, 422],
    ['31 véhicules', { baseRevision: 0, garage: garage(1, Array.from({ length: 31 }, (_, i) => vehicle('v' + i))) }, 422],
    ['trop gros', JSON.stringify({ baseRevision: 0, garage: garage(1), pad: 'x'.repeat(40000) }), 413]
  ];
  for (const [name, body, status] of cases) { const r = await s.json(s.call('PUT', 'tok-a', body)); assert.equal(r.status, status, name); }
  assert.equal((await s.json(handleGarage(req('/v2/garage', { method: 'PUT', headers: { Authorization: 'Bearer tok-a', 'Content-Type': 'text/plain' }, body: '{}' }), { db: s.db, authenticate: s.authenticate }))).status, 415);
  assert.equal(s.db.raw.prepare('SELECT count(*) n FROM garages').get().n, 0);
  assert.equal((await s.json(s.call('DELETE', 'tok-a'))).status, 405);
});
test('garage : CORS (origine autorisée seulement) et préflight', async () => {
  const s = setup();
  const pre = await s.call('OPTIONS', undefined, undefined, { Origin: 'https://carburantradar.fr' });
  assert.equal(pre.status, 204); assert.equal(pre.headers.get('Access-Control-Allow-Origin'), 'https://carburantradar.fr');
  const ko = await s.call('GET', 'tok-a', undefined, { Origin: 'https://evil.example' });
  assert.equal(ko.headers.get('Access-Control-Allow-Origin'), null);
});
test('garage : ligne corrompue en base => 500 contrôlé, jamais de données invalides renvoyées', async () => {
  const s = setup();
  s.db.raw.prepare("INSERT INTO garages(user_id, revision, body, updated_at) VALUES('user-a', 1, '{\"vehicles\":[{}]}', 1)").run();
  const r = await s.json(s.call('GET', 'tok-a'));
  assert.equal(r.status, 500); assert.equal(r.body.error, 'internal_error');
});
test('schéma garage : la révision ne peut ni reculer ni sauter, le compte ne peut pas changer', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  assert.throws(() => s.db.raw.exec("UPDATE garages SET revision = 3"), /garage_revision_step/);
  assert.throws(() => s.db.raw.exec("UPDATE garages SET revision = 1"), /garage_revision_step/);
  assert.throws(() => s.db.raw.exec("UPDATE garages SET user_id = 'autre', revision = 2"), /garage_revision_step/);
});
test('garage : effacement de compte (helper) supprime uniquement ce compte', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1) }));
  await s.json(s.call('PUT', 'tok-b', { baseRevision: 0, garage: garage(1) }));
  assert.equal(await deleteGarageForUser(s.db, 'user-a'), 1);
  assert.equal((await s.json(s.call('GET', 'tok-b'))).body.revision, 1);
  await assert.rejects(deleteGarageForUser(s.db, "x' OR '1'='1"), TypeError);
});

// ---------- équivalence avec le prototype ----------
test('validateGarage (serveur) == garage.js (prototype) sur 3000 entrées mutées', () => {
  let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  const junk = [undefined, null, '', 'x', 0, -1, 1.5, NaN, Infinity, 1e9, 80, 5.5, [], {}, true, 'Gazole', 'Kérosène', 'citadine_bleue', 'v1', 'a b', 'x'.repeat(70)];
  const fields = ['id', 'name', 'fuel', 'consumption', 'tankCapacity', 'illustration', 'fillPercent'];
  let accepted = 0, rejected = 0;
  for (let i = 0; i < 3000; i++) {
    const g = JSON.parse(JSON.stringify(garage(Math.floor(rnd() * 4), [vehicle('v1'), vehicle('v2')], 'v1')));
    const m = Math.floor(rnd() * 4);
    for (let k = 0; k < m; k++) {
      const r = rnd();
      if (r < 0.6) { const arr = Array.isArray(g.vehicles) ? g.vehicles : []; const v = pick(arr); if (v && typeof v === 'object') v[pick(fields)] = pick(junk); }
      else if (r < 0.7) g.defaultVehicleId = pick(junk.concat(['v1', 'v2']));
      else if (r < 0.8) g.revision = pick(junk);
      else if (r < 0.9) g.vehicles = pick([[], Array.isArray(g.vehicles) && g.vehicles[0] ? [g.vehicles[0], g.vehicles[0]] : [], Array.isArray(g.vehicles) ? g.vehicles.slice(0, 1) : [], null, 'x']);
      else g.vehicles?.push?.(vehicle('v' + (3 + k)));
    }
    let a, b, ea, eb;
    try { a = proto.validateGarage(g); } catch (e) { ea = e.message; }
    try { b = validateGarage(g); } catch (e) { eb = e.message; }
    assert.deepEqual([a, ea], [b, eb], JSON.stringify(g));
    if (ea) rejected++; else accepted++;
  }
  assert.ok(accepted > 100 && rejected > 100, `accepted=${accepted} rejected=${rejected}`);
});

// ---------- bout en bout : client du prototype + serveur ----------
test('synchronizeGarage (prototype) via adaptateur HTTP : sauvegarde, rien à faire, conflit', async () => {
  const s = setup();
  const fetchFn = async (url, init) => s.call(init.method, (init.headers.Authorization || '').replace('Bearer ', ''), init.body === undefined ? undefined : init.body);
  const adapter = createHttpGarageAdapter({ fetchFn, baseUrl: 'https://radar.test/v2/garage', getToken: async () => 'tok-a' });
  const server0 = await adapter.read();
  assert.equal(server0.revision, 0);
  const local = proto.addVehicle(server0, vehicle('v1'));
  const saved = await synchronizeGarage({ local, baseRevision: 0, adapter });
  assert.equal(saved.status, 'saved'); assert.equal(saved.server.revision, 1);
  assert.equal((await synchronizeGarage({ local: saved.server, baseRevision: 1, adapter })).status, 'unchanged');
  // un autre appareil écrit entre-temps
  const other = createHttpGarageAdapter({ fetchFn, baseUrl: 'https://radar.test/v2/garage', getToken: async () => 'tok-a' });
  await synchronizeGarage({ local: proto.addVehicle(saved.server, vehicle('v2', { name: 'Autre' })), baseRevision: 1, adapter: other });
  const staleLocal = proto.editVehicle(saved.server, 'v1', { name: 'Renommée' });
  const res = await synchronizeGarage({ local: staleLocal, baseRevision: 1, adapter });
  assert.equal(res.status, 'conflict'); assert.equal(res.server.revision, 2);
  // appel direct de l'API avec une base périmée => conflit renvoyé par le serveur (pas seulement détecté côté client)
  const direct = await adapter.compareAndSwap(1, proto.editVehicle(saved.server, 'v1', { name: 'X' }));
  assert.equal(direct.status, 'conflict'); assert.equal(direct.server.vehicles.length, 2);
  assert.equal((await adapter.read()).vehicles.find((v) => v.id === 'v1').name, 'Clio');
});
test('adaptateur HTTP : erreurs réseau/serveur propagées, jamais de faux « saved »', async () => {
  const bad = (status) => createHttpGarageAdapter({ fetchFn: async () => new Response('{}', { status }), baseUrl: 'https://x/', getToken: async () => 't' });
  await assert.rejects(bad(500).read(), /garage_http_500/);
  await assert.rejects(bad(401).compareAndSwap(0, garage(1)), /garage_http_401/);
  assert.throws(() => createHttpGarageAdapter({}), TypeError);
});
test('garage : une mise à jour ne touche que la ligne du compte authentifié (deux comptes à la même révision)', async () => {
  const s = setup();
  await s.json(s.call('PUT', 'tok-a', { baseRevision: 0, garage: garage(1, [vehicle('a1', { name: 'A' })]) }));
  await s.json(s.call('PUT', 'tok-b', { baseRevision: 0, garage: garage(1, [vehicle('b1', { name: 'B' })]) }));
  const r = await s.json(s.call('PUT', 'tok-a', { baseRevision: 1, garage: garage(2, [vehicle('a1', { name: 'A2' })]) }));
  assert.equal(r.status, 200);
  const b = await s.json(s.call('GET', 'tok-b'));
  assert.equal(b.body.revision, 1); assert.equal(b.body.garage.vehicles[0].name, 'B');
});
