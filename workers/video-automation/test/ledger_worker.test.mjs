// Protocole anti-doublon du Worker modifié (src/index.js) : D1 simulé sur SQLite (0001 + 0002), R2/KV/réseau factices.
// Aucun réseau réel, aucune publication. La concurrence est celle d'un seul processus Node : les requêtes s'entrelacent
// entre deux requêtes SQL ou deux appels réseau (comme des isolats Workers), ce n'est PAS la concurrence réelle de D1.
import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";
import { contexte, envoyer, requeteApi, sha256, video, dormir, avecHorloge, D1Shim, SQL_0001 } from "./harness.mjs";

const SLOT = "2026-11-07:matin";
const V = video("A");
const CLE = (sha, slot = SLOT) => `carburant/${slot.replace(":", "_")}/${sha}.mp4`;
const req = (v = V, o = {}) => requeteApi({ octets: v, slot: SLOT, sha: sha256(v), ...o });
async function avec(fn, { env, options } = {}) { const c = contexte(worker, env, options); try { await fn(c); } finally { c.fin(); } }
const statut = (c, slot = SLOT) => (c.env.DB_VIDEO.sql("SELECT status FROM video_slot_reservations WHERE slot_key=?", slot)[0] || {}).status;
const obs = (c) => Object.fromEntries(c.env.DB_VIDEO.sql("SELECT platform,status,remote_id FROM video_platform_results WHERE slot_key=?", SLOT).map((r) => [r.platform, [r.status, r.remote_id]]));
const traces = (c) => Object.fromEntries(c.env.DB_VIDEO.sql("SELECT platform||'/'||ref_kind AS k, ref_value FROM video_attempt_refs WHERE slot_key=?", SLOT).map((r) => [r.k, r.ref_value]));
const appels = (c) => [c.net.appels.youtube, c.net.appels.instagram_creation, c.net.appels.instagram_publish];
const publies = (c) => [c.net.publie.youtube.length, c.net.publie.instagram.length];
async function attendre(cond, ms = 3000) { const fin = Date.now() + ms; while (!cond()) { if (Date.now() > fin) throw new Error("délai d'attente du test"); await dormir(2); } }
const admin = (c, chemin, corps, cle = "mdp-test") => envoyer(worker, c.env, new Request(`https://video-automation.test/ledger/${chemin}${chemin.includes("?") ? "&" : "?"}key=${cle}`,
  corps ? { method: "POST", body: JSON.stringify(corps) } : { method: "GET" }));
const apresVieillissement = (c, fn) => avecHorloge(31 * 60 * 1000, fn);

test("contrat : entrées invalides refusées avant toute écriture et tout appel réseau", () => avec(async (c) => {
  const cas = [["slot_id manquant", requeteApi({ octets: V, sha: sha256(V) }), "slot_id_requis"],
    ["slot_id absurde", req(V, { slot: "demain" }), "slot_id_invalide"],
    ["date impossible", req(V, { slot: "2026-13-45:matin" }), "slot_id_invalide"],
    ["période inconnue", req(V, { slot: "2026-11-07:midi" }), "slot_id_invalide"],
    ["sha256 manquant", requeteApi({ octets: V, slot: SLOT }), "sha256_requis"],
    ["sha256 non hexadécimal", req(V, { sha: "z".repeat(64) }), "sha256_invalide"],
    ["sha256 en majuscules", req(V, { sha: sha256(V).toUpperCase() }), "sha256_invalide"],
    ["sha256 différent du fichier", req(V, { sha: sha256(video("autre")) }), "sha256_different_du_contenu"]];
  for (const [nom, r, code] of cas) {
    const rep = await envoyer(worker, c.env, r);
    assert.equal(rep.statut, 400, nom); assert.equal(rep.corps.code, code, nom); assert.equal(rep.corps.etat, "refuse", nom);
  }
  assert.equal(c.net.urls.length, 0);
  assert.equal(c.env.DB_VIDEO.sql("SELECT COUNT(*) AS n FROM video_slot_reservations")[0].n, 0);
  assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
  assert.equal((await envoyer(worker, c.env, req(V, { cle: "mauvaise" }))).statut, 401, "authentification inchangée");
}));

