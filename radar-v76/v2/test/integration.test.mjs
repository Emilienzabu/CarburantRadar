// Intégration : Worker V2 <-> modules du prototype V76 (inchangés) + constats de qualité sur le prototype.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { refreshSnapshot, handleRequest, r2Objects, clearCache, haversineKm } from '../snapshot-worker.mjs';
import { makeD1, makeR2, makeRows, makeSource, req } from './helpers.mjs';

const require = createRequire(import.meta.url);
const { rankSnapshot, loadSnapshotStations } = require('../../prototype/radar-snapshot-bridge.js');
const { normalizeV2Page } = require('../../prototype/proxy-contract.js');
const protoSnap = require('../../prototype/snapshot-france.js');
const { createPersistence, memoryAdapters } = require('../../prototype/snapshot-persistence.js');
const { handleFranceV2 } = require('../../prototype/worker-france-v2.js');

const now = () => Date.parse('2026-11-12T08:00:00Z');
async function live(rows) {
  clearCache();
  const db = makeD1('0001_snapshot_v2.sql'), objects = r2Objects(makeR2()), src = makeSource(rows);
  const cfg = { minStations: 50 };
  const r = await refreshSnapshot({ db, objects, fetchFn: src.fetchFn, now, config: cfg });
  assert.equal(r.status, 'published');
  const queryPage = async ({ lat, lon, radiusKm, fuel, offset, limit, snapshot }) => {
    const p = new URLSearchParams({ lat, lon, dist: radiusKm, fuel, cursor: offset, limit }); if (snapshot) p.set('snapshot', snapshot);
    const res = await handleRequest(req('/v2/france?' + p), { db, objects, now, config: cfg });
    assert.equal(res.status, 200); return res.json();
  };
  return { queryPage, db, objects, version: r.version };
}
const cluster = (n) => makeRows(n).map((r, i) => ({ ...r, geom: { lat: 45 + (i % 20) * 0.01, lon: 5 + Math.floor(i / 20) * 0.01 } }));

test('le pont du prototype (rankSnapshot) consomme le Worker V2 sur plusieurs pages et certifie le classement', async () => {
  const rows = cluster(350); const { queryPage } = await live(rows);
  const vehicle = { id: 'v1', name: 'C', fuel: 'Gazole', consumption: 6, tankCapacity: 50, illustration: 'citadine_bleue', fillPercent: 80 };
  const origin = { lat: 45.1, lon: 5.1 };
  const routeBatch = async ({ stations }) => stations.map((s) => ({ id: s.id, distanceRoundTripKm: 2 * 1.3 * haversineKm(origin, s) }));
  const loaded = await loadSnapshotStations({ queryPage, origin, radiusKm: 50, fuel: 'Gazole', pageSize: 40 });
  assert.equal(loaded.metadata.pages, Math.ceil(350 / 40)); assert.equal(loaded.stations.length, 350);
  const out = await rankSnapshot({ queryPage, origin, radiusKm: 50, fuel: 'Gazole', vehicle, fillPercent: 80, routeBatch, now: now(), pageSize: 40 });
  assert.equal(out.ranking.certified, true); assert.equal(out.metadata.complete, true);
  assert.equal(out.metadata.total, 350);
});
test('le pont refuse un changement de version en cours de route (pas de mélange)', async () => {
  const { queryPage } = await live(cluster(120));
  let n = 0;
  const flaky = async (p) => { const r = await queryPage(p); if (++n === 2) r.checksum = 'f'.repeat(64); return r; };
  await assert.rejects(loadSnapshotStations({ queryPage: flaky, origin: { lat: 45.1, lon: 5.1 }, radiusKm: 50, fuel: 'Gazole', pageSize: 40 }), /snapshot_changed/);
});

