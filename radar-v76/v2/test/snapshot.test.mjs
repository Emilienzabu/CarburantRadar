import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeRows, buildSnapshot, sha256Hex, refreshSnapshot, handleRequest, rollbackSnapshot, activate, getActive,
  r2Objects, clearCache, constantTimeEqual, haversineKm, parseQuery, SnapshotError, FUELS
} from '../snapshot-worker.mjs';
import { makeD1, makeR2, makeRows, makeSource, req } from './helpers.mjs';

const T0 = Date.parse('2026-11-12T08:00:00Z');
function setup({ n = 300, seed = 1, config = {} } = {}) {
  clearCache();
  const db = makeD1('0001_snapshot_v2.sql');
  const bucket = makeR2();
  const objects = r2Objects(bucket);
  const src = makeSource(makeRows(n, { seed }));
  const clock = { t: T0 };
  const now = () => clock.t;
  const cfg = { minStations: 50, ...config };
  const refresh = (extra = {}) => refreshSnapshot({ db, objects, fetchFn: src.fetchFn, now, config: cfg, ...extra });
  const call = (path, init, env = {}) => handleRequest(req(path, init), { db, objects, env, now, fetchFn: src.fetchFn, config: cfg });
  const get = async (path, env) => { const r = await call(path, undefined, env); return { status: r.status, body: await r.json(), headers: r.headers }; };
  return { db, bucket, objects, src, clock, now, cfg, refresh, call, get };
}
const q = (o = {}) => '/v2/france?' + new URLSearchParams({ lat: '46.5', lon: '2.5', dist: '50', fuel: 'Gazole', ...o });

// ---------- normalisation ----------
test('normalizeRows : lignes invalides écartées et comptées, jamais silencieuses', () => {
  const rows = makeRows(5);
  rows.push({ id: '', geom: { lat: 1, lon: 1 } }, { geom: { lat: 1, lon: 1 } }, { id: 'x1' }, { id: 'x2', geom: { lat: 0, lon: 0 } }, { id: 'x3', geom: { lat: 91, lon: 2 } });
  rows.push({ id: 'legacy', latitude: '4600000', longitude: '250000', gazole_prix: '1.9' });
  const r = normalizeRows(rows);
  assert.equal(r.stations.length, 6);
  assert.deepEqual(r.rejected.map((x) => x.reason).sort(), ['invalid_coordinates', 'invalid_coordinates', 'invalid_coordinates', 'missing_id', 'missing_id']);
  const legacy = r.stations.find((s) => s.id === 'legacy');
  assert.equal(legacy.lat, 46); assert.equal(legacy.lon, 2.5); assert.equal(legacy.prices.Gazole[0], 1.9);
});
test('normalizeRows : prix invalides => null + compteur (la station reste)', () => {
  const r = normalizeRows([{ id: 'a', geom: { lat: 45, lon: 3 }, gazole_prix: -1, e10_prix: 'abc', sp95_prix: 25, sp98_prix: 0, e85_prix: '', gplc_prix: 1.1 }]);
  assert.equal(r.stations.length, 1);
  assert.equal(r.invalidPrices, 4);
  assert.deepEqual(Object.keys(r.stations[0].prices), Object.keys(FUELS));
  assert.equal(r.stations[0].prices.GPLc[0], 1.1);
  assert.equal(r.stations[0].prices.Gazole, null);
});
test('normalizeRows : identifiant dupliqué = échec fatal ; entrée non tableau refusée', () => {
  assert.throws(() => normalizeRows([{ id: 'a', geom: { lat: 1, lon: 1 } }, { id: 'a', geom: { lat: 1, lon: 1 } }]), (e) => e.code === 'duplicate_id');
  assert.throws(() => normalizeRows({}), (e) => e.code === 'invalid_dataset');
  assert.throws(() => normalizeRows(null), SnapshotError);
});
test('normalizeRows : la date de mise à jour est conservée seulement si valide', () => {
  const r = normalizeRows([{ id: 'a', geom: { lat: 45, lon: 3 }, gazole_prix: 1.9, gazole_maj: '2026-11-12T07:00:00+00:00', e10_prix: 1.8, e10_maj: 'hier' }]);
  assert.equal(r.stations[0].prices.Gazole[1], '2026-11-12T07:00:00+00:00');
  assert.equal(r.stations[0].prices.E10[1], null);
});