test("sans binding D1 : refus total (503), rien n'est publié", () => avec(async (c) => {
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 503); assert.equal(rep.corps.code, "ledger_non_configure"); assert.equal(rep.corps.etat, "refuse");
  assert.equal(c.net.urls.length, 0); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}, { options: { d1: false } }));

test("nominal : 200, mêmes octets sur YouTube et Instagram, clés de réponse historiques conservées, copie R2 supprimée", () => avec(async (c) => {
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 200); assert.equal(rep.corps.etat, "complet"); assert.equal(rep.corps.rejoue, false);
  assert.equal(rep.corps.youtube.success, true); assert.match(rep.corps.youtube.url, /^https:\/\/youtu\.be\/yt-/);
  assert.equal(rep.corps.instagram.success, true); assert.match(rep.corps.instagram.mediaId, /^ig-/);
  assert.equal(c.net.publie.youtube[0].sha, sha256(V)); assert.equal(c.net.publie.instagram[0].sha, sha256(V));
  assert.deepEqual(appels(c), [1, 1, 1]); assert.equal(statut(c), "reported_complete");
  assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}));

test("rejeu d'un créneau complet : 200 en lecture seule, aucun appel, aucune copie recréée", () => avec(async (c) => {
  await envoyer(worker, c.env, req());
  const avant = c.net.urls.length;
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 200); assert.equal(rep.corps.rejoue, true); assert.equal(rep.corps.youtube.success, true);
  assert.equal(c.net.urls.length, avant); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}));

test("même créneau, autre vidéo : 409, aucun appel, aucune copie de la 2e vidéo", () => avec(async (c) => {
  await envoyer(worker, c.env, req());
  const B = video("B"); const avant = c.net.urls.length;
  const rep = await envoyer(worker, c.env, req(B));
  assert.equal(rep.statut, 409); assert.equal(rep.corps.code, "creneau_deja_utilise_par_une_autre_video");
  assert.equal(c.net.urls.length, avant); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}));

test("YouTube succès / Instagram refuse la création du conteneur : 502, bloqué, copie conservée, relance sans aucun appel", () => avec(async (c) => {
  c.net.ig.mode = "creation_http_error";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(rep.corps.etat, "reconciliation_requise");
  assert.equal(rep.corps.youtube.success, true); assert.equal(rep.corps.instagram.success, false);
  assert.equal(statut(c), "needs_reconciliation");
  assert.deepEqual(obs(c), { youtube: ["reported_success", rep.corps.youtube.remote_id], instagram: ["needs_reconciliation", null] });
  assert.equal(traces(c)["instagram/failure_class"], "definitive_pre_publish");
  assert.deepEqual(c.env.VIDEO_BUCKET.cles(), [CLE(sha256(V))], "copie conservée pour la vérification");
  for (let i = 0; i < 3; i++) assert.equal((await envoyer(worker, c.env, req())).corps.code, "reconciliation_requise");
  assert.deepEqual(appels(c), [1, 1, 0]); assert.deepEqual(publies(c), [1, 0]);
}));

test("YouTube succès / Instagram : réponse de publication PERDUE après publication réelle : bloqué, jamais republié", () => avec(async (c) => {
  c.net.ig.mode = "perdu_apres_publication";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(rep.corps.instagram.success, false);
  assert.deepEqual(publies(c), [1, 1], "Instagram a bien publié, le Worker l'ignore");
  assert.equal(traces(c)["instagram/instagram_container"], "c-1", "le conteneur est tracé pour la vérification");
  assert.equal(traces(c)["instagram/failure_class"], "uncertain");
  c.net.ig.mode = "ok";
  assert.equal((await envoyer(worker, c.env, req())).statut, 409);
  assert.deepEqual(publies(c), [1, 1]);
}));

