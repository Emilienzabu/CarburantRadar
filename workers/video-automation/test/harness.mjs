// Harnais de test : D1 simulé (node:sqlite), R2/KV factices, réseau factice. AUCUN accès réseau réel :
// toute URL non prévue fait échouer le test. Les clés/mots de passe ci-dessous sont des valeurs de test.
import { DatabaseSync } from "node:sqlite";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(HERE, "../../..");
const lire = (p) => (existsSync(p) ? readFileSync(p, "utf8") : null);
export const SQL_0001 = lire(path.join(ROOT, "video/ledger/0001_video_ledger.sql"));
export const SQL_0002 = lire(path.join(ROOT, "video/ledger/0002_video_ledger_evidence.sql"));

export const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
export const video = (texte) => new TextEncoder().encode(`mp4-de-test:${texte}`);
const realSetTimeout = globalThis.setTimeout;
export const dormir = (ms) => new Promise((r) => realSetTimeout(r, ms));
const jamais = () => new Promise(() => {});          // promesse qui ne se résout jamais = processus tué
const tick = () => new Promise((r) => setImmediate(r)); // point d'entrelacement entre deux requêtes SQL

// ---------------------------------------------------------------- D1 simulé
class Stmt {
  constructor(shim, sql, args = []) { this.shim = shim; this.sql = sql; this.args = args; }
  bind(...args) { return new Stmt(this.shim, this.sql, args); }
  async _pret() {
    await tick();
    for (const f of this.shim.pannes) {
      if (f.motif.test(this.sql) && f.reste > 0) {
        f.reste--;
        if (f.mode === "suspendre") await jamais();
        throw new Error("D1 : panne injectée (" + f.motif + ")");
      }
    }
    return this.shim.db.prepare(this.sql);
  }
  async run() { const r = (await this._pret()).run(...this.args); return { success: true, meta: { changes: Number(r.changes) } }; }
  async first() { const r = (await this._pret()).get(...this.args); return r ? { ...r } : null; }
  async all() { return { success: true, results: (await this._pret()).all(...this.args).map((r) => ({ ...r })) }; }
}
export class D1Shim {
  constructor(sqls = [SQL_0001, SQL_0002]) {
    this.db = new DatabaseSync(":memory:");
    this.pannes = [];
    for (const s of sqls) if (s) this.db.exec(s);
  }
  prepare(sql) { return new Stmt(this, sql); }
  async exec(sql) { this.db.exec(sql); }
  /** Fait échouer (mode "erreur") ou geler (mode "suspendre" : le processus « meurt ») les n prochaines requêtes dont le SQL correspond. */
  injecter(motif, mode = "erreur", reste = 1) { this.pannes.push({ motif, mode, reste }); }
  sql(requete, ...args) { return this.db.prepare(requete).all(...args).map((r) => ({ ...r })); }
}

// ---------------------------------------------------------------- R2 / KV factices
async function versOctets(v) {
  if (typeof v === "string") return new TextEncoder().encode(v);
  if (v instanceof ArrayBuffer) return new Uint8Array(v.slice(0));
  if (ArrayBuffer.isView(v)) return new Uint8Array(v.buffer.slice(v.byteOffset, v.byteOffset + v.byteLength));
  if (v && typeof v.getReader === "function") return new Uint8Array(await new Response(v).arrayBuffer());
  throw new Error("type R2 non géré");
}
export class R2Fake {
  constructor() { this.objects = new Map(); }
  async put(key, valeur, opts = {}) {
    this.objects.set(key, { bytes: await versOctets(valeur), customMetadata: { ...(opts.customMetadata || {}) } });
  }
  async get(key) {
    const o = this.objects.get(key);
    if (!o) return null;
    return { body: new Blob([o.bytes]).stream(), customMetadata: o.customMetadata,
             arrayBuffer: async () => o.bytes.buffer.slice(o.bytes.byteOffset, o.bytes.byteOffset + o.bytes.byteLength) };
  }
  async list() { return { objects: [...this.objects.keys()].sort().map((key) => ({ key })), truncated: false }; }
  async delete(key) { this.objects.delete(key); }
  cles() { return [...this.objects.keys()].sort(); }
}
export class KVFake {
  constructor(init = {}) { this.m = new Map(Object.entries(init)); }
  async get(k) { return this.m.has(k) ? this.m.get(k) : null; }
  async put(k, v) { this.m.set(k, v); }
  async delete(k) { this.m.delete(k); }
}
const LOIN = Date.now() + 365 * 24 * 3600 * 1000;
export function makeEnv(extra = {}) {
  const kv = new KVFake({
    youtube_refresh_token_carburant: "rt-c", youtube_refresh_token: "rt-d",
    instagram_token_carburant: JSON.stringify({ access_token: "igt-c", expires_at: LOIN }),
    instagram_token: JSON.stringify({ access_token: "igt-d", expires_at: LOIN }),
  });
  return { API_KEY: "cle-api-test", UPLOAD_PASSWORD: "mdp-test", YOUTUBE_CLIENT_ID: "cid", YOUTUBE_CLIENT_SECRET: "cs",
           INSTAGRAM_ACCOUNT_ID_CARBURANT: "ig-c", INSTAGRAM_ACCOUNT_ID: "ig-d",
           CONFIG_KV: kv, VIDEO_BUCKET: new R2Fake(), ...extra };
}

