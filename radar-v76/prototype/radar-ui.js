'use strict';
/* V49 browser-facing UI state. No network or storage writes. */
function createUiState({garage,ranking,stations=[],onCalculate=()=>{},onFillChange=()=>{},onVehicleChange=()=>{}}){
 let selectedVehicleId=garage?.defaultVehicleId??null,showMore=false,fillOverride=null;
 let current={garage,ranking,stations};
 function snapshot(){const vehicle=current.garage?.vehicles?.find(v=>v.id===selectedVehicleId);
  const all=current.stations||[],byId=new Map(all.map(s=>[String(s.id),s]));
  const r=current.ranking;
  if(!vehicle)return {status:'needs_vehicle',vehicles:current.garage?.vehicles||[],cards:[],more:[],hiddenCount:0};
  const percent=fillOverride??vehicle.fillPercent;
  if(!Number.isInteger(percent)||percent<1||percent>100)throw Error('Jauge invalide');
  if(r?.status==='cancelled')return {status:'cancelled',vehicle,vehicles:current.garage.vehicles,fillPercent:percent,cards:[],more:[],hiddenCount:0};
  if(r?.status==='error')return {status:'error',message:String(r.error||'Recherche indisponible'),vehicle,vehicles:current.garage.vehicles,fillPercent:percent,cards:[],more:[],hiddenCount:0};
  if(!r||!Array.isArray(r.top)||!Array.isArray(r.calculated)||!Array.isArray(r.uncalculated))return {status:'loading',vehicle,vehicles:current.garage.vehicles,fillPercent:percent,cards:[],more:[],hiddenCount:0};
  const calculated=new Map(r.calculated.map(s=>[String(s.id),s]));
  const topIds=new Set(r.top.map(s=>String(s.id)));
  const others=[...r.calculated.map(s=>String(s.id)),...r.uncalculated.map(String),...(r.unavailable||[]).map(String)].filter((id,i,a)=>!topIds.has(id)&&a.indexOf(id)===i);
  const card=id=>{const s=byId.get(String(id))||{},c=calculated.get(String(id));return {id:String(id),name:String(s.name||s.ville||'Station-service'),address:String(s.adresse||s.address||''),pricePerLiter:Number.isFinite(s.price)&&s.price>0?s.price:null,totalCost:Number.isFinite(c?.totalCost)?c.totalCost:null,distanceRoundTripKm:Number.isFinite(c?.distanceRoundTripKm)?c.distanceRoundTripKm:null,durationOutboundMinutes:Number.isFinite(c?.durationOutboundMinutes)?Math.ceil(c.durationOutboundMinutes):null,canCalculate:!c||!Number.isFinite(c.totalCost)};};
  return {status:r.certified?'verified':'unverified',vehicle,vehicles:current.garage.vehicles,fillPercent:percent,cards:r.top.map(s=>card(s.id)),more:showMore?others.map(card):[],hiddenCount:showMore?0:others.length,showMore};
 }
 return {snapshot,setData(next){current={...current,...next};if(!current.garage?.vehicles?.some(v=>v.id===selectedVehicleId))selectedVehicleId=current.garage?.defaultVehicleId??null;if(fillOverride!==null&&current.garage?.vehicles?.find(v=>v.id===selectedVehicleId)?.fillPercent===fillOverride)fillOverride=null;return snapshot();},selectVehicle(id){if(!current.garage?.vehicles?.some(v=>v.id===id))throw Error('Véhicule inconnu');selectedVehicleId=id;fillOverride=null;showMore=false;onVehicleChange(id);return snapshot();},setFillPercent(value){const n=Number(value);if(!Number.isInteger(n)||n<1||n>100)throw Error('Jauge invalide');fillOverride=n;onFillChange(selectedVehicleId,n);return snapshot();},toggleMore(){showMore=!showMore;return snapshot();},calculate(id){const s=snapshot();const c=[...s.cards,...s.more].find(x=>x.id===String(id));if(!c||!c.canCalculate)throw Error('Station non calculable');onCalculate(String(id));return snapshot();}};
}
if(typeof module!=="undefined"&&module.exports)module.exports={createUiState};
if(typeof window!=="undefined")window.CarburantRadarUI={createUiState};
