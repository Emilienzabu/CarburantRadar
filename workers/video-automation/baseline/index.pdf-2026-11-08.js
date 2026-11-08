// src/index.js : version multi-comptes
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
 ctx.waitUntil(publishVideo(env, PROFILES.default));
}
};
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
 result = await publishVideo(env, profile);
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
await env.VIDEO_BUCKET.put(videoKeyFor(profile), file.stream(), {
 httpMetadata: { contentType: file.type || "video/mp4" },
 customMetadata: custom
});
let result;
try {
 result = await publishVideo(env, profile);
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
async function publishVideo(env, profile) {
await refreshInstagramTokensIfNeeded(env);
const listing = await env.VIDEO_BUCKET.list();
// Chaque profil ne voit que ses propres fichiers
const objects = (listing.objects || []).filter((o) =>
 profile.prefix ? o.key.startsWith(profile.prefix) : !o.key.includes("/")
);
if (objects.length === 0) {
 return { error: "Aucun fichier trouvé dans le bucket R2 pour ce profil." };
}
const key = objects[0].key;
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
async function uploadVideoToInstagram(env, profile, post, key) {
try {
 const accountId = env[profile.igAccountVar];
 if (!accountId) {
 return { error: `Variable ${profile.igAccountVar} manquante.` };
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
 return { error: "Échec de la création du conteneur Instagram", details: createData };
 }
 const containerId = createData.id;
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
 details: `ID du conteneur : ${containerId}.`
 };
 }
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
 return { error: "Échec de la publication Instagram", details: publishData };
 }
 return { success: true, mediaId: publishData.id };
} catch (err) {
 return { error: "Exception pendant la publication Instagram", details: String(err) };
}
}
async function uploadVideoToYouTube(env, profile, post, videoBuffer) {
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
 return { error: "Échec de l'upload YouTube", details: result };
 }
 return { success: true, videoId: result.id, url: `https://youtu.be/${result.id}` };
} catch (err) {
 return { error: "Exception pendant l'upload YouTube", details: String(err) };
}
}
