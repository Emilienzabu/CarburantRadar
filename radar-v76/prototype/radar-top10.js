'use strict';
// V36: certified top K among the provided stations, when all potentially competitive routes resolve.
const {validateVehicle,validatePercent,costForStation}=require('./radar-cost');
const {validateStations,lowerBound}=require('./radar-search');
const validDistance=d=>typeof d==='number'&&Number.isFinite(d)&&d>=0;
function order(a,b){return a.totalCost-b.totalCost||String(a.id).localeCompare(String(b.id));}
function validDuration(t){return typeof t==='number'&&Number.isFinite(t)&&t>=0?t:null;}
function validateOrigin(o){if(!o||typeof o.lat!=='number'||!Number.isFinite(o.lat)||Math.abs(o.lat)>90||typeof o.lon!=='number'||!Number.isFinite(o.lon)||Math.abs(o.lon)>180)throw new TypeError('Origine invalide');}
function makeTop10({vehicle,fillPercent,stations,origin,routeBatch,batchSize=10,topK=10,signal,onProgress=()=>{}}={}){
  validateVehicle(vehicle);validatePercent(fillPercent);validateOrigin(origin);
  if(typeof routeBatch!=='function'||typeof onProgress!=='function')throw new TypeError('Callbacks invalides');
  if(!Number.isInteger(batchSize)||batchSize<1||batchSize>25)throw new RangeError('Taille de lot invalide');
  if(!Number.isInteger(topK)||topK<1||topK>50)throw new RangeError('TopK invalide');
  const all=validateStations(stations).sort((a,b)=>lowerBound(vehicle,fillPercent,a)-lowerBound(vehicle,fillPercent,b)||a.id.localeCompare(b.id));
  const byId=new Map(all.map(s=>[s.id,s]));
  const measured=new Map(), failed=new Set(), skipped=new Set();
  let cursor=0,requests=0;
  function ranked(){return [...measured.values()].map(({station,distance,durationOutboundMinutes,durationReturnMinutes})=>({...costForStation(vehicle,fillPercent,{...station,distanceRoundTripKm:distance}),distanceRoundTripKm:distance,durationOutboundMinutes,durationReturnMinutes})).sort(order);}
  function threshold(rows){return rows.length>=topK?rows[topK-1].totalCost:null;}
  function state(status){const rows=ranked(),cut=threshold(rows);const unresolved=all.filter(s=>!measured.has(s.id)&&!skipped.has(s.id));const blockers=unresolved.filter(s=>cut===null||lowerBound(vehicle,fillPercent,s)<=cut).map(s=>s.id);return {status,top:rows.slice(0,topK),calculated:rows,uncalculated:unresolved.map(s=>s.id),unavailable:[...failed],blockers,skipped:[...skipped],requests,total:all.length,certified:status==='verified'};}
  async function run(){
    while(cursor<all.length){
      if(signal?.aborted)return state('cancelled');
      const rows=ranked(),cut=threshold(rows);
      if(cut!==null&&lowerBound(vehicle,fillPercent,all[cursor])>cut){for(let i=cursor;i<all.length;i++)skipped.add(all[i].id);cursor=all.length;break;}
      const batch=[];
      while(cursor<all.length&&batch.length<batchSize){
        const s=all[cursor];
        if(cut!==null&&lowerBound(vehicle,fillPercent,s)>cut)break;
        cursor++;if(!measured.has(s.id)&&!failed.has(s.id))batch.push(s);
      }
      if(!batch.length)continue;
      requests++;
      let routes;
      try{routes=await routeBatch({origin,stations:batch,signal});}catch(e){routes=[];}
      if(signal?.aborted)return state('cancelled');
      const routeMap=new Map();
      if(Array.isArray(routes))for(const r of routes){
        if(r&&['string','number'].includes(typeof r.id)&&!routeMap.has(String(r.id)))routeMap.set(String(r.id),r);
      }
      for(const s of batch){const route=routeMap.get(s.id),d=route?.distanceRoundTripKm;if(validDistance(d))measured.set(s.id,{station:s,distance:d,durationOutboundMinutes:validDuration(route.durationOutboundMinutes),durationReturnMinutes:validDuration(route.durationReturnMinutes)});else failed.add(s.id);}
      onProgress(state('calculating'));
    }
    const result=state('calculating');
    // A missing route blocks certification only if it might enter the top K.
    return state(result.blockers.length===0&&result.top.length===Math.min(topK,all.length)?'verified':'unverified');
  }
  async function calculateOne(id){
    const key=String(id),s=byId.get(key);
    if(!s)throw new RangeError('Station inconnue');
    if(measured.has(key))return {status:'cached',result:ranked().find(row=>row.id===key)};
    if(signal?.aborted)return {status:'cancelled',result:null};
    requests++;
    let routes;
    try{routes=await routeBatch({origin,stations:[s],signal});}catch(e){routes=[];}
    if(signal?.aborted)return {status:'cancelled',result:null};
    const r=Array.isArray(routes)?routes.find(x=>x&&String(x.id)===key):null;
    if(!validDistance(r?.distanceRoundTripKm)){failed.add(key);return {status:'unavailable',result:null};}
    measured.set(key,{station:s,distance:r.distanceRoundTripKm,durationOutboundMinutes:validDuration(r.durationOutboundMinutes),durationReturnMinutes:validDuration(r.durationReturnMinutes)});failed.delete(key);skipped.delete(key);
    return {status:'calculated',result:ranked().find(row=>row.id===key)};
  }
  return {run,calculateOne,snapshot:()=>state('snapshot')};
}
module.exports={makeTop10};
