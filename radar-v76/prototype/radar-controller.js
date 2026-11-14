'use strict';
const {validateGarage,getDefaultVehicle}=require('./garage');
const {rankStations,canBeatKnownBest}=require('./radar-cost');
const {resolveRoutes,createRouteCache}=require('./routing');

function normalizeStations(stations, fuel){
  if(!Array.isArray(stations))throw new TypeError('Stations invalides');
  const seen=new Set();
  return stations.filter(s=>{
    if(!s||typeof s!=='object'||!['string','number'].includes(typeof s.id)||!String(s.id))throw new TypeError('Station invalide');
    const id=String(s.id);
    if(seen.has(id))throw new TypeError('Station dupliquée');
    seen.add(id);
    return s.fuel===fuel && typeof s.price==='number' && Number.isFinite(s.price) && s.price>0;
  }).map(s=>({...s,id:String(s.id)}));
}
function createRadar({fetchRoutes=resolveRoutes,fetchFn,cache=createRouteCache(),onUpdate=()=>{}}={}){
  if(typeof fetchRoutes!=='function'||typeof onUpdate!=='function')throw new TypeError('Fonctions invalides');
  let generation=0,controller=null,garage=null,origin=null,stations=[],routes=new Map(),phase='idle';
  function currentVehicle(){return garage?getDefaultVehicle(garage):null;}
  function snapshot(){
    const vehicle=currentVehicle();
    const rows=vehicle?rankStations(vehicle,vehicle.fillPercent,stations.map(s=>({...s,distanceRoundTripKm:routes.get(s.id)?.distanceRoundTripKm??null}))):[];
    return {phase,vehicleId:vehicle?.id??null,results:rows,pending:rows.filter(x=>x.status==='route_unavailable').length};
  }
  function publish(){const s=snapshot();onUpdate(s);return s;}
  function cancel(){generation++;controller?.abort();controller=null;}
  function setGarage(next){
    garage=validateGarage(next);
    const v=currentVehicle();
    // The fuel may change, but stations must be refreshed by the caller.
    if(v&&stations.some(s=>s.fuel!==v.fuel)){cancel();stations=[];routes.clear();phase='needs_stations';}
    return publish();
  }
  function setStations(next,from){
    cancel();
    if(!from||typeof from.lat!=='number'||typeof from.lon!=='number')throw new TypeError('Origine invalide');
    origin={lat:from.lat,lon:from.lon};
    const v=currentVehicle();
    if(!v)throw new Error('Véhicule requis');
    stations=normalizeStations(next,v.fuel);
    routes.clear();
    phase=stations.length?'ready':'empty';
    return publish();
  }
  async function calculate({batchSize=10,ttlMs}={}){
    const v=currentVehicle();
    if(!v||!origin)throw new Error('Configuration manquante');
    cancel();
    const id=generation;
    controller=new AbortController();
    const signal=controller.signal;
    phase='routing';publish();
    try{
      const response=await fetchRoutes({origin,stations,fetchFn,cache,batchSize,ttlMs,signal});
      if(id!==generation||signal.aborted)return {status:'superseded'};
      if(!Array.isArray(response)||response.length!==stations.length)throw new Error('Réponse routière incomplète');
      const expected=new Set(stations.map(s=>s.id)),found=new Set();
      for(const r of response){
        if(!r||!expected.has(String(r.id))||found.has(String(r.id)))throw new Error('Identifiant routage invalide');
        found.add(String(r.id));
        if(r.distanceRoundTripKm!==null && (typeof r.distanceRoundTripKm!=='number'||!Number.isFinite(r.distanceRoundTripKm)||r.distanceRoundTripKm<0))throw new Error('Distance routière invalide');
      }
      routes=new Map(response.map(r=>[String(r.id),{distanceRoundTripKm:r.distanceRoundTripKm}]));
      phase=response.some(r=>r.distanceRoundTripKm===null)?'partial':'complete';
      return publish();
    }catch(e){
      if(id!==generation||signal.aborted)return {status:'superseded'};
      phase='route_error';return publish();
    }
  }
  function updateFillPercent(percent){
    const v=currentVehicle();if(!v)throw new Error('Véhicule requis');
    const {editVehicle}=require('./garage');
    garage=editVehicle(garage,v.id,{fillPercent:percent});
    // No routing request: existing route measurements are reused.
    return publish();
  }
  function shortlistByLowerBound(bestTotalCost){
    const v=currentVehicle();if(!v)throw new Error('Véhicule requis');
    return stations.filter(s=>canBeatKnownBest(v,v.fillPercent,s.price,bestTotalCost)).map(s=>s.id);
  }
  return {setGarage,setStations,calculate,updateFillPercent,shortlistByLowerBound,snapshot,cancel};
}
module.exports={createRadar,normalizeStations};