test("YouTube succès / Instagram jamais prêt (délai) : media_publish jamais appelé, tracé comme échec avant publication", () => avec(async (c) => {
  c.net.ig.mode = "jamais_pret";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(c.net.appels.instagram_publish, 0);
  assert.equal(traces(c)["instagram/failure_class"], "definitive_pre_publish");
  assert.equal(traces(c)["instagram/instagram_container"], "c-1");
}));

test("YouTube refuse : Instagram n'est PAS tenté, créneau bloqué", () => avec(async (c) => {
  c.net.yt.mode = "http_error";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(rep.corps.instagram.tentee, false);
  assert.deepEqual(appels(c), [1, 0, 0]); assert.equal(statut(c), "needs_reconciliation");
  assert.equal(traces(c)["youtube/failure_class"], "uncertain");
  assert.equal((await envoyer(worker, c.env, req())).statut, 409); assert.deepEqual(appels(c), [1, 0, 0]);
}));

test("YouTube : réponse perdue après publication réelle : Instagram non tenté, jamais republié", () => avec(async (c) => {
  c.net.yt.mode = "perdu_apres_publication";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.deepEqual(publies(c), [1, 0]); assert.deepEqual(appels(c), [1, 0, 0]);
  c.net.yt.mode = "ok";
  assert.equal((await envoyer(worker, c.env, req())).statut, 409); assert.deepEqual(publies(c), [1, 0]);
}));

test("YouTube répond 200 sans identifiant de vidéo : ce n'est PAS un succès (bloqué, Instagram non tenté)", () => avec(async (c) => {
  c.net.yt.mode = "ok_sans_identifiant";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(rep.corps.youtube.success, false); assert.equal(rep.corps.youtube.remote_id, null);
  assert.deepEqual(obs(c), { youtube: ["needs_reconciliation", null] }); assert.deepEqual(appels(c), [1, 0, 0]);
}));

test("jeton YouTube absent : échec avant envoi tracé comme tel, Instagram non tenté", () => avec(async (c) => {
  c.env.CONFIG_KV.m.delete("youtube_refresh_token_carburant");
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.deepEqual(appels(c), [0, 0, 0]);
  assert.equal(traces(c)["youtube/failure_class"], "definitive_pre_publish");
}));

test("crash PENDANT l'appel YouTube (processus tué) : relance bloquée, balayage -> à réconcilier, aucune republication", () => avec(async (c) => {
  c.net.yt.mode = "suspendre_apres_publication";
  envoyer(worker, c.env, req());                                // jamais résolue : le processus est « mort »
  await attendre(() => c.net.publie.youtube.length === 1);
  assert.equal((await envoyer(worker, c.env, req())).corps.code, "creneau_en_cours");
  assert.deepEqual(publies(c), [1, 0]);
  await apresVieillissement(c, () => c.planifie());
  assert.equal(statut(c), "needs_reconciliation"); assert.deepEqual(obs(c), { youtube: ["needs_reconciliation", null] });
  assert.equal((await envoyer(worker, c.env, req())).corps.code, "reconciliation_requise");
  assert.deepEqual(publies(c), [1, 0]); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), [CLE(sha256(V))]);
}));

test("crash entre YouTube enregistré et Instagram : balayage -> à réconcilier, YouTube reste confirmé", () => avec(async (c) => {
  c.net.ig.mode = "suspendre_avant_creation";
  envoyer(worker, c.env, req());
  await attendre(() => c.net.appels.instagram_creation === 1);
  await apresVieillissement(c, () => c.planifie());
  assert.equal(statut(c), "needs_reconciliation");
  assert.deepEqual(obs(c), { youtube: ["reported_success", c.net.publie.youtube[0].id], instagram: ["needs_reconciliation", null] });
  assert.equal((await envoyer(worker, c.env, req())).statut, 409); assert.deepEqual(publies(c), [1, 0]);
}));