// ---------- construction ----------
test('buildSnapshot : déterministe, empreinte = SHA-256 du corps, version valide', async () => {
  const { stations } = normalizeRows(makeRows(40));
  const a = await buildSnapshot({ stations, sourceTotal: 40, createdAt: '2026-11-12T08:00:00.000Z' });
  const b = await buildSnapshot({ stations, sourceTotal: 40, createdAt: '2026-11-12T08:00:00.000Z' });
  assert.equal(a.body, b.body); assert.equal(a.sha256, b.sha256);
  assert.equal(a.sha256, await sha256Hex(a.body));
  assert.match(a.version, /^20261112T080000Z-[0-9a-f]{8}$/);
  const c = await buildSnapshot({ stations: stations.slice(1), sourceTotal: 40, createdAt: '2026-11-12T08:00:00.000Z' });
  assert.notEqual(a.sha256, c.sha256);
  await assert.rejects(buildSnapshot({ stations, sourceTotal: 40, createdAt: 'x' }), SnapshotError);
});

// ---------- rafraîchissement ----------
test('refresh : publication complète, objet R2 + version + pointeur actif', async () => {
  const s = setup();
  const r = await s.refresh();
  assert.equal(r.status, 'published'); assert.equal(r.count, 300);
  const active = await getActive(s.db);
  assert.equal(active.version, r.version); assert.equal(active.revision, 1); assert.equal(active.status, 'activated');
  assert.equal(s.bucket.data.size, 1);
  assert.equal(s.src.calls.total, 2, 'total mesuré avant ET après l’export'); assert.equal(s.src.calls.export, 1);
});

