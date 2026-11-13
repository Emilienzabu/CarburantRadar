'use strict';
// V48: UI-only adapter. Never represents missing routes or incomplete searches as verified.
const {validateGarage}=require('./garage');
const {validatePercent}=require('./radar-cost');
function amount(v){return typeof v==='number'&&Number.isFinite(v)&&v>=0?Number(v.toFixed(2)):null;}
function distance(v){return typeof v==='number'&&Number.isFinite(v)&&v>=0?Number(v.toFixed(1)):null;}
function minutes(v){return typeof v==='number'&&Number.isFinite(v)&&v>=0?Math.ceil(v):null;}
function view({garage,selectedVehicleId,ranking,stations=[],showMore=false,fillPercent,notice=null}={}){
 const g=validateGarage(garage);
 const vehicle=g.vehicles.find(v=>v.id===(selectedVehicleId??g.defaultVehicleId))??null;
 if(!vehicle)return {status:'needs_vehicle',vehicles:g.vehicles.map(v=>({id:v.id,name:v.name,fuel:v.fuel})),cards:[],more:[],message:'Ajoutez un véhicule pour calculer le coût total.'};
 const percent=fillPercent??vehicle.fillPercent;validatePercent(percent);
 if(!ranking||!Array.isArray(ranking.top)||!Array.isArray(ranking.calculated)||!Array.isArray(ranking.uncalculated))throw new TypeError('Classement invalide');
 const byId=new Map(stations.map(s=>[String(s.id),s]));
 const unavailableIds=new Set((ranking.unavailable||[]).map(String));
 const blockerIds=new Set((ranking.blockers||[]).map(String));
 const isError=ranking.status==='error';
 const isCancelled=ranking.status==='cancelled';
 const ranked=new Map(ranking.calculated.map(s=>[String(s.id),s]));
 const topIds=new Set(ranking.top.map(s=>String(s.id)));
 function card(id){const key=String(id),s=byId.get(key)||{},r=ranked.get(key);
  return {id:key,name:String(s.name||s.ville||'Station-service'),address:String(s.adresse||s.address||''),pricePerLiter:amount(s.price),totalCost:amount(r?.totalCost),distanceRoundTripKm:distance(r?.distanceRoundTripKm),durationOutboundMinutes:minutes(r?.durationOutboundMinutes),calculated:Boolean(r&&Number.isFinite(r.totalCost)),canCalculate:!r&&!isError&&!isCancelled,routeUnavailable:unavailableIds.has(key),blocksCertification:blockerIds.has(key)};}
 const top=ranking.top.map(s=>card(s.id));
 const otherIds=[...ranked.keys(),...ranking.uncalculated.map(String),...(ranking.unavailable||[]).map(String)].filter((id,i,a)=>!topIds.has(id)&&a.indexOf(id)===i);
 return {status:isError?'error':isCancelled?'cancelled':ranking.certified?'verified':'unverified',vehicle:{id:vehicle.id,name:vehicle.name,fuel:vehicle.fuel,illustration:vehicle.illustration},vehicles:g.vehicles.map(v=>({id:v.id,name:v.name,fuel:v.fuel})),fillPercent:percent,notice,top,more:showMore?otherIds.map(card):[],hiddenCount:showMore?0:otherIds.length,showMore:Boolean(showMore),message:isError?'Recherche impossible : '+String(ranking.error||'erreur réseau'):isCancelled?'Recherche annulée.':ranking.certified?'Top 10 vérifié sur les stations récupérées.':'Classement provisoire : certaines stations ou certains trajets ne sont pas vérifiés.'};
}
module.exports={view};