test("crash après les DEUX succès enregistrés, avant « complet » : le balayage complète et supprime la copie", () => avec(async (c) => {
  c.env.DB_VIDEO.injecter(/status = 'reported_complete'/, "suspendre");
  envoyer(worker, c.env, req());
  await attendre(() => (obs(c).instagram || [])[0] === "reported_success");
  assert.equal(statut(c), "upload_started");
  assert.equal((await envoyer(worker, c.env, req())).corps.code, "creneau_en_cours");
  await apresVieillissement(c, () => c.planifie());
  assert.equal(statut(c), "reported_complete"); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 200); assert.equal(rep.corps.rejoue, true); assert.deepEqual(publies(c), [1, 1]);
}));

test("erreur D1 à l'écriture de « complet » : bloqué (jamais faussement complet), puis clôture par le propriétaire", () => avec(async (c) => {
  c.env.DB_VIDEO.injecter(/status = 'reported_complete'/, "erreur");
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(statut(c), "needs_reconciliation");
  assert.equal((await admin(c, "resolve", { slot_id: SLOT, resolution: "completed_by_evidence", confirm: true })).statut, 200);
  const rejeu = await envoyer(worker, c.env, req());
  assert.equal(rejeu.statut, 200); assert.equal(rejeu.corps.rejoue, true); assert.deepEqual(publies(c), [1, 1]);
}));

test("balayage pendant un envoi lent : le succès non enregistré est RENVOYÉ avec son identifiant, rien d'autre n'est tenté", () => avec(async (c) => {
  c.net.yt.avant = async () => { await apresVieillissement(c, () => c.planifie()); };
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(rep.corps.youtube.success, true); assert.equal(rep.corps.youtube.enregistre, false);
  assert.match(rep.corps.youtube.remote_id, /^yt-/); assert.deepEqual(appels(c), [1, 0, 0]);
  assert.equal(statut(c), "needs_reconciliation");
}));

test("20 envois simultanés identiques : UNE seule publication par plateforme", () => avec(async (c) => {
  c.net.yt.delai = 20; c.net.ig.delai = 10;
  const rep = await Promise.all(Array.from({ length: 20 }, () => envoyer(worker, c.env, req())));
  const gagnants = rep.filter((r) => r.statut === 200 && !r.corps.rejoue);
  assert.equal(gagnants.length, 1);
  for (const r of rep) assert.ok(r.statut === 409 ? r.corps.code === "creneau_en_cours" : r.statut === 200, JSON.stringify(r.corps));
  assert.deepEqual(appels(c), [1, 1, 1]); assert.deepEqual(publies(c), [1, 1]);
  assert.equal(statut(c), "reported_complete"); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}));

test("20 envois simultanés, YouTube succès / Instagram refusé : un 502, dix-neuf 409, une publication YouTube", () => avec(async (c) => {
  c.net.yt.delai = 20; c.net.ig.mode = "creation_http_error";
  const rep = await Promise.all(Array.from({ length: 20 }, () => envoyer(worker, c.env, req())));
  assert.deepEqual(rep.map((r) => r.statut).sort(), [...Array(19).fill(409), 502]);
  assert.deepEqual(appels(c), [1, 1, 0]); assert.deepEqual(publies(c), [1, 0]); assert.equal(statut(c), "needs_reconciliation");
}));

test("20 envois simultanés, YouTube succès / Instagram : réponse perdue : une seule publication Instagram", () => avec(async (c) => {
  c.net.yt.delai = 20; c.net.ig.mode = "perdu_apres_publication";
  const rep = await Promise.all(Array.from({ length: 20 }, () => envoyer(worker, c.env, req())));
  assert.deepEqual(rep.map((r) => r.statut).sort(), [...Array(19).fill(409), 502]);
  assert.deepEqual(publies(c), [1, 1]);
}));

