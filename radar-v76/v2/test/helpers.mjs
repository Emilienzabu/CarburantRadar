// Aides de test. ÉMULATIONS : SQLite (node:sqlite) à la place de D1, Map à la place de R2.
// Elles ne prouvent NI la concurrence réelle entre isolats NI les limites Cloudflare.
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
export const migration = (name) => readFileSync(join(here, '..', 'migrations', name), 'utf8');

export function makeD1(...migrations) {
  const sql = new DatabaseSync(':memory:');
  sql.exec('PRAGMA foreign_keys = ON');
  for (const m of migrations) sql.exec(migration(m));
  const db = {
    raw: sql,
    prepare(q) {
      let args = [];
      const st = {
        bind(...a) { args = a; return st; },
        async run() { const r = sql.prepare(q).run(...args); return { success: true, meta: { changes: Number(r.changes) } }; },
        async first() { return sql.prepare(q).get(...args) ?? null; },
        async all() { return { results: sql.prepare(q).all(...args) }; }
      };
      return st;
    }
  };
  return db;
}

export function makeR2() {
  const data = new Map();
  const bucket = {
    data,
    async put(key, body, opts = {}) {
      if (opts.onlyIf?.etagDoesNotMatch === '*' && data.has(key)) return null;
      data.set(key, body);
      return { key };
    },
    async get(key) { return data.has(key) ? { async text() { return data.get(key); } } : null; },
    async delete(key) { data.delete(key); }
  };
  return bucket;
}

// Générateur déterministe de lignes au format de l'export ODS (champs observés dans l'audit E0/E1).
export function makeRows(n, { seed = 1, nowIso = '2026-11-12T08:00:00+00:00' } = {}) {
  let s = seed;
  const rnd = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 2 ** 32; };
  const rows = [];
  for (let i = 0; i < n; i++) {
    const lat = 42.5 + rnd() * 8, lon = -4.5 + rnd() * 13;
    rows.push({
      id: String(10000000 + i), geom: { lat, lon }, adresse: `${i} rue de Test`, ville: `Ville${i % 400}`, cp: String(10000 + (i % 89000)).padStart(5, '0'),
      gazole_prix: round(1.7 + rnd() * 0.5), gazole_maj: nowIso,
      sp95_prix: i % 5 === 0 ? null : round(1.8 + rnd() * 0.5), sp95_maj: nowIso,
      sp98_prix: i % 3 === 0 ? null : round(1.9 + rnd() * 0.5), sp98_maj: nowIso,
      e10_prix: i % 7 === 0 ? null : round(1.75 + rnd() * 0.5), e10_maj: nowIso,
      e85_prix: i % 4 === 0 ? round(0.8 + rnd() * 0.3) : null, e85_maj: nowIso,
      gplc_prix: i % 11 === 0 ? round(0.9 + rnd() * 0.2) : null, gplc_maj: nowIso
    });
  }
  return rows;
}
const round = (x) => Math.round(x * 1000) / 1000;

// Faux serveur de données : total_count + export, avec options de panne.
export function makeSource(rows, opts = {}) {
  const calls = { total: 0, export: 0 };
  const state = { rows, totalOverride: null, totalSequence: null, exportRows: null, httpStatus: 200 };
  const fetchFn = async (url) => {
    const u = String(url);
    if (state.httpStatus !== 200) return new Response('x', { status: state.httpStatus });
    if (u.includes('/records?limit=1')) {
      const t = state.totalSequence ? state.totalSequence[Math.min(calls.total, state.totalSequence.length - 1)] : (state.totalOverride ?? state.rows.length);
      calls.total++;
      return new Response(JSON.stringify({ total_count: t, results: [] }), { status: 200 });
    }
    if (u.endsWith('/exports/json')) { calls.export++; return new Response(JSON.stringify(state.exportRows ?? state.rows), { status: 200 }); }
    return new Response('nf', { status: 404 });
  };
  return { fetchFn, calls, state };
}

export const req = (path, init = {}) => new Request('https://radar.test' + path, init);