// ---------- constats sur le prototype (documentent des incompatibilités réelles) ----------
test('CONSTAT C1 : proxy-contract.js (V2 « curseur chaîne ») est incompatible avec le contrat snapshot (curseur numérique, complete=true par page)', async () => {
  const { queryPage } = await live(cluster(120));
  const page = await queryPage({ lat: 45.1, lon: 5.1, radiusKm: 50, fuel: 'Gazole', offset: 0, limit: 40 });
  assert.ok(page.nextCursor !== null);
  assert.throws(() => normalizeV2Page(page, 'Gazole'), /complete avec curseur/i, 'contrat 1 rejette les pages intermédiaires du contrat 2');
  const last = await queryPage({ lat: 45.1, lon: 5.1, radiusKm: 50, fuel: 'Gazole', offset: 80, limit: 40 });
  assert.equal(last.nextCursor, null); assert.doesNotThrow(() => normalizeV2Page(last, 'Gazole'));
});
test('CONSTAT C2 : snapshot-france.js (prototype) fait échouer TOUT le jeu sur une seule ligne invalide', () => {
  const rows = makeRows(20); rows[7] = { ...rows[7], gazole_prix: -1 };
  assert.throws(() => protoSnap.buildSnapshot(rows, { version: 'v1' }), /invalid_price/);
  rows[7] = { id: 'sans-geom' };
  assert.throws(() => protoSnap.buildSnapshot(rows, { version: 'v1' }), /invalid_coordinates/);
});
test('CONSTAT C3 : snapshot-persistence.js reconstruit et re-hache le jeu entier à CHAQUE requête (coût mesuré)', async () => {
  const rows = makeRows(9826); const mem = memoryAdapters();
  const p = createPersistence({ objects: mem.objects, coordinator: mem.coordinator, maxAgeMs: 9e12 });
  const m = await p.stage(rows, 'v1'); await p.publish(m);
  const params = { lat: 48.85, lon: 2.35, radiusKm: 20, fuel: 'Gazole' };
  await p.query(params);
  const t0 = performance.now(); for (let i = 0; i < 5; i++) await p.query(params); const proto = (performance.now() - t0) / 5;
  const db = makeD1('0001_snapshot_v2.sql'), objects = r2Objects(makeR2()); clearCache();
  await refreshSnapshot({ db, objects, fetchFn: makeSource(rows).fetchFn, now, config: { minStations: 50 } });
  const call = () => handleRequest(req('/v2/france?lat=48.85&lon=2.35&dist=20&fuel=Gazole'), { db, objects, now });
  await call(); const t1 = performance.now(); for (let i = 0; i < 5; i++) await call(); const v2 = (performance.now() - t1) / 5;
  console.log(`# MESURE (Node) : requête prototype=${proto.toFixed(1)} ms ; requête V2 (cache d’isolat)=${v2.toFixed(1)} ms`);
  assert.ok(v2 < proto, 'le cache par isolat doit être plus rapide');
});
test('CONSTAT C4 : worker-france-v2.js (prototype) enchaîne >50 sous-requêtes pour un grand jeu (limite Workers gratuite documentée : 50)', async () => {
  const total = 9000; let calls = 0;
  const fetchFn = async (url) => {
    calls++; const u = new URL(url); const off = Number(u.searchParams.get('offset')), lim = Number(u.searchParams.get('limit'));
    const results = Array.from({ length: Math.max(0, Math.min(lim, total - off)) }, (_, i) => ({ id: String(off + i), gazole_prix: 1.8, geom: { lat: 45, lon: 5 } }));
    return new Response(JSON.stringify({ total_count: total, results }), { status: 200 });
  };
  const r = await handleFranceV2(new Request('https://x/v2/france?lat=45&lon=5&dist=50&fuel=Gazole'), { fetchFn });
  assert.equal(r.status, 200); assert.ok(calls > 50, `sous-requêtes=${calls}`);
  assert.match((await r.json()).snapshot, /^single-response-/, 'identifiant de snapshot non versionné');
});
