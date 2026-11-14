'use strict';
const {normalizeProxyStation,FIELDS}=require('./proxy-adapter');
const {loadAllStations}=require('./station-pages');

// A V2 contract is explicit. Legacy results are NEVER silently upgraded.
function normalizeV2Page(raw,fuel){
  if(!FIELDS[fuel])throw new RangeError('Carburant invalide');
  if(!raw||raw.schemaVersion!==2||!Array.isArray(raw.results)||typeof raw.complete!=='boolean')throw new TypeError('Contrat proxy V2 absent');
  if(raw.complete && raw.nextCursor!=null)throw new TypeError('Page complete avec curseur');
  if(!raw.complete && (typeof raw.nextCursor!=='string'||!raw.nextCursor))throw new TypeError('Curseur manquant');
  if(raw.total!==undefined&&(!Number.isInteger(raw.total)||raw.total<0))throw new TypeError('Total invalide');
  if(typeof raw.snapshot!=='string'||!raw.snapshot)throw new TypeError('Snapshot manquant');
  const stations=[];const seen=new Set();
  for(const item of raw.results){
    const station=normalizeProxyStation(item,fuel);
    if(!station)continue; // Missing fuel price is not an error; no such fuel at this station.
    if(seen.has(station.id))throw new TypeError('Identifiant duplique dans une page');
    seen.add(station.id);stations.push(station);
  }
  return {stations,complete:raw.complete,nextCursor:raw.nextCursor??null,total:raw.total,snapshot:raw.snapshot};
}
function createV2PageFetcher({fetchFn,baseUrl,fuel,limit=100}={}){
  if(typeof fetchFn!=='function')throw new TypeError('fetchFn requis');
  if(!FIELDS[fuel])throw new RangeError('Carburant invalide');
  if(!Number.isInteger(limit)||limit<1||limit>500)throw new RangeError('Limite invalide');
  const base=new URL(baseUrl||'https://carburant-proxy.emilienzabukovec09.workers.dev');
  let snapshot=null;
  return async function fetchPage({origin,radiusKm,cursor,signal}){
    const url=new URL(base);url.searchParams.set('v','2');url.searchParams.set('lat',String(origin.lat));url.searchParams.set('lon',String(origin.lon));url.searchParams.set('dist',String(radiusKm));url.searchParams.set('limit',String(limit));
    if(cursor!=null)url.searchParams.set('cursor',String(cursor));
    if(snapshot!==null)url.searchParams.set('snapshot',snapshot);
    const response=await fetchFn(url.toString(),{signal});
    if(!response?.ok)throw new Error('proxy_http_'+(response?.status??'unknown'));
    const page=normalizeV2Page(await response.json(),fuel);
    if(snapshot!==null&&snapshot!==page.snapshot)throw new Error('snapshot_changed');
    snapshot=page.snapshot;
    return page;
  };
}
async function loadV2({fetchFn,baseUrl,fuel,limit=100,origin,radiusKm,signal,maxPages=100,onProgress}={}){
  const fetchPage=createV2PageFetcher({fetchFn,baseUrl,fuel,limit});
  const result=await loadAllStations({fetchPage,origin,radiusKm,signal,maxPages,onProgress});
  return {...result,certifiable:result.complete};
}
module.exports={normalizeV2Page,createV2PageFetcher,loadV2};