const FAILS = [
  ['total qui change pendant l’export', (s) => { s.src.state.totalSequence = [300, 301]; }, 'source_total_changed'],
  ['export plus court que le total', (s) => { s.src.state.exportRows = s.src.state.rows.slice(0, 299); }, 'export_count_mismatch'],
  ['export non tableau', (s) => { s.src.state.exportRows = { error: 1 }; }, 'export_count_mismatch'],
  ['source HTTP 500', (s) => { s.src.state.httpStatus = 500; }, 'source_http'],
  ['trop peu de stations', (s) => { s.cfg.minStations = 1000; }, 'too_few_stations'],
  ['trop de lignes rejetées', (s) => { for (let i = 0; i < 10; i++) s.src.state.rows[i] = { id: 'bad' + i }; }, 'too_many_rejected'],
  ['identifiant dupliqué', (s) => { s.src.state.rows[1] = { ...s.src.state.rows[0] }; }, 'duplicate_id']
];
for (const [name, mutate, reason] of FAILS) {
  test(`refresh : échec « ${name} » => ${reason}, rien de publié`, async () => {
    const s = setup();
    mutate(s);
    const r = await s.refresh();
    assert.equal(r.status, 'failed'); assert.equal(r.keptPrevious, true);
    assert.equal(r.reason, reason);
    assert.equal(await getActive(s.db), null); assert.equal(s.bucket.data.size, 0);
    const ev = await s.db.prepare('SELECT kind FROM snapshot_events').all();
    assert.deepEqual(ev.results.map((e) => e.kind), ['refresh_failed']);
  });
}
test('refresh : une chute brutale du nombre de stations est refusée et l’ancienne version reste active', async () => {
  const s = setup();
  const first = await s.refresh();
  s.clock.t += 60000; s.src.state.rows = s.src.state.rows.slice(0, 200);
  const r = await s.refresh();
  assert.equal(r.reason, 'suspicious_station_drop');
  assert.equal((await getActive(s.db)).version, first.version);
});
test('refresh : une horloge qui recule est refusée (stale_candidate)', async () => {
  const s = setup();
  await s.refresh();
  s.clock.t -= 3600000;
  assert.equal((await s.refresh()).reason, 'stale_candidate');
});
test('refresh : 20 rafraîchissements simultanés => une seule publication (bail D1)', async () => {
  const s = setup();
  const out = await Promise.all(Array.from({ length: 20 }, (_, i) => s.refresh({ holder: 'h' + i })));
  assert.equal(out.filter((x) => x.status === 'published').length, 1);
  assert.equal(out.filter((x) => x.reason === 'lease_unavailable').length, 19);
  assert.equal(s.src.calls.export, 1);
  assert.equal((await s.db.prepare('SELECT count(*) n FROM snapshot_versions').first()).n, 1);
});
test('refresh : un bail expiré (processus mort) n’empêche pas la reprise', async () => {
  const s = setup();
  await s.db.prepare('INSERT INTO snapshot_lock(id, holder, expires_at) VALUES(1, ?, ?)').bind('mort', T0 + 1000).run();
  assert.equal((await s.refresh()).reason, 'lease_unavailable');
  s.clock.t += 11 * 60 * 1000;
  assert.equal((await s.refresh()).status, 'published');
});
test('refresh : conflit de publication (un autre publieur passe entre-temps) => échec propre', async () => {
  const s = setup();
  const first = await s.refresh();
  s.clock.t += 60000;
  let hijacked = false;
  const sneaky = { ...s.objects, async get(k) {
    if (!hijacked) {
      hijacked = true;
      // un autre processus insère puis active sa version pendant notre relecture
      await s.db.prepare("INSERT INTO snapshot_versions(version, created_at, sha256, station_count, rejected_count, source_total) VALUES('autre', ?, ?, 1, 0, 1)").bind('2026-11-12T08:00:30.000Z', 'a'.repeat(64)).run();
      assert.equal(await activate(s.db, 'autre', 1, s.now()), true);
    }
    return s.objects.get(k);
  } };
  const r = await refreshSnapshot({ db: s.db, objects: sneaky, fetchFn: s.src.fetchFn, now: s.now, config: s.cfg });
  assert.equal(r.reason, 'publication_conflict');
  assert.equal((await getActive(s.db)).version, 'autre');
  assert.notEqual((await getActive(s.db)).version, first.version);
});
test('refresh : crash après écriture R2 (relecture impossible) => ancienne version intacte, objet orphelin inoffensif', async () => {
  const s = setup();
  const first = await s.refresh();
  s.clock.t += 60000; s.src.state.rows[0] = { ...s.src.state.rows[0], gazole_prix: 1.234 };
  const dying = { ...s.objects, async get() { throw new Error('crash simulé'); } };
  const r = await refreshSnapshot({ db: s.db, objects: dying, fetchFn: s.src.fetchFn, now: s.now, config: s.cfg });
  assert.equal(r.status, 'failed');
  assert.equal((await getActive(s.db)).version, first.version);
  assert.equal(s.bucket.data.size, 2, 'objet orphelin présent mais jamais référencé');
  assert.equal((await s.db.prepare('SELECT count(*) n FROM snapshot_versions').first()).n, 1);
});
test('refresh : relecture R2 corrompue détectée avant publication', async () => {
  const s = setup();
  const bad = { ...s.objects, async get(k) { const b = await s.objects.get(k); return b && b.replace('Ville1', 'Ville9'); } };
  const r = await refreshSnapshot({ db: s.db, objects: bad, fetchFn: s.src.fetchFn, now: s.now, config: s.cfg });
  assert.equal(r.reason, 'readback_mismatch'); assert.equal(await getActive(s.db), null);
});
test('refresh : l’écriture de version existante est refusée (immuabilité R2)', async () => {
  const s = setup();
  const r1 = await s.refresh();
  s.db.raw.exec("UPDATE snapshot_lock SET expires_at = 0");
  const r2 = await s.refresh(); // même horloge, mêmes données => même version => refus
  assert.equal(r2.reason, 'version_exists');
  assert.equal((await getActive(s.db)).version, r1.version);
});
test('refresh : rétention — au plus `retain` versions conservées, les autres élaguées', async () => {
  const s = setup({ config: { retain: 3 } });
  const versions = [];
  for (let i = 0; i < 6; i++) {
    s.clock.t += 60000;
    s.src.state.rows = s.src.state.rows.map((r, j) => (j === 0 ? { ...r, gazole_prix: 1.5 + i / 100 } : r));
    const r = await s.refresh(); assert.equal(r.status, 'published'); versions.push(r.version);
  }
  assert.equal(s.bucket.data.size, 3);
  const { results } = await s.db.prepare('SELECT version, status FROM snapshot_versions ORDER BY created_at').all();
  assert.deepEqual(results.map((r) => r.status), ['pruned', 'pruned', 'pruned', 'activated', 'activated', 'activated']);
  const old = await s.get(q({ snapshot: versions[0] }));
  assert.equal(old.status, 404); assert.equal(old.body.error, 'snapshot_unavailable');
  assert.equal((await s.get(q({ snapshot: versions[4] }))).status, 200);
});

