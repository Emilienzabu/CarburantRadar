import test from 'node:test';
import assert from 'node:assert/strict';
import {statistiques} from './statistiques.mjs';

function fixture() {
  const objets = new Map();
  const env = {API_KEY:'test', VIDEO_STATS:{
    async put(k,v,options) {
      assert.equal(options.onlyIf.get('if-none-match'), '*');
      if (objets.has(k)) return null;
      objets.set(k,v);
      return {};
    },
    async get(k) { return objets.has(k) ? {json: async () => JSON.parse(objets.get(k))} : null; },
    async head(k) { return objets.has(k); },
    async list({prefix}) {
      return {objects:[...objets.keys()].filter(k => k.startsWith(prefix)).map(key => ({key})),truncated:false};
    }
  }};
  const pub = {plateforme:'youtube',video_id:'abcdefghijk',id_video:'2026-matin',
    publie_le:'2026-01-01T00:00:00Z',musique:4,hashtags:['#test']};
  const appeler = (route, body, lire, heures=24, cle='test') => statistiques(
    new Request('https://worker.test/api/stats/'+route, {method:body?'POST':'GET',
      headers:{Authorization:'Bearer '+cle},body:body && JSON.stringify(body)}),env,lire,
    () => Date.parse(pub.publie_le)+heures*3600000);
  return {pub,appeler,env};
}

test('routes isolées, accès privé et identifiants validés', async () => {
  const {pub,appeler,env}=fixture();
  assert.equal(await statistiques(new Request('https://worker.test/api/upload'),env),null);
  assert.equal((await appeler('publications',null,null,24,'autre')).status,401);
  assert.equal((await appeler('recu',{...pub,video_id:'../'})).status,400);
});

test('reprise après échec et concurrence à chaque horizon', async () => {
  const {pub,appeler}=fixture();
  assert.equal((await appeler('recu',pub)).status,200);
  assert.equal((await appeler('recu',pub)).status,200);
  assert.equal((await appeler('recu',{...pub,id_video:'autre'})).status,409);
  assert.equal((await appeler('relever',pub,async()=>{throw Error()})).status,502);
  const lire=async()=>({vues:0,hashtags:['#reel'],hashtags_source:'plateforme'});
  for (const jour of [1,3,7,14,30]) {
    const reponses=await Promise.all([1,2].map(()=>appeler('relever',pub,lire,jour*24)));
    const etats=await Promise.all(reponses.map(async r=>(await r.json()).statut));
    assert.deepEqual(etats.sort(),['deja_releve','releve']);
  }
  assert.equal((await (await appeler('relever',pub,lire,30*24+12)).json()).statut,'hors_fenetre');
  const {lignes}=await (await appeler('mesures')).json();
  assert.equal(lignes.length,5);
  assert.deepEqual(lignes.map(l=>l.horizon_jours),[1,3,7,14,30]);
  assert.equal(lignes[0].musique,4);
  assert.equal(lignes[0].vues,0);
  assert.deepEqual(lignes[0].hashtags,['#reel']);
});

test('marqueur durable pour les reçus entièrement archivés',async()=>{
  const {appeler}=fixture();
  await appeler('importe',{id:'42'});
  await appeler('importe',{id:'42'});
  assert.deepEqual((await (await appeler('artefacts')).json()).lignes,['42']);
});

test('adaptateur YouTube avec lectures réelles simulées, zéro vues et hashtags',async(t)=>{
  const {pub,appeler,env}=fixture();
  env.CONFIG_KV={get:async()=> 'refresh-test'};
  const urls=[];
  t.mock.method(globalThis,'fetch',async(url,opts)=>{
    urls.push(url);
    assert.equal(opts.redirect,'manual');
    if (url==='https://oauth2.googleapis.com/token') return Response.json({access_token:'test'});
    assert.equal(opts.headers.Authorization,'Bearer test');
    return Response.json({items:[{id:pub.video_id,statistics:{viewCount:'0'},snippet:{title:'#Éco #éco'}}]});
  });
  await appeler('recu',pub);
  assert.equal((await appeler('relever',pub)).status,200);
  const [m]=(await (await appeler('mesures')).json()).lignes;
  assert.equal(m.vues,0);
  assert.deepEqual(m.hashtags,['#éco']);
  assert.equal(urls.length,2);
});

test('adaptateur Instagram conserve les hashtags du reçu si la légende est inaccessible',async(t)=>{
  const {pub,appeler,env}=fixture();
  const reel={...pub,plateforme:'instagram',video_id:'1234',hashtags_source:'texte_envoye'};
  env.CONFIG_KV={get:async()=> JSON.stringify({access_token:'test'})};
  t.mock.method(globalThis,'fetch',async(url,opts)=>{
    assert.equal(opts.headers.Authorization,'Bearer test');
    return url.includes('/insights?') ?
      Response.json({data:[{name:'views',values:[{value:24}]},{name:'shares',values:[{value:0}]}]}) :
      new Response(null,{status:403});
  });
  await appeler('recu',reel);
  assert.equal((await appeler('relever',reel)).status,200);
  const [m]=(await (await appeler('mesures')).json()).lignes;
  assert.equal(m.vues,24);
  assert.equal(m.partages,0);
  assert.deepEqual(m.hashtags,['#test']);
  assert.equal(m.hashtags_source,'texte_envoye');
});