test("20 vidéos DIFFÉRENTES pour le même créneau : une seule gagne, aucune copie orpheline des autres", () => avec(async (c) => {
  c.net.yt.delai = 20;
  const videos = Array.from({ length: 20 }, (_, i) => video("V" + i));
  const rep = await Promise.all(videos.map((v) => envoyer(worker, c.env, req(v))));
  const gagnants = rep.filter((r) => r.statut === 200 && !r.corps.rejoue);
  assert.equal(gagnants.length, 1); assert.deepEqual(publies(c), [1, 1]);
  assert.equal(c.net.publie.youtube[0].sha, c.net.publie.instagram[0].sha);
  assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}));

test("réconciliation : preuves et clôture refusées si elles ne sont pas justifiées, acceptées sinon, puis rejeu en lecture seule", () => avec(async (c) => {
  c.net.ig.mode = "perdu_apres_publication";
  await envoyer(worker, c.env, req());
  assert.equal((await admin(c, "status?slot_id=" + SLOT, null, "mauvaise")).statut, 403);
  const etat = await admin(c, "status?slot_id=" + SLOT);
  assert.equal(etat.corps.reservation.status, "needs_reconciliation"); assert.equal(etat.corps.copie_r2, CLE(sha256(V)));
  const preuve = (o) => admin(c, "evidence", { slot_id: SLOT, confirm: true, ...o });
  assert.equal((await admin(c, "evidence", { slot_id: SLOT, platform: "instagram", outcome: "absent", proof_kind: "owner_manual_check" })).corps.code, "confirm_requis");
  assert.equal((await preuve({ platform: "instagram", outcome: "published", proof_kind: "remote_lookup" })).statut, 400, "identifiant distant requis");
  assert.equal((await preuve({ platform: "youtube", outcome: "absent", proof_kind: "owner_manual_check" })).corps.code, "preuve_refusee", "YouTube est déjà confirmé");
  assert.equal((await preuve({ platform: "instagram", outcome: "absent", proof_kind: "worker_pre_publish" })).corps.code, "preuve_refusee", "pas de trace d'échec avant envoi");
  assert.equal((await admin(c, "resolve", { slot_id: SLOT, resolution: "completed_by_evidence", confirm: true })).corps.code, "decision_refusee");
  assert.equal((await preuve({ platform: "instagram", outcome: "published", remote_id: "ig-verifie", proof_kind: "remote_lookup" })).statut, 200);
  assert.equal((await admin(c, "resolve", { slot_id: SLOT, resolution: "closed_nothing_published", confirm: true })).corps.code, "decision_refusee");
  assert.equal((await admin(c, "resolve", { slot_id: SLOT, resolution: "completed_by_evidence", confirm: true })).statut, 200);
  assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
  const avant = c.net.urls.length;
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 200); assert.equal(rep.corps.rejoue, true); assert.equal(rep.corps.instagram.remote_id, "ig-verifie");
  assert.equal(c.net.urls.length, avant);
}));

test("clôture sans publication prouvée : le créneau reste clos, jamais rouvert automatiquement", () => avec(async (c) => {
  c.env.CONFIG_KV.m.delete("youtube_refresh_token_carburant");
  await envoyer(worker, c.env, req());
  const ev = await admin(c, "evidence", { slot_id: SLOT, platform: "youtube", outcome: "absent", proof_kind: "worker_pre_publish", confirm: true });
  assert.equal(ev.statut, 200);
  assert.equal((await admin(c, "resolve", { slot_id: SLOT, resolution: "closed_nothing_published", confirm: true })).statut, 200);
  c.env.CONFIG_KV.m.set("youtube_refresh_token_carburant", "rt-c");
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 409); assert.equal(rep.corps.code, "creneau_clos_sans_publication");
  assert.deepEqual(appels(c), [0, 0, 0]);
}));

