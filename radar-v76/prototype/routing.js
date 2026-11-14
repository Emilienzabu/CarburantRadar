'use strict';
// Prototype V33. Service injectable; no network call unless caller explicitly invokes resolveRoutes.
const DEFAULT_BASE='https://router.project-osrm.org/table/v1/driving/';
function coord(p){
  if(!p || typeof p.lat!=='number'||typeof p.lon!=='number'||!Number.isFinite(p.lat)||!Number.isFinite(p.lon)||Math.abs(p.lat)>90||Math.abs(p.lon)>180)throw new TypeError('Coordonnées invalides');
  return `${p.lon},${p.lat}`;
}
function stationId(s){if(!s || (typeof s.id!=='string'&&typeof s.id!=='number') || String(s.id)==='')throw new TypeError('Identifiant station invalide');return String(s.id);}
function parseMeters(value){return typeof value==='number'&&Number.isFinite(value)&&value>=0?value:null;}
function extract(table, count, outbound){
  if(!table || table.code!=='Ok'||!Array.isArray(table.distances))throw new Error('Réponse routière invalide');
  const rows=table.distances;
  // OSRM returns 1 x N for outbound and N x 1 for inbound.
  if(outbound){if(rows.length!==1||!Array.isArray(rows[0])||rows[0].length!==count)throw new Error('Matrice aller invalide');return rows[0].map(parseMeters);}
  if(rows.length!==count||rows.some(row=>!Array.isArray(row)||row.length!==1))throw new Error('Matrice retour invalide');
  return rows.map(row=>parseMeters(row[0]));
}
function buildUrl(base,origin,batch,outbound){
  if(typeof base!=='string'||!/^https:\/\//.test(base))throw new TypeError('Base HTTPS requise');
  const points=[origin,...batch].map(coord);
  const indexes=batch.map((_,i)=>String(i+1)).join(';');
  const query=outbound?`sources=0&destinations=${indexes}`:`sources=${indexes}&destinations=0`;
  return `${base.replace(/\/$/,'')}/${points.join(';')}?annotations=distance,duration&${query}`;
}
function cacheKey(origin,s){return `${coord(origin)}|${stationId(s)}|${coord(s)}`;}
function createRouteCache(){return new Map();}
function extractDuration(table,count,outbound){
  if(!table||!Array.isArray(table.durations))return Array(count).fill(null);
  const rows=table.durations;
  if(outbound){if(rows.length!==1||!Array.isArray(rows[0])||rows[0].length!==count)throw new Error('Matrice durée aller invalide');return rows[0].map(parseMeters);}
  if(rows.length!==count||rows.some(row=>!Array.isArray(row)||row.length!==1))throw new Error('Matrice durée retour invalide');
  return rows.map(row=>parseMeters(row[0]));
}
async function requestMatrix(url,fetchFn,signal){
  const response=await fetchFn(url,{signal});
  if(!response||!response.ok)throw new Error('Erreur HTTP itinéraire');
  return response.json();
}
async function resolveRoutes({origin,stations,fetchFn,cache=createRouteCache(),base=DEFAULT_BASE,batchSize=10,ttlMs=15*60*1000,now=()=>Date.now(),signal}={}){
  coord(origin);
  if(!Array.isArray(stations)||typeof fetchFn!=='function')throw new TypeError('Stations ou fetchFn invalides');
  if(!Number.isInteger(batchSize)||batchSize<1||batchSize>25)throw new RangeError('Lot invalide');
  if(!Number.isFinite(ttlMs)||ttlMs<0)throw new RangeError('TTL invalide');
  if(typeof now!=='function'||!cache||typeof cache.get!=='function'||typeof cache.set!=='function')throw new TypeError('Cache invalide');
  const ids=new Set(),result=new Map(),pending=[];
  for(const s of stations){
    const id=stationId(s);coord(s);
    if(ids.has(id))throw new Error('Identifiant station dupliqué');ids.add(id);
    const key=cacheKey(origin,s),entry=cache.get(key),t=now();
    if(entry && t<entry.expiresAt && typeof entry.distanceRoundTripKm==='number')result.set(id,{id,status:'routed',distanceRoundTripKm:entry.distanceRoundTripKm,durationOutboundMinutes:entry.durationOutboundMinutes??null,durationReturnMinutes:entry.durationReturnMinutes??null,fromCache:true});
    else pending.push(s);
  }
  for(let start=0;start<pending.length;start+=batchSize){
    if(signal?.aborted)throw new Error('Calcul annulé');
    const batch=pending.slice(start,start+batchSize);
    try{
      // Both directions are mandatory; never infer return from outbound.
      const outwardTable=await requestMatrix(buildUrl(base,origin,batch,true),fetchFn,signal);
      const inwardTable=await requestMatrix(buildUrl(base,origin,batch,false),fetchFn,signal);
      const outward=extract(outwardTable,batch.length,true);
      const inward=extract(inwardTable,batch.length,false);
      const outwardTime=extractDuration(outwardTable,batch.length,true);
      const inwardTime=extractDuration(inwardTable,batch.length,false);
      batch.forEach((s,i)=>{
        const id=stationId(s),a=outward[i],b=inward[i];
        if(a===null||b===null){result.set(id,{id,status:'route_unavailable',distanceRoundTripKm:null,durationOutboundMinutes:null,durationReturnMinutes:null,fromCache:false});return;}
        const distanceRoundTripKm=(a+b)/1000;
        const durationOutboundMinutes=outwardTime[i]===null?null:outwardTime[i]/60;
        const durationReturnMinutes=inwardTime[i]===null?null:inwardTime[i]/60;
        result.set(id,{id,status:'routed',distanceRoundTripKm,durationOutboundMinutes,durationReturnMinutes,fromCache:false});
        cache.set(cacheKey(origin,s),{distanceRoundTripKm,durationOutboundMinutes,durationReturnMinutes,expiresAt:now()+ttlMs});
      });
    }catch(e){
      if(signal?.aborted)throw e;
      batch.forEach(s=>result.set(stationId(s),{id:stationId(s),status:'route_unavailable',distanceRoundTripKm:null,durationOutboundMinutes:null,durationReturnMinutes:null,fromCache:false}));
    }
  }
  return stations.map(s=>result.get(stationId(s)));
}
module.exports={DEFAULT_BASE,coord,buildUrl,extract,extractDuration,createRouteCache,resolveRoutes};