// ---------------------------------------------------------------- réseau factice (YouTube, Instagram)
/** Modes YouTube : ok | ok_sans_identifiant | http_error | throw_avant | suspendre_avant | perdu_apres_publication | suspendre_apres_publication.
 *  Modes Instagram : ok | creation_http_error | jamais_pret | publish_http_error | perdu_apres_publication | suspendre_apres_publication | suspendre_avant_creation. */
export class Net {
  constructor() {
    this.yt = { mode: "ok", delai: 0, avant: null };
    this.ig = { mode: "ok", delai: 0, avant: null, apresCreation: null };
    this.appels = { youtube: 0, instagram_creation: 0, instagram_publish: 0, token: 0 };
    this.publie = { youtube: [], instagram: [] };
    this.conteneurs = new Map();
    this.n = 0; this.worker = null; this.env = null;
    this.urls = [];
  }
  installer() {
    this._fetch = globalThis.fetch; this._st = globalThis.setTimeout;
    globalThis.fetch = (u, i) => this._traiter(u, i);
    globalThis.setTimeout = (fn, ms, ...a) => realSetTimeout(fn, ms >= 1000 ? 1 : ms, ...a); // sondage Instagram (5 s) accéléré
  }
  restaurer() { globalThis.fetch = this._fetch; globalThis.setTimeout = this._st; }
  async _traiter(input, init = {}) {
    const url = typeof input === "string" ? input : input.url;
    this.urls.push(url);
    const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json" } });
    if (url.startsWith("https://oauth2.googleapis.com/token")) { this.appels.token++; return json({ access_token: "at-test" }); }
    if (url.startsWith("https://www.googleapis.com/upload/youtube/v3/videos")) return this._youtube(init, json);
    const m = url.match(/^https:\/\/graph\.instagram\.com\/v21\.0\/([^/?]+)(\/media|\/media_publish)?(\?.*)?$/);
    if (m) return this._instagram(m, init, json);
    throw new Error("RÉSEAU INTERDIT en test : " + url);
  }
  async _youtube(init, json) {
    this.appels.youtube++;
    const y = this.yt;
    if (y.avant) await y.avant();
    if (y.delai) await dormir(y.delai);
    if (y.mode === "throw_avant") throw new Error("réseau coupé avant l'envoi");
    if (y.mode === "suspendre_avant") await jamais();
    if (y.mode === "http_error") return json({ error: { message: "quota" } }, 403);
    const corps = new Uint8Array(await new Blob([init.body]).arrayBuffer());
    const txt = Buffer.from(corps).toString("latin1");
    const debut = txt.indexOf("Content-Type: video/mp4\r\n\r\n") + "Content-Type: video/mp4\r\n\r\n".length;
    const fin = txt.lastIndexOf("\r\n--video_automation_boundary--");
    const sha = sha256(corps.slice(debut, fin));
    const meta = JSON.parse(txt.slice(txt.indexOf("{"), txt.indexOf("\r\n--video_automation_boundary", 5)));
    const id = "yt-" + sha.slice(0, 8);
    this.publie.youtube.push({ sha, id, titre: meta.snippet.title });
    if (y.mode === "suspendre_apres_publication") await jamais();
    if (y.mode === "perdu_apres_publication") throw new Error("réponse YouTube perdue");
    if (y.mode === "ok_sans_identifiant") return json({});
    return json({ id });
  }
  async _instagram(m, init, json) {
    const [, cible, suffixe] = m;
    const g = this.ig;
    if (suffixe === "/media") {
      this.appels.instagram_creation++;
      if (g.avant) await g.avant();
      if (g.delai) await dormir(g.delai);
      if (g.mode === "suspendre_avant_creation") await jamais();
      if (g.mode === "creation_http_error") return json({ error: { message: "refusé" } }, 400);
      const b = JSON.parse(init.body);
      const id = "c-" + ++this.n;
      this.conteneurs.set(id, { video_url: b.video_url, sondages: 0, sha: null });
      if (g.apresCreation) await g.apresCreation(id);
      return json({ id });
    }
    if (suffixe === "/media_publish") {
      this.appels.instagram_publish++;
      if (g.delai) await dormir(g.delai);
      const b = JSON.parse(init.body);
      const c = this.conteneurs.get(b.creation_id);
      if (g.mode === "publish_http_error") return json({ error: { message: "erreur serveur" } }, 500);
      const id = "ig-" + (c.sha || "inconnu").slice(0, 8);
      this.publie.instagram.push({ sha: c.sha, id, conteneur: b.creation_id });
      if (g.mode === "suspendre_apres_publication") await jamais();
      if (g.mode === "perdu_apres_publication") throw new Error("réponse Instagram perdue");
      return json({ id });
    }
    // sondage du conteneur : Instagram « télécharge » la vidéo au 2e sondage (traitement asynchrone côté plateforme)
    const c = this.conteneurs.get(cible);
    if (g.mode === "jamais_pret") return json({ status_code: "IN_PROGRESS" });
    c.sondages++;
    if (c.sondages < 2) return json({ status_code: "IN_PROGRESS" });
    if (!c.sha) {
      const r = await this.worker.fetch(new Request(c.video_url), this.env);
      c.sha = r.status === 200 ? sha256(new Uint8Array(await r.arrayBuffer())) : "introuvable";
    }
    return json({ status_code: c.sha === "introuvable" ? "ERROR" : "FINISHED" });
  }
}

