/** Extension du Worker video-automation. Les jetons sociaux restent dans Cloudflare. */
const jours = [1, 3, 7, 14, 30];
const json = (value, status = 200) => Response.json(value, {status, headers: {'Cache-Control': 'no-store'}});

function valide(p) {
  const format = {youtube: /^[A-Za-z0-9_-]{11}$/, instagram: /^\d{1,32}$/}[p?.plateforme];
  return format instanceof RegExp && typeof p.video_id === 'string' && format.test(p.video_id);
}

function horizon(date, maintenant) {
  const heures = (maintenant - Date.parse(date)) / 3600000;
  return jours.find(j => j * 24 <= heures && heures < j * 24 + 12);
}

async function api(url, options) {
  const res = await fetch(url, {...options, redirect: 'manual'});
  if (!res.ok) throw new Error('API sociale HTTP ' + res.status);
  return res.json();
}

async function compteurs(p, env) {
  let stats, textes;
  if (p.plateforme === 'youtube') {
    const refresh = await env.CONFIG_KV.get('youtube_refresh_token_carburant');
    if (!refresh) throw new Error('Connexion YouTube indisponible');
    const oauth = await api('https://oauth2.googleapis.com/token', {method: 'POST',
      body: new URLSearchParams({client_id: env.YOUTUBE_CLIENT_ID, client_secret: env.YOUTUBE_CLIENT_SECRET,
        refresh_token: refresh, grant_type: 'refresh_token'})});
    const data = await api('https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id=' + p.video_id,
      {headers: {Authorization: 'Bearer ' + oauth.access_token}});
    const v = data.items.find(v => v.id === p.video_id);
    stats = {vues: v?.statistics?.viewCount, likes: v?.statistics?.likeCount, commentaires: v?.statistics?.commentCount};
    textes = [v?.snippet?.title, v?.snippet?.description];
  } else {
    const token = JSON.parse(await env.CONFIG_KV.get('instagram_token_carburant'))?.access_token;
    if (!token) throw new Error('Connexion Instagram indisponible');
    const options = {headers: {Authorization: 'Bearer ' + token}};
    const version = env.CR_INSTAGRAM_VERSION || 'v21.0';
    if (!/^v\d+\.\d+$/.test(version)) throw new Error('Version Instagram invalide');
    const url = 'https://graph.instagram.com/' + version + '/' + p.video_id;
    const data = await api(url + '/insights?metric=views,likes,comments,shares', options);
    const m = Object.fromEntries(data.data.map(x => [x.name, x.values?.[0]?.value]));
    stats = {vues: m.views, likes: m.likes, commentaires: m.comments, partages: m.shares};
    try { textes = [(await api(url + '?fields=caption', options)).caption]; } catch { textes = []; }
  }
  const nombres = Object.fromEntries(Object.entries(stats)
    .filter(([,v]) => /^(0|[1-9]\d*)$/.test(String(v)) && Number.isSafeInteger(Number(v)))
    .map(([k,v]) => [k, Number(v)]));
  if (nombres.vues === undefined) throw new Error('Vues indisponibles');
  if (textes.some(t => typeof t === 'string')) {
    const tags = textes.filter(t => typeof t === 'string').join(' ').normalize('NFC')
      .match(/(?<![\p{L}\p{N}_#])#[\p{L}\p{N}_]+/gu) || [];
    nombres.hashtags = [...new Set(tags.map(t => t.toLowerCase()))];
    nombres.hashtags_source = 'plateforme';
  }
  return nombres;
}

const premiereEcriture = {onlyIf: new Headers({'If-None-Match': '*'})};

// Retourne null pour que le Worker continue de traiter ses routes habituelles.
export async function statistiques(request, env, lire = compteurs, horloge = Date.now) {
  const url = new URL(request.url);
  if (!url.pathname.startsWith('/api/stats/')) return null;
  if (!env.API_KEY || request.headers.get('Authorization') !== 'Bearer ' + env.API_KEY) return json({}, 401);
  const bucket = env.VIDEO_STATS;
  if (!bucket) return json({erreur: 'Stockage privé indisponible'}, 503);
  const route = url.pathname.slice('/api/stats/'.length);
  if (request.method === 'GET' && ['publications','mesures','artefacts'].includes(route)) {
    const page = await bucket.list({prefix: route + '/', cursor: url.searchParams.get('cursor') || undefined, limit: 25});
    const lignes = route === 'artefacts' ? page.objects.map(o => o.key.slice('artefacts/'.length))
      : await Promise.all(page.objects.map(async o => (await bucket.get(o.key)).json()));
    return json({lignes, curseur: page.truncated ? page.cursor : null});
  }
  if (request.method !== 'POST' || !['recu','relever','importe'].includes(route)) return json({}, 404);
  let pub;
  try { pub = await request.json(); } catch { return json({}, 400); }
  if (route === 'importe') {
    if (typeof pub?.id !== 'string' || !/^\d{1,24}$/.test(pub.id)) return json({}, 400);
    await bucket.put('artefacts/' + pub.id, '', premiereEcriture);
    return json({archive: true});
  }
  if (!valide(pub)) return json({}, 400);
  const suffixe = pub.plateforme + '/' + pub.video_id;
  const cle = 'publications/' + suffixe;
  if (route === 'recu') {
    if (typeof pub.publie_le !== 'string' || !/(Z|[+-]\d\d:\d\d)$/.test(pub.publie_le)
      || !Number.isFinite(Date.parse(pub.publie_le)) || !pub.id_video) return json({}, 400);
    const ajoute = await bucket.put(cle, JSON.stringify(pub), premiereEcriture);
    if (!ajoute) {
      const ancien = await (await bucket.get(cle)).json();
      if (ancien.id_video !== pub.id_video || ancien.publie_le !== pub.publie_le) return json({erreur:'Reçus contradictoires'},409);
    }
    return json({archive: true});
  }
  const objet = await bucket.get(cle);
  if (!objet) return json({}, 404);
  const fiche = await objet.json();
  const j = horizon(fiche.publie_le, horloge());
  if (!j) return json({statut:'hors_fenetre'});
  const mesure = 'mesures/' + suffixe + '/' + j;
  if (await bucket.head(mesure)) return json({statut:'deja_releve'});
  let stats;
  try { stats = await lire(fiche, env); } catch { return json({erreur:'Lecture plateforme indisponible'},502); }
  const fin = horloge();
  if (horizon(fiche.publie_le, fin) !== j) return json({statut:'hors_fenetre'});
  const ajoute = await bucket.put(mesure, JSON.stringify({...fiche,...stats,horizon_jours:j,
    mesure_le:new Date(fin).toISOString()}), premiereEcriture);
  return json({statut: ajoute ? 'releve' : 'deja_releve'});
}