// ---------- schéma D1 : garde-fous ----------
test('schéma : immuabilité, suppression, transitions et pointeur protégés par triggers', async () => {
  const s = setup();
  const r = await s.refresh();
  const exec = (sql) => s.db.raw.exec(sql);
  assert.throws(() => exec(`UPDATE snapshot_versions SET sha256 = '${'b'.repeat(64)}' WHERE version = '${r.version}'`), /snapshot_version_immutable/);
  assert.throws(() => exec(`UPDATE snapshot_versions SET station_count = 1 WHERE version = '${r.version}'`), /snapshot_version_immutable/);
  assert.throws(() => exec(`DELETE FROM snapshot_versions WHERE version = '${r.version}'`), /snapshot_version_undeletable/);
  assert.throws(() => exec(`UPDATE snapshot_versions SET status = 'staged' WHERE version = '${r.version}'`), /snapshot_status_invalid/);
  assert.throws(() => exec(`UPDATE snapshot_versions SET status = 'pruned' WHERE version = '${r.version}'`), /snapshot_active_not_prunable/);
  assert.throws(() => exec('UPDATE snapshot_active SET revision = 5'), /snapshot_revision_step/);
  assert.throws(() => exec('DELETE FROM snapshot_active'), /snapshot_active_undeletable/);
  assert.throws(() => exec("UPDATE snapshot_active SET version = 'inconnue', revision = 2"), /snapshot_target_invalid/);
  assert.throws(() => exec('INSERT INTO snapshot_active(id, version, revision, switched_at) VALUES(2, \'x\', 1, 1)'), /CHECK|snapshot_target_invalid/);
});
test('schéma : on ne peut pas activer une version élaguée', async () => {
  const s = setup({ config: { retain: 2 } });
  const vs = [];
  for (let i = 0; i < 4; i++) { s.clock.t += 60000; s.src.state.rows = s.src.state.rows.map((r, j) => (j === 0 ? { ...r, gazole_prix: 1.5 + i / 100 } : r)); vs.push((await s.refresh()).version); }
  const active = await getActive(s.db);
  await assert.rejects(activate(s.db, vs[0], active.revision, s.now()), /snapshot_target_invalid/);
});

