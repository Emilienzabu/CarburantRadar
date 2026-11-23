// src/index.js : version multi-comptes + journal anti-doublon (CANDIDAT : non déployé, à relire avant tout déploiement)
// MODIFIÉ par rapport à la version reconstruite depuis WORKER.pdf (voir workers/video-automation/README.md ; diff -u baseline/index.pdf-2026-11-08.js src/index.js) :
// - profil "carburant" via POST /api/upload : protocole slot_id + sha256 avec journal D1 (binding DB_VIDEO), cf. section « Journal anti-doublon »
// - publishVideo reçoit une clé R2 explicite (plus de choix par listing quand la clé est connue)
// - routes /ledger/* (propriétaire) et balayage des créneaux interrompus dans scheduled
// - "default" = ton compte actuel (comportement inchangé)
// - "carburant" = les 2 nouveaux comptes (YouTube + Instagram) de CarburantRadar
// - POST /api/upload : envoi automatique (robot), protégé par la clé API_KEY
// - /run, /oauth/start et /instagram/init-token demandent maintenant ?key=TON_UPLOAD_PASSWORD
const PROFILES = {
default: {
 title: ".",
 description:
 "Si tu te reconnais dans cette vidéo, ce compte peut t'aider. #viral #fyp #pourtoi #relashionship #depression #men #debate #opinion #tromperie #amour",
 tags: [
 "viral", "fyp", "pourtoi", "relashionship", "depression",
 "men", "debate", "opinion", "tromperie", "amour"
 ],
 caption:
 "Si tu te reconnais dans cette vidéo, ce compte peut t'aider. #viral #fyp #relashionship #tromperie #amour",
 categoryId: "22",
 ytKvKey: "youtube_refresh_token",
 ytEnvRefresh: "YOUTUBE_REFRESH_TOKEN",
 igKvKey: "instagram_token",
 igAccountVar: "INSTAGRAM_ACCOUNT_ID",
 prefix: ""
},
carburant: {
 title: "Le carburant le moins cher près de chez toi | CarburantRadar",
 description:
 "Compare les prix du carburant près de chez toi, gratuitement et sans compte : https://carburantradar.fr #Shorts #carburant #essence #diesel #economies",
 tags: ["carburant", "essence", "diesel", "prix carburant", "économies", "CarburantRadar"],
 caption:
 "Compare les prix près de chez toi : carburantradar.fr (lien en bio) #carburant #essence #diesel #economies",
 categoryId: "2",
 ytKvKey: "youtube_refresh_token_carburant",
 ytEnvRefresh: null,
 igKvKey: "instagram_token_carburant",
 igAccountVar: "INSTAGRAM_ACCOUNT_ID_CARBURANT",
 prefix: "carburant/"
}
};
const VIDEO_FILE = "video-du-jour.mp4";
function getProfile(name) {
return Object.prototype.hasOwnProperty.call(PROFILES, name) ? PROFILES[name] : null;
}
function videoKeyFor(profile) {
return profile.prefix + VIDEO_FILE;
}
function isOwner(url, env) {
const key = url.searchParams.get("key");
return !!env.UPLOAD_PASSWORD && key === env.UPLOAD_PASSWORD;
}
function jsonResponse(obj, status = 200) {
return new Response(JSON.stringify(obj, null, 2), {
 status,
 headers: { "content-type": "application/json" }
});
}
function denied() {
return new Response("Accès refusé : ajoute ?key=TON_MOT_DE_PASSE à l'URL.", { status: 403 });
}
function uploadPageHtml(error) {
return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload vidéo</title>
<style>
 body { font-family: system-ui, sans-serif; max-width: 420px; margin: 40px auto; padding: 0 16px; }
 input, select, button { width: 100%; padding: 12px; margin-top: 12px; font-size: 16px; box-sizing: border-box; }
 button { background: #2563eb; color: white; border: none; border-radius: 8px; font-weight: 600; }
 button:disabled { background: #93c5fd; }
 .error { color: #dc2626; margin-top: 10px; }
 .info { color: #555; font-size: 14px; margin-top: 16px; }
 .progress-wrap { display: none; margin-top: 16px; }
 .progress-bar-bg { background: #e5e7eb; border-radius: 8px; height: 18px; overflow: hidden; }
 .progress-bar-fill { background: #2563eb; height: 100%; width: 0%; transition: width 0.2s; }
 .progress-label { font-size: 14px; color: #333; margin-top: 6px; text-align: center; }
</style>
</head>
<body>
<h2>Envoyer la vidéo du jour</h2>
<form id="uploadForm">
 <input type="password" name="password" id="password" placeholder="Mot de passe" required>
 <select name="profile" id="profile">
 <option value="default">Compte actuel</option>
 <option value="carburant">CarburantRadar</option>
 </select>
 <input type="file" name="video" id="video" accept="video/*" required>
 <button type="submit" id="submitBtn">Envoyer</button>
</form>
<div class="progress-wrap" id="progressWrap">
 <div class="progress-bar-bg">
 <div class="progress-bar-fill" id="progressFill"></div>
 </div>
 <div class="progress-label" id="progressLabel">Envoi : 0%</div>
</div>
${error ? `<p class="error">${error}</p>` : ""}
<p class="info">La vidéo sera publiée immédiatement après l'envoi.</p>
<script>
 const form = document.getElementById('uploadForm');
 const progressWrap = document.getElementById('progressWrap');
 const progressFill = document.getElementById('progressFill');
 const progressLabel = document.getElementById('progressLabel');
 const submitBtn = document.getElementById('submitBtn');
 form.addEventListener('submit', function (e) {
 e.preventDefault();
 const formData = new FormData(form);
 const xhr = new XMLHttpRequest();
 submitBtn.disabled = true;
 progressWrap.style.display = 'block';
 xhr.upload.addEventListener('progress', function (event) {
 if (event.lengthComputable) {
 const percent = Math.round((event.loaded / event.total) * 100);
 progressFill.style.width = percent + '%'; progressLabel.textContent = 'Envoi : ' + percent + '%';
 }
 });
 xhr.upload.addEventListener('load', function () {
 progressFill.style.width = '100%';
 progressLabel.textContent = 'Publication sur YouTube et Instagram en cours...';
 });
 xhr.onload = function () {
 document.open();
 document.write(xhr.responseText);
 document.close();
 };
 xhr.onerror = function () {
 progressLabel.textContent = 'Erreur réseau pendant l\\'envoi.';
 submitBtn.disabled = false;
 };
 xhr.open('POST', '/upload-file');
 xhr.send(formData);
 });
<\/script>
</body>
</html>`;
}
function homePageHtml() {
return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>automatisation video</title>
<style>
 body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; line-height: 1.6; color: #222; }
 h1 { font-size: 1.5rem; }
 a { color: #2563eb; }
</style>
</head>
<body>
<h1>automatisation video</h1>
<p>Cette application est un outil personnel qui automatise la publication de vidéos sur YouTube et Instagram pour le compte de son propriétaire.</p>
<p>Elle n'est pas ouverte au public : elle sert uniquement à connecter les comptes YouTube et Instagram appartenant à l'auteur de l'application, afin de publier automatiquement du contenu qu'il dépose lui-même.</p>
<p>
 <a href="/privacy">Politique de confidentialité</a> ·
 <a href="/terms">Conditions d'utilisation</a>
</p>
</body>
</html>`;
}
function privacyPolicyHtml() {
return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Politique de confidentialité</title>
<style>
 body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; line-height: 1.6; color: #222; }
 h1 { font-size: 1.5rem; }
</style>
</head>
<body>
<h1>Politique de confidentialité</h1>
<p>Cette application ("video-automation") est un outil à usage strictement personnel, utilisé uniquement par son propriétaire pour automatiser la publication de ses propres vidéos sur YouTube et Instagram.</p>
<p>Elle n'est pas destinée au grand public et ne collecte, ne stocke ni ne partage aucune donnée personnelle appartenant à des tiers. Les seules données traitées sont :</p>
<ul>
 <li>Les fichiers vidéo déposés par le propriétaire de l'application, transmis directement aux plateformes YouTube et Instagram pour publication ;</li>
 <li>Les jetons d'authentification OAuth nécessaires à la connexion aux comptes YouTube et Instagram du propriétaire, stockés de façon sécurisée et jamais partagés avec des tiers.</li>
</ul>
<p>Aucune donnée n'est vendue, louée ou transmise à des tiers à des fins commerciales.</p>
<p>Pour toute question, contactez le propriétaire de l'application via l'adresse indiquée sur l'écran de consentement Google Cloud associé à ce projet.</p>
</body>
</html>`;
}
function termsOfServiceHtml() {
return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Conditions d'utilisation</title>
<style>
 body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; line-height: 1.6; color: #222; }
 h1 { font-size: 1.5rem; }
</style>
</head>
<body>
<h1>Conditions d'utilisation</h1>
<p>Cette application ("video-automation") est un outil personnel destiné exclusivement à automatiser la publication de vidéos sur les comptes YouTube et Instagram de son propriétaire.</p>
<p>Elle n'est pas mise à disposition du public et n'est pas destinée à être utilisée par des tiers. L'accès est limité au propriétaire de l'application.</p>
<p>L'application est fournie "telle quelle", sans garantie d'aucune sorte. Le propriétaire se réserve le droit de modifier ou d'interrompre son fonctionnement à tout moment.</p>
</body>
</html>`;
}
export default {
async fetch(request, env) {
 const url = new URL(request.url);
 if (url.pathname === "/oauth/start") {
 return handleOAuthStart(url, env);
 }
 if (url.pathname === "/oauth/callback") {
 return handleOAuthCallback(url, env);
 }
 if (url.pathname === "/privacy") {
 return new Response(privacyPolicyHtml(), {
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
 }
 if (url.pathname === "/terms") {
 return new Response(termsOfServiceHtml(), {
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
 }
 if (url.pathname === "/upload" && request.method === "GET") {
 return new Response(uploadPageHtml(), {
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
 }
 if (url.pathname === "/upload-file" && request.method === "POST") {
 return handleFileUpload(request, env);
 }
 if (url.pathname === "/api/upload" && request.method === "POST") {
 return handleApiUpload(request, env);
 }
 if (url.pathname.startsWith("/ledger/")) {
 return handleLedgerAdmin(request, url, env);
 }
 if (url.pathname === "/run") {
 if (!isOwner(url, env)) return denied();
 const profile = getProfile(url.searchParams.get("profile") || "default");
 if (!profile) return jsonResponse({ error: "Profil inconnu." }, 400);
 const result = await publishVideo(env, profile);
 return jsonResponse(result);
 }
 if (url.pathname === "/instagram/init-token") {
 return handleInstagramInitToken(url, env);
 }
 if (url.pathname.startsWith("/media/")) {
 return handleServeMedia(url, env);
 }
 return new Response(homePageHtml(), {
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
},
async scheduled(event, env, ctx) {
 ctx.waitUntil(sweepStaleSlots(env).catch((err) => console.error("Balayage du journal :", err)));
 ctx.waitUntil(publishVideo(env, PROFILES.default));
}
};
// ====================================================================================
// Journal anti-doublon (D1, binding DB_VIDEO) : protocole slot_id + sha256.
// Schéma : video/ledger/0001_video_ledger.sql puis 0002_video_ledger_evidence.sql (appliqués à la main par le propriétaire).
// Règles : réservation puis prise du créneau AVANT tout appel de plateforme ; une ligne d'observation par plateforme AVANT
// l'appel ; tout ce qui n'est pas un succès prouvé (identifiant distant) bloque le créneau (needs_reconciliation) ; si YouTube
// n'est pas confirmé, Instagram n'est PAS tenté ; AUCUNE republication automatique ; la copie R2 est conservée tant que le
// créneau n'est pas complet. Ne s'applique qu'à POST /api/upload du profil "carburant" (voir README du dossier).
// ====================================================================================
const LEDGER_PROFILE = "carburant";
const PLATFORM_NAMES = ["youtube", "instagram"];
const SLOT_RE = /^\d{4}-\d{2}-\d{2}:(matin|soir)$/;
const SHA_RE = /^[0-9a-f]{64}$/;
const MAX_VIDEO_BYTES = 64 * 1024 * 1024;
const STALE_SLOT_MS = 30 * 60 * 1000; // un créneau « upload_started » plus vieux que ça est considéré interrompu
const PROOF_KINDS = ["remote_lookup", "owner_manual_check", "worker_pre_publish"];
function slotValide(slot) {
if (typeof slot !== "string" || !SLOT_RE.test(slot)) return false;
const d = new Date(slot.slice(0, 10) + "T00:00:00Z");
return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === slot.slice(0, 10);
}
function currentSlotParis(now = new Date()) {
const parts = Object.fromEntries(
 new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23" })
 .formatToParts(now).map((p) => [p.type, p.value])
);
return `${parts.year}-${parts.month}-${parts.day}:${Number(parts.hour) < 13 ? "matin" : "soir"}`;
}
async function sha256Hex(buffer) {
const digest = await crypto.subtle.digest("SHA-256", buffer);
return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function ledgerKey(slot, sha) {
return `${LEDGER_PROFILE}/${slot.replace(":", "_")}/${sha}.mp4`;
}
const isoNow = () => new Date().toISOString();
async function dbRun(db, sql, ...args) {
const r = await db.prepare(sql).bind(...args).run();
return r && r.meta ? r.meta.changes : 0;
}
async function dbFirst(db, sql, ...args) {
return db.prepare(sql).bind(...args).first();
}
async function dbAll(db, sql, ...args) {
const r = await db.prepare(sql).bind(...args).all();
return (r && r.results) || [];
}
async function dbRevision(db, slot) {
const r = await dbFirst(db, "SELECT revision FROM video_slot_reservations WHERE slot_key = ?1", slot);
return r ? r.revision : null;
}
const BLOCK_MESSAGES = {
creneau_en_cours: "Ce créneau est en cours de traitement ou a été interrompu : aucune nouvelle publication.",
reconciliation_requise: "Ce créneau a une issue incertaine : vérifie les comptes puis ajoute les preuves (/ledger/*). Aucune republication automatique.",
creneau_clos_sans_publication: "Ce créneau a été clos sans publication prouvée : il ne sera pas rouvert automatiquement.",
creneau_deja_utilise_par_une_autre_video: "Ce créneau est déjà réservé pour une autre vidéo (empreinte différente)."
};
function ledgerBlocked(slot, sha, code) {
return jsonResponse({ error: BLOCK_MESSAGES[code], code, etat: "bloque", slot_id: slot, sha256: sha }, 409);
}
function ledgerRefused(code, message, status, extra = {}) {
// « refuse » = la requête a été arrêtée AVANT toute publication : rien n'a été envoyé aux plateformes
return jsonResponse({ error: message, code, etat: "refuse", ...extra }, status);
}
async function ledgerReplayBody(db, slot, sha) {
const ids = {};
for (const r of await dbAll(db, "SELECT platform, status, remote_id FROM video_platform_results WHERE slot_key = ?1", slot)) {
 if (r.status === "reported_success") ids[r.platform] = r.remote_id;
}
try {
 for (const e of await dbAll(db, "SELECT platform, outcome, remote_id FROM video_reconciliation_evidence WHERE slot_key = ?1", slot)) {
 if (e.outcome === "published" && !ids[e.platform]) ids[e.platform] = e.remote_id;
 }
} catch (_) { /* 0002 non appliqué */ }
return {
 slot_id: slot, sha256: sha, etat: "complet", rejoue: true,
 youtube: ids.youtube ? { success: true, remote_id: ids.youtube, videoId: ids.youtube, url: `https://youtu.be/${ids.youtube}` } : { success: false },
 instagram: ids.instagram ? { success: true, remote_id: ids.instagram, mediaId: ids.instagram } : { success: false }
};
}
async function ledgerRef(db, slot, platform, kind, value) {
// trace facultative (table 0002) : n'empêche jamais la publication ni la réponse
try {
 await dbRun(db, "INSERT INTO video_attempt_refs(slot_key, platform, ref_kind, ref_value, recorded_at) VALUES (?1, ?2, ?3, ?4, ?5)", slot, platform, kind, String(value).slice(0, 200), isoNow());
} catch (_) { /* déjà notée, ou 0002 absent */ }
}
async function ledgerFailureRefs(db, slot, platform, sortie) {
const classe = sortie && sortie.stage === "pre_publish" ? "definitive_pre_publish" : "uncertain";
await ledgerRef(db, slot, platform, "failure_class", classe);
if (sortie && sortie.stage) await ledgerRef(db, slot, platform, "failure_stage", sortie.stage);
if (sortie && sortie.httpStatus) await ledgerRef(db, slot, platform, "http_status", sortie.httpStatus);
}
async function ledgerRecord(db, slot, platform, ok, remoteId) {
try {
 const n = await dbRun(
 db,
 "UPDATE video_platform_results SET status = ?1, remote_id = ?2, expected_revision = ?3, updated_at = ?4 WHERE slot_key = ?5 AND platform = ?6 AND status = 'upload_started'",
 ok ? "reported_success" : "needs_reconciliation", ok ? remoteId : null, await dbRevision(db, slot), isoNow(), slot, platform
 );
 return n === 1;
} catch (_) {
 return false;
}
}
async function handleLedgerUpload(env, profile, formData, file, custom) {
const db = env.DB_VIDEO;
if (!db) {
 return ledgerRefused("ledger_non_configure", "Journal anti-doublon non configuré (binding D1 DB_VIDEO manquant) : rien n'est publié.", 503);
}
const legacyOk = env.ALLOW_LEGACY_CLIENT === "1"; // transition : ancien générateur sans slot_id / sha256
let slot = formData.get("slot_id");
let derived = false;
if (typeof slot !== "string" || !slot.trim()) {
 if (!legacyOk) return ledgerRefused("slot_id_requis", "Champ slot_id requis (AAAA-MM-JJ:matin|soir).", 400);
 slot = currentSlotParis();
 derived = true;
}
slot = slot.trim();
if (!slotValide(slot)) return ledgerRefused("slot_id_invalide", "slot_id invalide (AAAA-MM-JJ:matin|soir, date réelle).", 400);
if (file.size > MAX_VIDEO_BYTES) return ledgerRefused("video_trop_volumineuse", "Vidéo trop volumineuse.", 413, { slot_id: slot });
const bytes = await file.arrayBuffer();
const sha = await sha256Hex(bytes);
const declared = formData.get("sha256");
if (typeof declared === "string" && declared.trim()) {
 if (!SHA_RE.test(declared.trim())) return ledgerRefused("sha256_invalide", "sha256 invalide (64 caractères hexadécimaux minuscules).", 400, { slot_id: slot });
 if (declared.trim() !== sha) return ledgerRefused("sha256_different_du_contenu", "Le sha256 déclaré ne correspond pas au fichier reçu.", 400, { slot_id: slot });
} else if (!legacyOk) {
 return ledgerRefused("sha256_requis", "Champ sha256 requis.", 400, { slot_id: slot });
}
let engage = false; // devient vrai dès que ce créneau nous appartient : une exception ensuite est INCERTAINE
try {
 const t0 = isoNow();
 await dbRun(db, "INSERT INTO video_slot_reservations(slot_key, mp4_sha256, status, created_at, updated_at) VALUES (?1, ?2, 'reserved', ?3, ?3) ON CONFLICT(slot_key) DO NOTHING", slot, sha, t0);
 const row = await dbFirst(db, "SELECT status, mp4_sha256, revision FROM video_slot_reservations WHERE slot_key = ?1", slot);
 if (row.mp4_sha256 !== sha) return ledgerBlocked(slot, sha, "creneau_deja_utilise_par_une_autre_video");
 if (row.status === "reported_complete") return jsonResponse(await ledgerReplayBody(db, slot, sha), 200);
 if (row.status === "needs_reconciliation") {
 let decision = null;
 try { decision = await dbFirst(db, "SELECT resolution FROM video_slot_resolutions WHERE slot_key = ?1", slot); } catch (_) { /* 0002 absent */ }
 if (decision && decision.resolution === "completed_by_evidence") return jsonResponse(await ledgerReplayBody(db, slot, sha), 200);
 if (decision && decision.resolution === "closed_nothing_published") return ledgerBlocked(slot, sha, "creneau_clos_sans_publication");
 return ledgerBlocked(slot, sha, "reconciliation_requise");
 }
 if (row.status !== "reserved") return ledgerBlocked(slot, sha, "creneau_en_cours");
 // Copie durable AVANT la prise : clé unique (créneau + empreinte), jamais écrasée par une autre vidéo
 const key = ledgerKey(slot, sha);
 try {
 await env.VIDEO_BUCKET.put(key, bytes, {
  httpMetadata: { contentType: file.type || "video/mp4" },
  customMetadata: { ...custom, slot_id: slot, sha256: sha }
 });
 } catch (_) {
 return ledgerRefused("stockage_indisponible", "Stockage R2 indisponible : rien n'est publié, le créneau reste réutilisable.", 500, { slot_id: slot, sha256: sha });
 }
 const pris = await dbRun(db, "UPDATE video_slot_reservations SET status = 'upload_started', revision = revision + 1, updated_at = ?1 WHERE slot_key = ?2 AND mp4_sha256 = ?3 AND status = 'reserved' AND revision = ?4", isoNow(), slot, sha, row.revision);
 if (pris !== 1) {
 const apres = await dbFirst(db, "SELECT status FROM video_slot_reservations WHERE slot_key = ?1", slot);
 if (apres && apres.status === "reported_complete") { try { await env.VIDEO_BUCKET.delete(key); } catch (_) { /* copie orpheline */ } }
 return ledgerBlocked(slot, sha, "creneau_en_cours");
 }
 engage = true;
 const post = {
 title: custom.title || profile.title,
 description: custom.description || profile.description,
 caption: custom.caption || profile.caption,
 tags: profile.tags
 };
 const resultats = {};
 let tout = true;
 for (const nom of PLATFORM_NAMES) {
 if (!tout) {
  resultats[nom] = { success: false, tentee: false, remote_id: null, error: "Non tentée : la plateforme précédente n'est pas confirmée." };
  continue;
 }
 try {
  await dbRun(db, "INSERT INTO video_platform_results(slot_key, platform, mp4_sha256, status, updated_at) VALUES (?1, ?2, ?3, 'upload_started', ?4)", slot, nom, sha, isoNow());
 } catch (_) {
  resultats[nom] = { success: false, tentee: false, remote_id: null, error: "Observation impossible à initialiser : plateforme non tentée." };
  tout = false;
  continue;
 }
 const sortie = nom === "youtube"
  ? await uploadVideoToYouTube(env, profile, post, bytes)
  : await uploadVideoToInstagram(env, profile, post, key, { onContainer: (id) => ledgerRef(db, slot, "instagram", "instagram_container", id) });
 const remoteId = nom === "youtube" ? sortie.videoId : sortie.mediaId;
 const ok = sortie.success === true && typeof remoteId === "string" && remoteId.length > 0;
 const enregistre = await ledgerRecord(db, slot, nom, ok, remoteId);
 if (!ok) await ledgerFailureRefs(db, slot, nom, sortie);
 if (ok && !enregistre) console.error("[journal] publication NON enregistrée", slot, nom, remoteId);
 resultats[nom] = { ...sortie, success: ok, remote_id: ok ? remoteId : null, enregistre, tentee: true };
 if (!ok || !enregistre) tout = false;
 }
 let etat = "reconciliation_requise";
 if (tout) {
 try {
  const n = await dbRun(db, "UPDATE video_slot_reservations SET status = 'reported_complete', revision = revision + 1, updated_at = ?1 WHERE slot_key = ?2 AND status = 'upload_started' AND revision = ?3", isoNow(), slot, await dbRevision(db, slot));
  if (n === 1) etat = "complet";
 } catch (_) { /* on bloque ci-dessous */ }
 }
 if (etat === "complet") {
 try { await env.VIDEO_BUCKET.delete(key); } catch (_) { /* copie conservée */ }
 } else {
 try {
  await dbRun(db, "UPDATE video_slot_reservations SET status = 'needs_reconciliation', revision = revision + 1, updated_at = ?1 WHERE slot_key = ?2 AND status = 'upload_started' AND revision = ?3", isoNow(), slot, await dbRevision(db, slot));
 } catch (_) { /* le balayage terminera */ }
 }
 return jsonResponse(
 { slot_id: slot, sha256: sha, etat, rejoue: false, ...(derived ? { slot_id_derive: true } : {}), youtube: resultats.youtube, instagram: resultats.instagram },
 etat === "complet" ? 200 : 502
 );
} catch (err) {
 console.error("[journal] erreur", slot, String(err));
 return jsonResponse(
 { error: "Erreur interne du journal.", code: "erreur_interne", etat: engage ? "incertain" : "refuse", slot_id: slot, sha256: sha, details: String(err).slice(0, 200) },
 500
 );
}
}
// Créneaux interrompus (crash, coupure) : jamais de republication. Deux succès enregistrés -> complet ; sinon -> à réconcilier.
async function sweepStaleSlots(env, nowMs = Date.now()) {
const db = env.DB_VIDEO;
if (!db) return [];
const cutoff = new Date(nowMs - STALE_SLOT_MS).toISOString();
const sortie = [];
for (const { slot_key: slot, mp4_sha256: sha } of await dbAll(db, "SELECT slot_key, mp4_sha256 FROM video_slot_reservations WHERE status = 'upload_started' AND updated_at < ?1", cutoff)) {
 try {
 const t = isoNow();
 const ok = await dbFirst(db, "SELECT COUNT(*) AS n FROM video_platform_results WHERE slot_key = ?1 AND status = 'reported_success' AND remote_id IS NOT NULL", slot);
 let cible = "reported_complete";
 if (!ok || ok.n !== 2) {
  cible = "needs_reconciliation";
  for (const p of await dbAll(db, "SELECT platform FROM video_platform_results WHERE slot_key = ?1 AND status = 'upload_started'", slot)) {
  await dbRun(db, "UPDATE video_platform_results SET status = 'needs_reconciliation', expected_revision = ?1, updated_at = ?2 WHERE slot_key = ?3 AND platform = ?4 AND status = 'upload_started'", await dbRevision(db, slot), t, slot, p.platform);
  await ledgerRef(db, slot, p.platform, "failure_class", "uncertain");
  }
 }
 const n = await dbRun(db, "UPDATE video_slot_reservations SET status = ?1, revision = revision + 1, updated_at = ?2 WHERE slot_key = ?3 AND status = 'upload_started' AND revision = ?4", cible, t, slot, await dbRevision(db, slot));
 if (n === 1) {
  sortie.push({ slot_id: slot, etat: cible });
  if (cible === "reported_complete") { try { await env.VIDEO_BUCKET.delete(ledgerKey(slot, sha)); } catch (_) { /* copie conservée */ } }
 }
 } catch (err) {
 console.error("[journal] balayage impossible pour", slot, String(err));
 }
}
return sortie;
}
// Routes propriétaire (?key=UPLOAD_PASSWORD) : consulter un créneau, ajouter une preuve, clore un créneau incertain.
async function handleLedgerAdmin(request, url, env) {
if (!isOwner(url, env)) return denied();
const db = env.DB_VIDEO;
if (!db) return jsonResponse({ error: "Binding D1 DB_VIDEO manquant." }, 503);
try {
 if (url.pathname === "/ledger/status" && request.method === "GET") {
 const slot = url.searchParams.get("slot_id") || "";
 if (!slotValide(slot)) return jsonResponse({ error: "slot_id invalide." }, 400);
 const reservation = await dbFirst(db, "SELECT slot_key, mp4_sha256, status, revision, created_at, updated_at FROM video_slot_reservations WHERE slot_key = ?1", slot);
 if (!reservation) return jsonResponse({ error: "Créneau inconnu.", slot_id: slot }, 404);
 const lire = async (sql) => { try { return await dbAll(db, sql, slot); } catch (_) { return []; } };
 return jsonResponse({
  reservation,
  observations: await lire("SELECT platform, status, remote_id, updated_at FROM video_platform_results WHERE slot_key = ?1"),
  traces: await lire("SELECT platform, ref_kind, ref_value, recorded_at FROM video_attempt_refs WHERE slot_key = ?1"),
  preuves: await lire("SELECT platform, outcome, remote_id, proof_kind, note, recorded_at FROM video_reconciliation_evidence WHERE slot_key = ?1"),
  decision: (await lire("SELECT resolution, recorded_at FROM video_slot_resolutions WHERE slot_key = ?1"))[0] || null,
  copie_r2: ledgerKey(slot, reservation.mp4_sha256)
 });
 }
 if ((url.pathname === "/ledger/evidence" || url.pathname === "/ledger/resolve") && request.method === "POST") {
 const b = await request.json().catch(() => null);
 if (!b || typeof b !== "object") return jsonResponse({ error: "JSON invalide." }, 400);
 if (!slotValide(b.slot_id)) return jsonResponse({ error: "slot_id invalide." }, 400);
 if (b.confirm !== true) return jsonResponse({ error: "Ajoute \"confirm\": true : une preuve ou une décision ne peut jamais être corrigée ensuite.", code: "confirm_requis" }, 400);
 const reservation = await dbFirst(db, "SELECT mp4_sha256 FROM video_slot_reservations WHERE slot_key = ?1", b.slot_id);
 if (!reservation) return jsonResponse({ error: "Créneau inconnu." }, 404);
 if (url.pathname === "/ledger/evidence") {
  if (!PLATFORM_NAMES.includes(b.platform)) return jsonResponse({ error: "platform invalide (youtube|instagram)." }, 400);
  if (b.outcome !== "published" && b.outcome !== "absent") return jsonResponse({ error: "outcome invalide (published|absent)." }, 400);
  if (!PROOF_KINDS.includes(b.proof_kind)) return jsonResponse({ error: "proof_kind invalide.", valeurs: PROOF_KINDS }, 400);
  const remote = b.outcome === "published" ? String(b.remote_id || "").trim().slice(0, 200) : null;
  if (b.outcome === "published" && !remote) return jsonResponse({ error: "remote_id requis pour outcome=published." }, 400);
  const note = typeof b.note === "string" && b.note.trim() ? b.note.trim().slice(0, 500) : null;
  try {
  await dbRun(db, "INSERT INTO video_reconciliation_evidence(slot_key, platform, mp4_sha256, outcome, remote_id, proof_kind, note, recorded_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)", b.slot_id, b.platform, reservation.mp4_sha256, b.outcome, remote, b.proof_kind, note, isoNow());
  } catch (err) {
  return jsonResponse({ error: "Preuve refusée par le journal : " + String(err && err.message || err).slice(0, 200), code: "preuve_refusee" }, 409);
  }
  return jsonResponse({ ok: true, slot_id: b.slot_id, platform: b.platform, outcome: b.outcome });
 }
 if (b.resolution !== "completed_by_evidence" && b.resolution !== "closed_nothing_published") {
  return jsonResponse({ error: "resolution invalide (completed_by_evidence|closed_nothing_published)." }, 400);
 }
 try {
  await dbRun(db, "INSERT INTO video_slot_resolutions(slot_key, mp4_sha256, resolution, recorded_at) VALUES (?1, ?2, ?3, ?4)", b.slot_id, reservation.mp4_sha256, b.resolution, isoNow());
 } catch (err) {
  return jsonResponse({ error: "Décision refusée par le journal : " + String(err && err.message || err).slice(0, 200), code: "decision_refusee" }, 409);
 }
 if (b.resolution === "completed_by_evidence") {
  try { await env.VIDEO_BUCKET.delete(ledgerKey(b.slot_id, reservation.mp4_sha256)); } catch (_) { /* copie conservée */ }
 }
 return jsonResponse({ ok: true, slot_id: b.slot_id, resolution: b.resolution });
 }
 return jsonResponse({ error: "Route inconnue." }, 404);
} catch (err) {
 return jsonResponse({ error: "Erreur interne.", details: String(err).slice(0, 200) }, 500);
}
}
// ---------- YouTube OAuth (un token par profil) ----------
async function handleOAuthStart(url, env) {
if (!isOwner(url, env)) return denied();
const name = url.searchParams.get("profile") || "default";
if (!getProfile(name)) {
 return new Response("Profil inconnu.", { status: 400 });
}
// "state" aléatoire à usage unique : empêche un tiers de brancher sa propre chaîne YouTube
const state = crypto.randomUUID();
await env.CONFIG_KV.put("oauth_state:" + state, name, { expirationTtl: 600 });
const redirectUri = `https://video-automation.emilienzabukovec09.workers.dev/oauth/callback`;
const params = new URLSearchParams({
 client_id: env.YOUTUBE_CLIENT_ID,
 redirect_uri: redirectUri,
 response_type: "code",
 scope: "https://www.googleapis.com/auth/youtube.force-ssl",
 access_type: "offline", // nécessaire pour obtenir un refresh_token
 prompt: "consent", // force Google à renvoyer le refresh_token à chaque fois
 state
});
const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
return Response.redirect(authUrl, 302);
}
async function handleOAuthCallback(url, env) {
const code = url.searchParams.get("code");
if (!code) {
 return new Response("Erreur : pas de code reçu de Google.", { status: 400 });
}
const state = url.searchParams.get("state");
const name = state ? await env.CONFIG_KV.get("oauth_state:" + state) : null;
const profile = name ? getProfile(name) : null;
if (!profile) {
 return new Response("État OAuth invalide ou expiré. Relance /oauth/start?key=...", { status: 400 });
}
await env.CONFIG_KV.delete("oauth_state:" + state);
const redirectUri = `https://video-automation.emilienzabukovec09.workers.dev/oauth/callback`;
const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
 method: "POST",
 headers: { "content-type": "application/x-www-form-urlencoded" },
 body: new URLSearchParams({
 client_id: env.YOUTUBE_CLIENT_ID, client_secret: env.YOUTUBE_CLIENT_SECRET,
 code,
 grant_type: "authorization_code",
 redirect_uri: redirectUri
 })
});
const tokenData = await tokenRes.json();
if (!tokenData.refresh_token) {
 return new Response(
 `Pas de refresh_token reçu. Réponse Google : ${JSON.stringify(tokenData)}\n\nAstuce : révoque l'accès sur https://myaccount.google.com/permissions puis relance /oauth/start.`,
 { status: 400 }
 );
}
await env.CONFIG_KV.put(profile.ytKvKey, tokenData.refresh_token);
return new Response(
 `<!DOCTYPE html><html lang="fr"><body style="font-family: system-ui; max-width: 420px; margin: 40px auto; padding: 0 16px;">
 <h2>✅ Autorisation YouTube enregistrée (${name})</h2>
 <p>C'est bon, tu peux fermer cette page et publier une vidéo normalement.</p>
 </body></html>`,
 { headers: { "content-type": "text/html; charset=UTF-8" } }
);
}
async function getFreshAccessToken(env, profile) {
const kvToken = await env.CONFIG_KV.get(profile.ytKvKey);
const refreshToken = kvToken || (profile.ytEnvRefresh ? env[profile.ytEnvRefresh] : null);
if (!refreshToken) {
 throw new Error("Aucun token YouTube pour ce profil. Va sur /oauth/start?profile=...&key=...");
}
const res = await fetch("https://oauth2.googleapis.com/token", {
 method: "POST",
 headers: { "content-type": "application/x-www-form-urlencoded" },
 body: new URLSearchParams({
 client_id: env.YOUTUBE_CLIENT_ID,
 client_secret: env.YOUTUBE_CLIENT_SECRET,
 refresh_token: refreshToken,
 grant_type: "refresh_token"
 })
});
const data = await res.json();
if (!data.access_token) {
 throw new Error(`Impossible de rafraîchir le token : ${JSON.stringify(data)}`);
}
return data.access_token;
}
// ---------- Envoi par la page web (humain) ----------
async function handleFileUpload(request, env) {
const formData = await request.formData();
const password = formData.get("password");
const file = formData.get("video");
const profile = getProfile(String(formData.get("profile") || "default"));
if (!env.UPLOAD_PASSWORD || password !== env.UPLOAD_PASSWORD) {
 return new Response(uploadPageHtml("Mot de passe incorrect."), {
 status: 401,
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
}
if (!profile) {
 return new Response(uploadPageHtml("Profil inconnu."), {
 status: 400,
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
}
if (!file || typeof file === "string") {
 return new Response(uploadPageHtml("Aucun fichier reçu."), {
 status: 400,
 headers: { "content-type": "text/html; charset=UTF-8" }
 });
}
await env.VIDEO_BUCKET.put(videoKeyFor(profile), file.stream(), {
 httpMetadata: { contentType: file.type || "video/mp4" }
});
let result;
try {
 result = await publishVideo(env, profile, videoKeyFor(profile));
} catch (err) {
 return new Response(
 `<!DOCTYPE html><html lang="fr"><body style="font-family: system-ui; max-width: 420px; margin: 40px auto; padding: 0 16px;">
 <h2>⚠️ Erreur inattendue pendant la publication</h2>
 <p>${String(err)}</p>
 <a href="/upload">Réessayer</a>
 </body></html>`,
 { status: 200, headers: { "content-type": "text/html; charset=UTF-8" } }
 );
}
const youtubeLine = result.youtube?.success
 ? `<p>✅ YouTube : <a href="${result.youtube.url}" target="_blank">${result.youtube.url}</a></p>`
 : `<p>⚠️ YouTube a échoué : ${JSON.stringify(result.youtube?.error ?? result.error)}<br><small>${JSON.stringify(
 result.youtube?.details
 )}</small></p>`;
const instagramLine = result.instagram?.success
 ? `<p>✅ Instagram : publié</p>`
 : `<p>⚠️ Instagram a échoué : ${JSON.stringify(result.instagram?.error ?? result.error)}<br><small>${JSON.stringify(
 result.instagram?.details
 )}</small></p>`;
return new Response(
 `<!DOCTYPE html><html lang="fr"><body style="font-family: system-ui; max-width: 420px; margin: 40px auto; padding: 0 16px;">
 <h2>Résultat de la publication</h2>
 ${youtubeLine}
 ${instagramLine}
 <a href="/upload">Envoyer une autre vidéo</a>
 </body></html>`,
 { headers: { "content-type": "text/html; charset=UTF-8" } }
);
}
// ---------- Envoi automatique (robot) ----------
// curl -X POST https://video-automation.emilienzabukovec09.workers.dev/api/upload \
// -H "Authorization: Bearer $API_KEY" \
// -F profile=carburant -F video=@video.mp4 -F title="..." -F description="..." -F caption="..."
async function handleApiUpload(request, env) {
const auth = request.headers.get("authorization") || "";
if (!env.API_KEY || auth !== `Bearer ${env.API_KEY}`) {
 return jsonResponse({ error: "Non autorisé." }, 401);
}
let formData;
try {
 formData = await request.formData();
} catch (err) {
 return jsonResponse({ error: "Requête invalide (multipart attendu)." }, 400);
}
const profile = getProfile(String(formData.get("profile") || ""));
if (!profile) {
 return jsonResponse({ error: "Profil manquant ou inconnu." }, 400);
}
const file = formData.get("video");
if (!file || typeof file === "string") {
 return jsonResponse({ error: "Aucun fichier reçu (champ 'video')." }, 400);
}
// Titre / description / légende propres à cette vidéo (sinon ceux du profil)
const custom = {};
const limits = { title: 100, description: 600, caption: 600 };
for (const field of Object.keys(limits)) {
 const value = formData.get(field);
 if (typeof value === "string" && value.trim()) {
 custom[field] = value.trim().slice(0, limits[field]);
 }
}
if (profile === PROFILES[LEDGER_PROFILE] && env.LEDGER_MODE !== "off") {
 return handleLedgerUpload(env, profile, formData, file, custom);
}
// Chemin historique (autres profils, ou LEDGER_MODE=off) : clé UNIQUE par requête, publiée explicitement (pas de listing)
const legacyKey = profile.prefix + "api-" + crypto.randomUUID() + ".mp4";
await env.VIDEO_BUCKET.put(legacyKey, file.stream(), {
 httpMetadata: { contentType: file.type || "video/mp4" },
 customMetadata: custom
});
let result;
try {
 result = await publishVideo(env, profile, legacyKey);
} catch (err) {
 return jsonResponse({ error: "Exception pendant la publication", details: String(err) }, 500);
}
const ok = result.youtube?.success || result.instagram?.success;
return jsonResponse(result, ok ? 200 : 502);
}
// ---------- Instagram (un token par profil) ----------
async function handleInstagramInitToken(url, env) {
if (!isOwner(url, env)) return denied();
const name = url.searchParams.get("profile") || "default";
const profile = getProfile(name);
if (!profile) {
 return new Response("Profil inconnu.", { status: 400 });
}
const token = url.searchParams.get("token");
if (!token) {
 return new Response("Ajoute &token=TON_TOKEN à l'URL.", { status: 400 });
}
const checkRes = await fetch(
 `https://graph.instagram.com/v21.0/me?fields=user_id&access_token=${token}`
);
const checkData = await checkRes.json();
if (!checkRes.ok || !checkData.user_id) {
 return new Response(`Le token ne semble pas valide : ${JSON.stringify(checkData)}`, { status: 400 });
}
const expiresAt = Date.now() + 60 * 24 * 60 * 60 * 1000; // 60 jours
await env.CONFIG_KV.put(
 profile.igKvKey,
 JSON.stringify({ access_token: token, expires_at: expiresAt })
);
return new Response( `✅ Token enregistré pour "${name}" (validité estimée jusqu'au ${new Date(expiresAt).toLocaleString("fr-FR")}).
Identifiant de ce compte Instagram : ${checkData.user_id}
(à mettre dans la variable ${profile.igAccountVar})
Le Worker tentera de le renouveler automatiquement avant l'échéance.`
);
}
async function getInstagramToken(env, profile) {
const raw = await env.CONFIG_KV.get(profile.igKvKey);
if (!raw) {
 throw new Error(
 "Aucun token Instagram initialisé pour ce profil. Va sur /instagram/init-token?profile=...&token=...&key=... une première fois."
 );
}
return JSON.parse(raw);
}
async function refreshInstagramTokensIfNeeded(env) {
const kvKeys = [...new Set(Object.values(PROFILES).map((p) => p.igKvKey))];
for (const kvKey of kvKeys) {
 try {
 const raw = await env.CONFIG_KV.get(kvKey);
 if (!raw) continue;
 const current = JSON.parse(raw);
 // On ne renouvelle que si l'expiration est dans moins de 10 jours
 const tenDaysMs = 10 * 24 * 60 * 60 * 1000;
 if (current.expires_at - Date.now() > tenDaysMs) continue;
 const refreshRes = await fetch(
 `https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=${current.access_token}`
 );
 const refreshData = await refreshRes.json();
 if (refreshData.access_token) {
 const expiresAt = Date.now() + refreshData.expires_in * 1000;
 await env.CONFIG_KV.put(
 kvKey,
 JSON.stringify({ access_token: refreshData.access_token, expires_at: expiresAt })
 );
 }
 } catch (err) {
 console.error("Échec du rafraîchissement du token Instagram :", err);
 }
}
}
// ---------- Fichier servi à Instagram ----------
async function handleServeMedia(url, env) {
const key = decodeURIComponent(url.pathname.replace("/media/", ""));
const object = await env.VIDEO_BUCKET.get(key);
if (!object) {
 return new Response("Fichier introuvable", { status: 404 });
}
return new Response(object.body, {
 headers: {
 "content-type": "video/mp4",
 "cache-control": "no-store"
 }
});
}
// ---------- Publication ----------
async function publishVideo(env, profile, explicitKey) {
await refreshInstagramTokensIfNeeded(env);
let key = explicitKey;
if (!key) {
 const listing = await env.VIDEO_BUCKET.list();
 // Chaque profil ne voit que ses propres fichiers ; les copies du journal (carburant/<créneau>/<sha>.mp4) ne sont JAMAIS candidates
 const objects = (listing.objects || []).filter((o) =>
  profile.prefix ? o.key.startsWith(profile.prefix) && !o.key.slice(profile.prefix.length).includes("/") : !o.key.includes("/")
 );
 if (objects.length === 0) {
  return { error: "Aucun fichier trouvé dans le bucket R2 pour ce profil." };
 }
 key = objects[0].key;
}
const object = await env.VIDEO_BUCKET.get(key);
if (!object) {
 return { error: `Fichier "${key}" introuvable au moment de la lecture.` };
}
const meta = object.customMetadata || {};
const post = {
 title: meta.title || profile.title,
 description: meta.description || profile.description,
 caption: meta.caption || profile.caption,
 tags: profile.tags
};
const videoBuffer = await object.arrayBuffer();
const youtubeResult = await uploadVideoToYouTube(env, profile, post, videoBuffer);
const instagramResult = await uploadVideoToInstagram(env, profile, post, key);
await env.VIDEO_BUCKET.delete(key);
return { youtube: youtubeResult, instagram: instagramResult };
}
async function uploadVideoToInstagram(env, profile, post, key, hooks = {}) {
let stage = "pre_publish"; // « pre_publish » = media_publish n'a PAS été appelé : rien n'est publié sur Instagram
try {
 const accountId = env[profile.igAccountVar];
 if (!accountId) {
 return { error: `Variable ${profile.igAccountVar} manquante.`, stage };
 }
 const tokenData = await getInstagramToken(env, profile);
 const accessToken = tokenData.access_token;
 const publicVideoUrl = `https://video-automation.emilienzabukovec09.workers.dev/media/${encodeURIComponent(
 key
 )}`;
 const createRes = await fetch(`https://graph.instagram.com/v21.0/${accountId}/media`, {
 method: "POST",
 headers: { "content-type": "application/json" },
 body: JSON.stringify({
 media_type: "REELS",
 video_url: publicVideoUrl,
 caption: post.caption,
 access_token: accessToken
 })
 });
 const createData = await createRes.json();
 if (!createRes.ok || !createData.id) {
 return { error: "Échec de la création du conteneur Instagram", details: createData, stage };
 }
 const containerId = createData.id;
 if (hooks.onContainer) {
 try { await hooks.onContainer(containerId); } catch (_) { /* trace facultative : ne bloque pas la publication */ }
 }
 let status = "IN_PROGRESS";
 let attempts = 0;
 while (status === "IN_PROGRESS" && attempts < 60) {
 await new Promise((resolve) => setTimeout(resolve, 5000));
 const statusRes = await fetch(
 `https://graph.instagram.com/v21.0/${containerId}?fields=status_code&access_token=${accessToken}`
 );
 const statusData = await statusRes.json();
 status = statusData.status_code;
 attempts++;
 }
 if (status !== "FINISHED") {
 return {
 error: `Le conteneur Instagram n'est pas prêt (statut: ${status})`,
 details: `ID du conteneur : ${containerId}.`,
 stage
 };
 }
 stage = "publish";
 const publishRes = await fetch(`https://graph.instagram.com/v21.0/${accountId}/media_publish`, {
 method: "POST",
 headers: { "content-type": "application/json" },
 body: JSON.stringify({
 creation_id: containerId,
 access_token: accessToken
 })
 });
 const publishData = await publishRes.json();
 if (!publishRes.ok || !publishData.id) {
 return { error: "Échec de la publication Instagram", details: publishData, stage, httpStatus: publishRes.status };
 }
 return { success: true, mediaId: publishData.id };
} catch (err) {
 return { error: "Exception pendant la publication Instagram", details: String(err), stage };
}
}
async function uploadVideoToYouTube(env, profile, post, videoBuffer) {
let stage = "pre_publish"; // « pre_publish » = aucun octet n'a été envoyé à YouTube
try {
 const accessToken = await getFreshAccessToken(env, profile);
 const metadata = {
 snippet: {
 title: post.title,
 description: post.description,
 tags: post.tags,
 categoryId: profile.categoryId || "22"
 },
 status: {
 privacyStatus: "public" // ou "private" / "unlisted" pour tester d'abord
 }
 };
 const boundary = "video_automation_boundary";
 const metadataPart = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${JSON.stringify(
 metadata
 )}\r\n`;
 const videoPartHeader = `--${boundary}\r\nContent-Type: video/mp4\r\n\r\n`;
 const closing = `\r\n--${boundary}--`;
 const body = new Blob([metadataPart, videoPartHeader, videoBuffer, closing]);
 stage = "publish";
 const uploadRes = await fetch(
 "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
 {
 method: "POST",
 headers: {
 Authorization: `Bearer ${accessToken}`, "Content-Type": `multipart/related; boundary=${boundary}`
 },
 body
 }
 );
 const result = await uploadRes.json();
 if (!uploadRes.ok) {
 return { error: "Échec de l'upload YouTube", details: result, stage, httpStatus: uploadRes.status };
 }
 return { success: true, videoId: result.id, url: `https://youtu.be/${result.id}` };
} catch (err) {
 return { error: "Exception pendant l'upload YouTube", details: String(err), stage };
}
}
