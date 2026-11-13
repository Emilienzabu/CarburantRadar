'use strict';
// V35: exact lower-bound pruning for a *single fuel* and one fixed origin.
// Pure decision logic + injectable routing; no live network by default.
const {validateVehicle,validatePercent,costForStation}=require('./radar-cost');
function validateStations(stations){
  if(!Array.isArray(stations))throw new TypeError('Stations invalides');
  const ids=new Set();
  return stations.map(s=>{
    if(!s || (typeof s.id!=='string'&&typeof s.id!=='number') || !String(s.id))throw new TypeError('Identifiant station invalide');
    const id=String(s.id);
    if(ids.has(id))throw new Error('Station dupliquée');ids.add(id);
    if(typeof s.price!=='number'||!Number.isFinite(s.price)||s.price<=0)throw new TypeError('Prix invalide');
    if(typeof s.lat!=='number'||!Number.isFinite(s.lat)||Math.abs(s.lat)>90||typeof s.lon!=='number'||!Number.isFinite(s.lon)||Math.abs(s.lon)>180)throw new TypeError('Coordonnées station invalides');
    return {...s,id};
  });
}
function lowerBound(vehicle,percent,station){return vehicle.tankCapacity*percent/100*station.price;}
function isAbort(signal){return Boolean(signal?.aborted);}
async function searchCheapest({vehicle,fillPercent,stations,origin,routeBatch,batchSize=10,signal,onProgress=()=>{}}={}){
  validateVehicle(vehicle);validatePercent(fillPercent);
  if(!origin||typeof origin.lat!=='number'||!Number.isFinite(origin.lat)||Math.abs(origin.lat)>90||typeof origin.lon!=='number'||!Number.isFinite(origin.lon)||Math.abs(origin.lon)>180)throw new TypeError('Origine invalide');
  if(typeof routeBatch!=='function'||typeof onProgress!=='function')throw new TypeError('Callback invalide');
  if(!Number.isInteger(batchSize)||batchSize<1||batchSize>25)throw new RangeError('Lot invalide');
  const all=validateStations(stations).sort((a,b)=>lowerBound(vehicle,fillPercent,a)-lowerBound(vehicle,fillPercent,b)||a.id.localeCompare(b.id));
  const completed=[],unavailable=[],skipped=[];
  let best=null,requests=0,visited=0;
  for(let start=0;start<all.length;){
    if(isAbort(signal))return {status:'cancelled',best,completed,unavailable,skipped,requests,visited};
    // Strictly greater can be discarded; ties may represent co-winners.
    if(best!==null && lowerBound(vehicle,fillPercent,all[start])>best.totalCost){
      skipped.push(...all.slice(start).map(s=>s.id));break;
    }
    const batch=[];
    while(start<all.length&&batch.length<batchSize && (best===null||lowerBound(vehicle,fillPercent,all[start])<=best.totalCost))batch.push(all[start++]);
    requests++;
    let routes;
    try{routes=await routeBatch({origin,stations:batch,signal});}
    catch(e){if(isAbort(signal))return {status:'cancelled',best,completed,unavailable,skipped,requests,visited};routes=[];}
    if(isAbort(signal))return {status:'cancelled',best,completed,unavailable,skipped,requests,visited};
    const lookup=new Map();
    if(Array.isArray(routes))for(const r of routes){
      if(r && (typeof r.id==='string'||typeof r.id==='number') && !lookup.has(String(r.id)))lookup.set(String(r.id),r);
    }
    for(const s of batch){
      visited++;
      const r=lookup.get(s.id);
      const distance=r?.distanceRoundTripKm;
      if(typeof distance!=='number'||!Number.isFinite(distance)||distance<0){unavailable.push({id:s.id,lowerBound:lowerBound(vehicle,fillPercent,s)});continue;}
      const result=costForStation(vehicle,fillPercent,{...s,distanceRoundTripKm:distance});
      completed.push(result);
      if(best===null||result.totalCost<best.totalCost)best=result;
    }
    onProgress({best,visited,total:all.length,requests});
  }
  const unverified=unavailable.filter(x=>best===null||x.lowerBound<=best.totalCost);
  const status=best===null?'unverified':unverified.length?'unverified':'verified';
  return {status,best,completed:completed.sort((a,b)=>a.totalCost-b.totalCost),unavailable,unverified,skipped,requests,visited,total:all.length};
}
module.exports={searchCheapest,lowerBound,validateStations};