// ---------- HTTP : lecture ----------
test('GET /v2/france : paramètres invalides refusés (y compris prototypes JS)', async () => {
  const s = setup(); await s.refresh();
  const bad = [{ lat: '91' }, { lat: 'abc' }, { lat: '' }, { lon: '-181' }, { dist: '0' }, { dist: '51' }, { dist: '-3' }, { fuel: 'Foo' }, { fuel: 'toString' },
    { fuel: '__proto__' }, { fuel: 'constructor' }, { limit: '0' }, { limit: '101' }, { limit: '1.5' }, { cursor: '-1' }, { cursor: '1.5' }, { cursor: 'x' },
    { snapshot: '../etc' }, { snapshot: 'a b' }, { snapshot: 'x'.repeat(101) }];
  for (const b of bad) { const r = await s.get(q(b)); assert.equal(r.status, 400, JSON.stringify(b)); assert.equal(r.body.error, 'invalid_parameters'); }
  for (const k of ['lat', 'lon', 'dist', 'fuel']) { const p = new URLSearchParams({ lat: '46', lon: '2', dist: '10', fuel: 'E10' }); p.delete(k); assert.equal((await s.get('/v2/france?' + p)).status, 400, 'manquant ' + k); }
  assert.throws(() => parseQuery('https://x/?lat=1'), SnapshotError);
});
test('GET /v2/france : pas prêt avant la première publication (503)', async () => {
  const s = setup();
  const r = await s.get(q());
  assert.equal(r.status, 503); assert.equal(r.body.error, 'not_ready');
});
test('GET /v2/france : résultats = référence Haversine, triés, sans doublon, pagination complète', async () => {
  const s = setup({ n: 2000 });
  await s.refresh();
  const lat = 45.76, lon = 4.84, dist = 40;
  const expected = s.src.state.rows.filter((r) => r.gazole_prix != null && haversineKm({ lat, lon }, r.geom) <= dist).map((r) => r.id).sort();
  assert.ok(expected.length > 5);
  const seen = []; let cursor = null, pages = 0, snap = null, checksum = null;
  do {
    const p = { lat: String(lat), lon: String(lon), dist: String(dist), limit: '7' }; if (cursor !== null) p.cursor = String(cursor); if (snap) p.snapshot = snap;
    const r = await s.get(q(p)); assert.equal(r.status, 200);
    assert.equal(r.body.schemaVersion, 2); assert.equal(r.body.complete, true);
    snap ??= r.body.snapshot; checksum ??= r.body.checksum; assert.equal(r.body.snapshot, snap); assert.equal(r.body.checksum, checksum);
    assert.equal(r.body.total, expected.length);
    seen.push(...r.body.results); cursor = r.body.nextCursor; pages++;
  } while (cursor !== null && pages < 100);
  assert.equal(seen.length, expected.length);
  assert.deepEqual(seen.map((x) => x.id).sort(), expected);
  assert.equal(new Set(seen.map((x) => x.id)).size, seen.length);
  for (let i = 1; i < seen.length; i++) assert.ok(seen[i].distanceIndicativeKm >= seen[i - 1].distanceIndicativeKm);
  for (const x of seen) assert.ok(x.price > 0 && x.distanceIndicativeKm <= dist && x.updatedAt);
});
test('GET /v2/france : une version épinglée reste cohérente pendant un rafraîchissement', async () => {
  const s = setup({ n: 1500 });
  const first = await s.refresh();
  const p1 = await s.get(q({ lat: '46', lon: '2', dist: '50', limit: '5' }));
  assert.ok(p1.body.nextCursor !== null || p1.body.total <= 5);
  s.clock.t += 60000; s.src.state.rows = s.src.state.rows.map((r) => ({ ...r, gazole_prix: 9.99 }));
  const second = await s.refresh(); assert.equal(second.status, 'published');
  const pinned = await s.get(q({ lat: '46', lon: '2', dist: '50', limit: '5', cursor: String(p1.body.nextCursor ?? 0), snapshot: first.version }));
  assert.equal(pinned.status, 200); assert.equal(pinned.body.snapshot, first.version); assert.equal(pinned.body.checksum, p1.body.checksum);
  assert.ok(pinned.body.results.every((x) => x.price < 5));
  const unpinned = await s.get(q({ lat: '46', lon: '2', dist: '50', limit: '5' }));
  assert.equal(unpinned.body.snapshot, second.version);
});
test('GET /v2/france : données périmées signalées (stale) mais servies', async () => {
  const s = setup(); await s.refresh();
  s.clock.t += 25 * 3600 * 1000;
  const r = await s.get(q());
  assert.equal(r.status, 200); assert.equal(r.body.stale, true); assert.ok(r.body.ageMs >= 25 * 3600 * 1000);
});
test('GET /v2/france : une version altérée dans R2 n’est jamais servie (integrity_failure)', async () => {
  const s = setup(); const r = await s.refresh(); clearCache();
  const key = [...s.bucket.data.keys()][0];
  s.bucket.data.set(key, s.bucket.data.get(key).replace('"Ville1"', '"Ville2"'));
  const out = await s.get(q());
  assert.equal(out.status, 503); assert.equal(out.body.error, 'integrity_failure');
  assert.ok(r.version);
});
test('GET /v2/status : état public minimal, sans secret', async () => {
  const s = setup();
  assert.equal((await s.get('/v2/status')).body.ready, false);
  const r = await s.refresh();
  const st = await s.get('/v2/status');
  assert.equal(st.body.ready, true); assert.equal(st.body.active.version, r.version); assert.equal(st.body.lastEvent.kind, 'refresh_success');
  assert.ok(!JSON.stringify(st.body).includes('secret'));
});

