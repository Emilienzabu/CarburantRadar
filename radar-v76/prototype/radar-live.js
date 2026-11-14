'use strict';
// V50: orchestrator; inject station provider and routing provider. No production writes.
const {validateGarage,editVehicle}=require('./garage');
const {makeTop10}=require('./radar-top10');
function createLiveRadar({garage,origin,loadStations,routeBatch,onUpdate=()=>{},onGarageChange=()=>{},topK=10,routeCacheTtlMs=15*60*1000,now=()=>Date.now()}={}){
 let currentGarage=validateGarage(garage),selected=currentGarage.defaultVehicleId;
 if(typeof loadStations!=='function'||typeof routeBatch!=='function')throw new TypeError('Fournisseurs requis');
 if(!Number.isFinite(routeCacheTtlMs)||routeCacheTtlMs<0||typeof now!=='function')throw new TypeError('Configuration du cache invalide');
 let generation=0,controller=null,engine=null,stations=[],ranking=null,loading=false,showMore=false;
 let stationSource=null; // Only reuse for the same fuel and origin, never across fuel changes.
 const cache=new Map();
 const pendingManual=new Map(); // Deduplicate concurrent requests for the same station and search.
 const vehicle=()=>currentGarage.vehicles.find(v=>v.id===selected)||null;
 const key=(o,s)=>[o.lat,o.lon,s.lat,s.lon].join(':');
 async function cachedRoutes({origin,stations:batch,signal}){
  const missing=batch.filter(s=>{const entry=cache.get(key(origin,s));return !entry||entry.expiresAt<=now();}),result=[];
  if(missing.length){const fetched=await routeBatch({origin,stations:missing,signal});if(signal?.aborted)return [];
   for(const r of Array.isArray(fetched)?fetched:[]){const s=missing.find(x=>String(x.id)===String(r?.id));if(s&&Number.isFinite(r.distanceRoundTripKm)&&r.distanceRoundTripKm>=0)cache.set(key(origin,s),{...r,id:String(s.id),expiresAt:now()+routeCacheTtlMs});}
  }
  for(const s of batch){const r=cache.get(key(origin,s));if(r&&r.expiresAt>now())result.push({...r,id:String(s.id)});}
  return result;
 }
 function snapshot(){return {garage:currentGarage,selectedVehicleId:selected,stations,ranking,loading,showMore};}
 function emit(){onUpdate(snapshot());}
 function invalidate({clear=true}={}){
  generation++;controller?.abort();controller=null;loading=false;pendingManual.clear();
  if(clear){stations=[];ranking=null;engine=null;showMore=false;}
 }
 function cancel(){invalidate();emit();return snapshot();}
 async function refresh({reloadStations=true}={}){
  // Clear previous vehicle's results before notifying listeners, including during loading.
  invalidate();if(reloadStations)stationSource=null;const v=vehicle();
  if(!v){emit();return snapshot();}
  const token=generation,signal=(controller=new AbortController()).signal;loading=true;emit();
  try{
   const source=(!reloadStations&&stationSource&&stationSource.fuel===v.fuel)
    ?stationSource.data:await loadStations({fuel:v.fuel,origin,signal,reloadStations});
   if(signal.aborted||token!==generation)return snapshot();
   if(!source||!Array.isArray(source.stations))throw Error('Liste de stations invalide');
   stations=source.stations;
   if(!signal.aborted)stationSource={fuel:v.fuel,data:source};
   // Provider must explicitly confirm complete coverage. Otherwise never certify.
   const complete=source.complete===true;
   engine=makeTop10({vehicle:v,fillPercent:v.fillPercent,stations,origin,routeBatch:cachedRoutes,topK,signal,
     onProgress:r=>{if(token===generation&&!signal.aborted){ranking={...r,certified:false};emit();}}});
   const r=await engine.run();
   if(signal.aborted||token!==generation)return snapshot();
   ranking={...r,certified:complete&&r.certified};
  }catch(e){if(token===generation&&!signal.aborted){ranking={status:'error',top:[],calculated:[],uncalculated:stations.map(s=>String(s.id)),unavailable:[],certified:false,error:String(e.message||e)};}}
  finally{if(token===generation){loading=false;emit();}}
  return snapshot();
 }
 function selectVehicle(id){if(!currentGarage.vehicles.some(v=>v.id===id))throw Error('Véhicule inconnu');selected=id;return refresh();}
 function setFillPercent(value){const v=vehicle();if(!v)throw Error('Aucun véhicule');const n=Number(value);if(!Number.isInteger(n)||n<1||n>100)throw Error('Pourcentage invalide');
  currentGarage=editVehicle(currentGarage,v.id,{fillPercent:n});onGarageChange(currentGarage);return refresh({reloadStations:false});
 }
 async function calculateOne(id){
  if(!engine||loading)throw Error('Calcul indisponible');
  const stationId=String(id),token=generation;
  if(pendingManual.has(stationId))return pendingManual.get(stationId);
  const activeEngine=engine;
  const task=(async()=>{
   const res=await activeEngine.calculateOne(stationId);
   if(token!==generation||activeEngine!==engine)return snapshot();
   // A manual calculation can change the top K. Re-run using cached routes and same stations.
   if(res.status==='calculated')return refresh({reloadStations:false});
   if(res.status==='cached'){emit();return snapshot();}
   ranking={...engine.snapshot(),certified:false};emit();return snapshot();
  })();
  pendingManual.set(stationId,task);
  try{return await task;}finally{if(pendingManual.get(stationId)===task)pendingManual.delete(stationId);}
 }

 return {snapshot,refresh,selectVehicle,setFillPercent,calculateOne,cancel};
}
module.exports={createLiveRadar};
