'use strict';
// Read-only compatibility adapter for the existing public frontend proxy response.
// Does NOT claim a limit=100 response is exhaustive.
const FIELDS=Object.freeze({Gazole:'gazole_prix',SP95:'sp95_prix',SP98:'sp98_prix',E10:'e10_prix',E85:'e85_prix',GPLc:'gplc_prix'});
function coords(s){
  const lat=s?.geom?.lat!==undefined?Number(s.geom.lat):Number(s?.latitude)/100000;
  const lon=s?.geom?.lon!==undefined?Number(s.geom.lon):Number(s?.longitude)/100000;
  return Number.isFinite(lat)&&Math.abs(lat)<=90&&Number.isFinite(lon)&&Math.abs(lon)<=180?{lat,lon}:null;
}
function normalizeProxyStation(s,fuel){
  if(!FIELDS[fuel])throw new RangeError('Carburant inconnu');
  const c=coords(s),price=Number(s?.[FIELDS[fuel]]);
  if(!s||!['string','number'].includes(typeof s.id)||!String(s.id).trim()||!c||!Number.isFinite(price)||price<=0)return null;
  return {id:String(s.id),...c,price,address:s.adresse||'',city:s.ville||'',postalCode:s.cp||''};
}
function adaptProxyResponse(raw,{fuel,limit=100}={}){
  if(!FIELDS[fuel])throw new RangeError('Carburant inconnu');
  if(!Number.isInteger(limit)||limit<1)throw new RangeError('Limite invalide');
  if(!raw||!Array.isArray(raw.results))throw new TypeError('Réponse proxy invalide');
  const seen=new Set(),stations=[];let rejected=0;
  for(const item of raw.results){const s=normalizeProxyStation(item,fuel);if(!s){rejected++;continue;}if(seen.has(s.id))continue;seen.add(s.id);stations.push(s);}
  // The existing frontend only documents `results`, not a trusted pagination contract.
  // Never infer completeness from results.length < limit or from a self-reported count.
  return {stations,rawCount:raw.results.length,rejected,complete:false,reason:'proxy_completion_unverified',hasMoreUnknown:true};
}
function createLegacyProxyFetch({fetchFn,baseUrl='https://carburant-proxy.emilienzabukovec09.workers.dev'}={}){
  if(typeof fetchFn!=='function')throw new TypeError('fetchFn requis');
  return async function fetchLegacy({origin,radiusKm,fuel,limit=100,signal}){
    if(!origin||!Number.isFinite(origin.lat)||!Number.isFinite(origin.lon)||Math.abs(origin.lat)>90||Math.abs(origin.lon)>180)throw new RangeError('Origine invalide');
    if(!Number.isFinite(radiusKm)||radiusKm<=0||radiusKm>100)throw new RangeError('Rayon invalide');
    const url=new URL(baseUrl);url.searchParams.set('lat',String(origin.lat));url.searchParams.set('lon',String(origin.lon));url.searchParams.set('dist',String(radiusKm));url.searchParams.set('limit',String(limit));
    const response=await fetchFn(url.toString(),{signal});
    if(!response?.ok)throw new Error('Erreur HTTP proxy '+(response?.status??'inconnue'));
    return adaptProxyResponse(await response.json(),{fuel,limit});
  };
}
module.exports={FIELDS,coords,normalizeProxyStation,adaptProxyResponse,createLegacyProxyFetch};