test("transition : ancien générateur sans slot_id/sha256 accepté UNIQUEMENT avec ALLOW_LEGACY_CLIENT=1, créneau déduit (Paris)", () => avec(async (c) => {
  const sans = () => requeteApi({ octets: V });
  assert.equal((await envoyer(worker, c.env, sans())).corps.code, "slot_id_requis");
  c.env.ALLOW_LEGACY_CLIENT = "1";
  const r1 = await envoyer(worker, c.env, sans());
  assert.equal(r1.statut, 200); assert.equal(r1.corps.slot_id_derive, true); assert.match(r1.corps.slot_id, /^\d{4}-\d{2}-\d{2}:(matin|soir)$/);
  const r2 = await envoyer(worker, c.env, sans());
  assert.ok(r2.statut === 200 && r2.corps.rejoue === true); assert.deepEqual(publies(c), [1, 1], "un 2e envoi du même créneau ne republie pas");
}));

test("schéma 0001 seul (0002 non appliqué) : le protocole fonctionne, les traces sont ignorées", () => avec(async (c) => {
  c.net.ig.mode = "creation_http_error";
  const rep = await envoyer(worker, c.env, req());
  assert.equal(rep.statut, 502); assert.equal(statut(c), "needs_reconciliation");
  assert.equal((await envoyer(worker, c.env, req())).corps.code, "reconciliation_requise");
}, { env: { DB_VIDEO: new D1Shim([SQL_0001]) } }));

test("LEDGER_MODE=off (retour arrière) : chemin historique, SANS protection anti-doublon, mais clé unique et publication explicite", () => avec(async (c) => {
  c.env.LEDGER_MODE = "off";
  await envoyer(worker, c.env, req()); await envoyer(worker, c.env, req());
  assert.deepEqual(publies(c), [2, 2]); assert.deepEqual(c.env.VIDEO_BUCKET.cles(), []);
}));

test("publication d'un autre profil : deux envois simultanés publient CHACUN leur vidéo (plus d'écrasement de clé)", () => avec(async (c) => {
  c.net.yt.delai = 20;
  const [A, B] = [video("A"), video("B")];
  await Promise.all([A, B].map((v) => envoyer(worker, c.env, requeteApi({ octets: v, profil: "default" }))));
  assert.deepEqual(c.net.publie.youtube.map((p) => p.sha).sort(), [sha256(A), sha256(B)].sort());
  assert.deepEqual(c.net.publie.instagram.map((p) => p.sha).sort(), [sha256(A), sha256(B)].sort());
}));

test("page humaine et /run n'utilisent jamais une copie du journal : la vidéo envoyée est celle publiée", () => avec(async (c) => {
  c.net.ig.mode = "creation_http_error";
  await envoyer(worker, c.env, req());                         // laisse la copie du créneau (à réconcilier)
  assert.equal(c.env.VIDEO_BUCKET.cles().length, 1);
  const B = video("B"); c.net.ig.mode = "ok";
  const fd = new FormData(); fd.set("password", "mdp-test"); fd.set("profile", "carburant"); fd.set("video", new File([B], "v.mp4", { type: "video/mp4" }));
  await worker.fetch(new Request("https://video-automation.test/upload-file", { method: "POST", body: fd }), c.env);
  assert.equal(c.net.publie.youtube.at(-1).sha, sha256(B));
  assert.equal(c.net.publie.instagram.at(-1).sha, sha256(B));
  const avant = publies(c);
  const run = await envoyer(worker, c.env, new Request("https://video-automation.test/run?profile=carburant&key=mdp-test"));
  assert.match(run.corps.error, /Aucun fichier/); assert.deepEqual(publies(c), avant);
  assert.deepEqual(c.env.VIDEO_BUCKET.cles(), [CLE(sha256(V))], "la copie du créneau bloqué est toujours là");
}));
