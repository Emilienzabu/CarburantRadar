// Vérification EXÉCUTABLE des six constats de ChatGPT sur la baseline reconstruite depuis WORKER.pdf
// (baseline/index.pdf-2026-11-08.js, code NON modifié). Chaque test PASSE quand le risque EST présent dans ce code.
// Cela confirme le code du PDF, pas la version réellement déployée sur Cloudflare (non vérifiable ici).
import test from "node:test";
import assert from "node:assert/strict";
import baseline from "../baseline/index.pdf-2026-11-08.js";
import { contexte, envoyer, requeteApi, sha256, video, dormir } from "./harness.mjs";

const SLOT = "2026-11-07:matin";
const CLE_FIXE = "carburant/video-du-jour.mp4";

test("CONSTAT 1 - aucune réservation durable : le même créneau est publié deux fois", async () => {
  const c = contexte(baseline, {}, { d1: false });
  try {
    const v = video("A");
    const r1 = await envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }));
    const r2 = await envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }));
    assert.equal(r1.statut, 200); assert.equal(r2.statut, 200);
    assert.equal(c.net.publie.youtube.length, 2, "YouTube a reçu deux publications du même créneau");
    assert.equal(c.net.publie.instagram.length, 2);
    assert.ok(!("DB_VIDEO" in c.env), "le code n'utilise aucun binding D1");
  } finally { c.fin(); }
});

test("CONSTAT 1b - 20 envois simultanés : plusieurs publications du même créneau", async () => {
  const c = contexte(baseline, {}, { d1: false });
  c.net.yt.delai = 15;
  try {
    const v = video("A");
    await Promise.all(Array.from({ length: 20 }, () => envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }))));
    assert.ok(c.net.publie.youtube.length > 1, `publications YouTube : ${c.net.publie.youtube.length}`);
  } finally { c.fin(); }
});

test("CONSTAT 2 - clé R2 fixe : un 2e envoi écrase la vidéo qu'Instagram va chercher (YouTube et Instagram reçoivent deux vidéos différentes)", async () => {
  const c = contexte(baseline, {}, { d1: false });
  const A = video("A"), B = video("B");
  // un 2e /api/upload commence toujours par écrire la même clé : on reproduit ce premier geste pendant le traitement de A
  c.net.ig.apresCreation = async () => { await c.env.VIDEO_BUCKET.put(CLE_FIXE, B); };
  try {
    await envoyer(baseline, c.env, requeteApi({ octets: A, slot: SLOT, sha: sha256(A) }));
    assert.equal(c.net.publie.youtube[0].sha, sha256(A));
    assert.equal(c.net.publie.instagram[0].sha, sha256(B));
    assert.notEqual(c.net.publie.youtube[0].sha, c.net.publie.instagram[0].sha);
  } finally { c.fin(); }
});

test("CONSTAT 3 - sélection par listing : un fichier résiduel est publié à la place de la vidéo envoyée", async () => {
  const c = contexte(baseline, {}, { d1: false });
  const ancien = video("ANCIEN"), A = video("A");
  await c.env.VIDEO_BUCKET.put("carburant/a-ancien.mp4", ancien);
  try {
    await envoyer(baseline, c.env, requeteApi({ octets: A, slot: SLOT, sha: sha256(A) }));
    assert.equal(c.net.publie.youtube[0].sha, sha256(ancien), "la vidéo envoyée n'est pas celle publiée");
    assert.notEqual(c.net.publie.youtube[0].sha, sha256(A));
  } finally { c.fin(); }
});

test("CONSTAT 4 - le fichier est supprimé même quand les deux publications échouent", async () => {
  const c = contexte(baseline, {}, { d1: false });
  c.net.yt.mode = "http_error"; c.net.ig.mode = "creation_http_error";
  try {
    const v = video("A");
    const r = await envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }));
    assert.equal(r.statut, 502);
    assert.deepEqual(c.env.VIDEO_BUCKET.cles(), [], "plus aucun fichier : ni reprise ni vérification possibles");
  } finally { c.fin(); }
});

test("CONSTAT 5 - HTTP 200 alors qu'une seule plateforme a réussi", async () => {
  const c = contexte(baseline, {}, { d1: false });
  c.net.ig.mode = "creation_http_error";
  try {
    const v = video("A");
    const r = await envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }));
    assert.equal(r.corps.youtube.success, true);
    assert.ok(!r.corps.instagram.success);
    assert.equal(r.statut, 200);
  } finally { c.fin(); }
});

test("CONSTAT 6 - aucune trace durable après un résultat incertain : rien ne bloque la relance", async () => {
  const c = contexte(baseline, {}, { d1: false });
  c.net.ig.mode = "perdu_apres_publication";   // Instagram a publié, la réponse est perdue
  try {
    const v = video("A");
    await envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }));
    assert.equal(c.net.publie.instagram.length, 1);
    const kvAvant = JSON.stringify([...c.env.CONFIG_KV.m.entries()]);
    c.net.ig.mode = "ok";
    await envoyer(baseline, c.env, requeteApi({ octets: v, slot: SLOT, sha: sha256(v) }));
    assert.equal(c.net.publie.instagram.length, 2, "Instagram publié une 2e fois : doublon");
    assert.equal(JSON.stringify([...c.env.CONFIG_KV.m.entries()]), kvAvant, "KV inchangé : aucun journal du créneau");
  } finally { c.fin(); }
});

test("CONSTAT bonus - /media/ sert n'importe quelle clé du bucket sans authentification", async () => {
  const c = contexte(baseline, {}, { d1: false });
  try {
    await c.env.VIDEO_BUCKET.put("secret-autre-compte.mp4", video("PRIVE"));
    const r = await baseline.fetch(new Request("https://video-automation.test/media/secret-autre-compte.mp4"), c.env);
    assert.equal(r.status, 200);
  } finally { c.fin(); }
});