// ---------------------------------------------------------------- requêtes
export function requeteApi({ octets, slot, sha, profil = "carburant", titre, cle = "cle-api-test", extra = {} }) {
  const fd = new FormData();
  fd.set("profile", profil);
  fd.set("video", new File([octets], "video-du-jour.mp4", { type: "video/mp4" }));
  if (titre) fd.set("title", titre);
  if (slot !== undefined && slot !== null) fd.set("slot_id", slot);
  if (sha !== undefined && sha !== null) fd.set("sha256", sha);
  for (const [k, v] of Object.entries(extra)) fd.set(k, v);
  return new Request("https://video-automation.test/api/upload", { method: "POST", headers: { authorization: `Bearer ${cle}` }, body: fd });
}
export async function envoyer(worker, env, req) {
  const r = await worker.fetch(req, env);
  const texte = await r.text();
  let corps = null;
  try { corps = JSON.parse(texte); } catch { /* HTML ou texte */ }
  return { statut: r.status, corps, texte };
}
export function contexte(worker, extraEnv = {}, { d1 = true } = {}) {
  const net = new Net();
  const env = makeEnv(d1 ? { DB_VIDEO: new D1Shim(), ...extraEnv } : extraEnv);
  net.worker = worker; net.env = env; net.installer();
  const attente = [];
  const ctx = { waitUntil: (p) => attente.push(p) };
  return { net, env, ctx, attente, fin: () => net.restaurer(),
           planifie: async () => { await worker.scheduled({}, env, ctx); await Promise.all(attente.splice(0)); } };
}
export async function avecHorloge(ms, fn) {            // fait « vieillir » Date.now() (utilisé par le balayage des créneaux)
  const reel = Date.now; Date.now = () => reel() + ms;
  try { return await fn(); } finally { Date.now = reel; }
}