// ---------- CORS ----------
test('CORS : origine autorisée reflétée, autres sans en-tête, préflight 204, liste surchargeable', async () => {
  const s = setup(); await s.refresh();
  const ok = await s.call(q(), { headers: { Origin: 'https://carburantradar.fr' } });
  assert.equal(ok.headers.get('Access-Control-Allow-Origin'), 'https://carburantradar.fr'); assert.equal(ok.headers.get('Vary'), 'Origin');
  const ko = await s.call(q(), { headers: { Origin: 'https://evil.example' } });
  assert.equal(ko.headers.get('Access-Control-Allow-Origin'), null);
  const pre = await s.call(q(), { method: 'OPTIONS', headers: { Origin: 'https://emilienzabu.github.io' } });
  assert.equal(pre.status, 204); assert.equal(pre.headers.get('Access-Control-Allow-Origin'), 'https://emilienzabu.github.io');
  const env = await s.call(q(), { headers: { Origin: 'https://staging.example' } }, { ALLOWED_ORIGINS: 'https://staging.example' });
  assert.equal(env.headers.get('Access-Control-Allow-Origin'), 'https://staging.example');
});

// ---------- administration et retour arrière ----------
const post = (path, body, token) => ({ method: 'POST', headers: { ...(token ? { Authorization: 'Bearer ' + token } : {}), 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) });
test('admin : désactivé sans secret, 401 si jeton faux, jamais de lecture du secret par GET', async () => {
  const s = setup();
  assert.equal((await s.call('/admin/snapshot/refresh', post('/x'))).status, 503);
  const env = { RADAR_ADMIN_SECRET: 'S3cret-test' };
  assert.equal((await s.call('/admin/snapshot/refresh', post('/x'), env)).status, 401);
  assert.equal((await s.call('/admin/snapshot/refresh', post('/x', {}, 'faux'), env)).status, 401);
  assert.equal((await s.call('/admin/snapshot/refresh', { method: 'GET' }, env)).status, 404);
  const ok = await s.call('/admin/snapshot/refresh', post('/x', {}, 'S3cret-test'), env);
  assert.equal(ok.status, 200); assert.equal((await ok.json()).status, 'published');
});
test('rollback : retour à la version précédente, requêtes servies depuis elle, événement journalisé', async () => {
  const s = setup({ n: 500 });
  const a = await s.refresh();
  s.clock.t += 60000; s.src.state.rows = s.src.state.rows.map((r) => ({ ...r, gazole_prix: 9.5 }));
  const b = await s.refresh();
  assert.equal((await s.get(q())).body.snapshot, b.version);
  const env = { RADAR_ADMIN_SECRET: 'tok' };
  const rb = await s.call('/admin/snapshot/rollback', post('', { version: a.version }, 'tok'), env);
  assert.equal(rb.status, 200); assert.deepEqual(await rb.json(), { status: 'rolled_back', from: b.version, to: a.version });
  const after = await s.get(q());
  assert.equal(after.body.snapshot, a.version); assert.ok(after.body.results.every((x) => x.price < 5));
  assert.equal((await getActive(s.db)).revision, 3);
  assert.equal((await s.db.prepare('SELECT kind FROM snapshot_events ORDER BY id DESC LIMIT 1').first()).kind, 'rollback');
  // et on peut revenir en avant
  assert.equal((await rollbackSnapshot({ db: s.db, objects: s.objects, version: b.version, now: s.now })).to, b.version);
});
test('rollback : refusé pour version inconnue, déjà active, élaguée, invalide ou altérée', async () => {
  const s = setup({ config: { retain: 2 } });
  const vs = [];
  for (let i = 0; i < 3; i++) { s.clock.t += 60000; s.src.state.rows = s.src.state.rows.map((r, j) => (j === 0 ? { ...r, gazole_prix: 1.5 + i / 100 } : r)); vs.push((await s.refresh()).version); }
  const env = { RADAR_ADMIN_SECRET: 'tok' }; const rb = (v) => s.call('/admin/snapshot/rollback', post('', { version: v }, 'tok'), env).then(async (r) => [r.status, (await r.json()).error]);
  assert.deepEqual(await rb('inconnue'), [422, 'version_not_restorable']);
  assert.deepEqual(await rb(vs[2]), [422, 'already_active']);
  assert.deepEqual(await rb(vs[0]), [422, 'version_not_restorable']);
  assert.deepEqual(await rb('../x'), [422, 'invalid_version']);
  assert.deepEqual(await rb(undefined), [422, 'invalid_version']);
  clearCache(); const key = `france/snapshots/${vs[1]}.json`; s.bucket.data.set(key, s.bucket.data.get(key) + ' ');
  assert.deepEqual(await rb(vs[1]), [422, 'integrity_failure']);
  assert.equal((await getActive(s.db)).version, vs[2], 'pointeur inchangé après refus');
  assert.equal((await s.call('/admin/snapshot/rollback', { method: 'POST', headers: { Authorization: 'Bearer tok', 'Content-Type': 'application/json' }, body: '{pas du json' }, env)).status, 400);
});
test('constantTimeEqual', () => {
  assert.equal(constantTimeEqual('abc', 'abc'), true);
  assert.equal(constantTimeEqual('abc', 'abd'), false);
  assert.equal(constantTimeEqual('abc', 'abcd'), false);
  assert.equal(constantTimeEqual('', undefined), true);
});

// ---------- taille réelle ----------
test('taille réelle (9 826 stations) : publication, relecture et requête dans des délais raisonnables', async () => {
  const s = setup({ n: 9826, config: { minStations: 5000 } });
  const t0 = performance.now(); const r = await s.refresh(); const t1 = performance.now();
  assert.equal(r.status, 'published');
  clearCache();
  const t2 = performance.now(); const first = await s.get(q({ lat: '48.85', lon: '2.35', dist: '20' })); const t3 = performance.now();
  const second = await s.get(q({ lat: '48.85', lon: '2.35', dist: '20' })); const t4 = performance.now();
  assert.equal(first.status, 200);
  const body = [...s.bucket.data.values()][0];
  console.log(`# MESURE (Node, pas Workers) : refresh=${(t1 - t0).toFixed(0)} ms ; 1re requête à froid=${(t3 - t2).toFixed(0)} ms ; requête en cache=${(t4 - t3).toFixed(1)} ms ; objet=${(body.length / 1e6).toFixed(2)} Mo`);
  assert.ok(t1 - t0 < 15000); assert.ok(t4 - t3 < 500);
  assert.equal(second.body.checksum, first.body.checksum);
});
