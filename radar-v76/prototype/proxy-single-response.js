'use strict';
// Explicit adapter for the standalone /v2/france handler. It is NOT the cursor-based V2 API.
const {normalizeProxyStation,FIELDS}=require('./proxy-adapter');
function normalizeSingleResponse(raw,fuel){
 if(!FIELDS[fuel])throw new RangeError('Carburant invalide');
 if(!raw||raw.schemaVersion!==2||raw.complete!==true||raw.nextCursor!==null||!Array.isArray(raw.results)||!Number.isInteger(raw.total)||raw.total<0||!Number.isInteger(raw.sourceTotal)||raw.sourceTotal<0||typeof raw.snapshot!=='string'||!raw.snapshot)throw new TypeError('Réponse complète V2 invalide');
 if(raw.results.length!==raw.total||raw.total>raw.sourceTotal)throw new TypeError('Total incohérent');
 const ids=new Set(),stations=[];
 for(const item of raw.results){
  if(item?.id===undefined||item.id===null)throw new TypeError('ID absent');
  const id=String(item.id);if(ids.has(id))throw new TypeError('ID dupliqué');ids.add(id);
  const s=normalizeProxyStation(item,fuel);
  if(!s)throw new TypeError('Prix demandé absent dans réponse filtrée');
  stations.push(s);
 }
 return {stations,complete:true,source:'france_v2_single',snapshot:raw.snapshot,sourceTotal:raw.sourceTotal};
}
async function loadSingleResponse({fetchFn,baseUrl='https://carburant-proxy.emilienzabukovec09.workers.dev',origin,radiusKm,fuel,signal}={}){
 if(typeof fetchFn!=='function')throw new TypeError('fetchFn requis');
 if(!FIELDS[fuel])throw new RangeError('Carburant invalide');
 if(!origin||!Number.isFinite(origin.lat)||!Number.isFinite(origin.lon)||Math.abs(origin.lat)>90||Math.abs(origin.lon)>180||![5,10,20,50].includes(radiusKm))throw new RangeError('Recherche invalide');
 const url=new URL('/v2/france',baseUrl);
 for(const [k,v] of Object.entries({lat:origin.lat,lon:origin.lon,dist:radiusKm,fuel}))url.searchParams.set(k,String(v));
 const response=await fetchFn(url.toString(),{signal});
 if(!response?.ok)throw new Error('proxy_http_'+(response?.status??'unknown'));
 return normalizeSingleResponse(await response.json(),fuel);
}
module.exports={normalizeSingleResponse,loadSingleResponse};
