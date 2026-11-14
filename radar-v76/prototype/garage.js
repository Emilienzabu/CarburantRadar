'use strict';
/* CarburantRadar V32: pure, immutable garage operations; no storage/network side effects. */
const FUELS = Object.freeze(['Gazole','SP95','SP98','E10','E85','GPLc']);
const ICONS = Object.freeze(['citadine_bleue','citadine_rouge','berline','suv','break','sportive','cabriolet','pickup','utilitaire','ancienne','tacot','brouette','fusee','kart','tracteur','licorne']);
const MAX_VEHICLES = 30;
const isObj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const validId = x => typeof x === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(x);
function fail(message){throw new TypeError(message);}
function validateVehicle(v){
  if (!isObj(v)) fail('vehicle must be an object');
  if (!validId(v.id)) fail('invalid vehicle id');
  if (typeof v.name !== 'string' || !v.name.trim() || v.name.trim().length > 60) fail('invalid name');
  if (!FUELS.includes(v.fuel)) fail('invalid fuel');
  if (typeof v.consumption !== 'number' || !Number.isFinite(v.consumption) || v.consumption <= 0 || v.consumption > 100) fail('invalid consumption');
  if (typeof v.tankCapacity !== 'number' || !Number.isFinite(v.tankCapacity) || v.tankCapacity <= 0 || v.tankCapacity > 2000) fail('invalid tank capacity');
  if (!ICONS.includes(v.illustration)) fail('invalid illustration');
  if (!Number.isInteger(v.fillPercent) || v.fillPercent < 1 || v.fillPercent > 100) fail('invalid fill percentage');
  return {id:v.id,name:v.name.trim(),fuel:v.fuel,consumption:v.consumption,tankCapacity:v.tankCapacity,illustration:v.illustration,fillPercent:v.fillPercent};
}
function validateGarage(g){
  if (!isObj(g) || !Array.isArray(g.vehicles) || g.vehicles.length > MAX_VEHICLES) fail('invalid garage');
  if (!Number.isSafeInteger(g.revision) || g.revision < 0) fail('invalid revision');
  const vehicles=g.vehicles.map(validateVehicle);
  if (new Set(vehicles.map(v=>v.id)).size !== vehicles.length) fail('duplicate vehicle id');
  if (vehicles.length===0 ? g.defaultVehicleId!==null : !vehicles.some(v=>v.id===g.defaultVehicleId)) fail('invalid default vehicle');
  return {schemaVersion:1,revision:g.revision,defaultVehicleId:g.defaultVehicleId,vehicles};
}
function emptyGarage(){return {schemaVersion:1,revision:0,defaultVehicleId:null,vehicles:[]};}
function change(g,fn){const original=validateGarage(g);const next=fn(original);next.revision=original.revision+1;return validateGarage(next);}
function addVehicle(g,v){const vehicle=validateVehicle(v);return change(g,x=>{
  if(x.vehicles.length>=MAX_VEHICLES) fail('garage full');
  if(x.vehicles.some(y=>y.id===vehicle.id)) fail('duplicate vehicle id');
  return {...x,vehicles:[...x.vehicles,vehicle],defaultVehicleId:x.defaultVehicleId??vehicle.id};
});}
function editVehicle(g,id,patch){if(!isObj(patch)) fail('invalid patch');
  const allowed=['name','fuel','consumption','tankCapacity','illustration','fillPercent'];
  if(Object.keys(patch).some(k=>!allowed.includes(k))) fail('unsupported patch field');
  return change(g,x=>{
    if(!x.vehicles.some(v=>v.id===id)) fail('vehicle not found');
    return {...x,vehicles:x.vehicles.map(v=>v.id===id?validateVehicle({...v,...patch}):v)};
  });
}
function removeVehicle(g,id){return change(g,x=>{
  if(!x.vehicles.some(v=>v.id===id)) fail('vehicle not found');
  const vehicles=x.vehicles.filter(v=>v.id!==id);
  return {...x,vehicles,defaultVehicleId:x.defaultVehicleId===id?(vehicles[0]?.id??null):x.defaultVehicleId};
});}
function setDefaultVehicle(g,id){return change(g,x=>{
  if(!x.vehicles.some(v=>v.id===id)) fail('vehicle not found');
  return {...x,defaultVehicleId:id};
});}
function getDefaultVehicle(g){const x=validateGarage(g);return x.vehicles.find(v=>v.id===x.defaultVehicleId)??null;}
/* Idempotent: only migrate if garage is empty. Call after reading existing local garage. */
function migrateLegacy(g,legacy,id){const x=validateGarage(g);if(x.vehicles.length)return x;
  if(!isObj(legacy))return x;
  const tank=Number(legacy.tankSize),cons=Number(legacy.consumption);
  if(legacy.tankSize==null || legacy.consumption==null || !Number.isFinite(tank)||tank<=0||tank>2000||!Number.isFinite(cons)||cons<=0||cons>100)return x;
  if(!validId(id)) fail('migration id required');
  const fuel=FUELS.includes(legacy.fuel)?legacy.fuel:'Gazole';
  return addVehicle(x,{id,name:'Mon véhicule',fuel,consumption:cons,tankCapacity:tank,illustration:'citadine_bleue',fillPercent:80});
}
/* No last-write-wins. The backend must atomically compare revision and write. */
function prepareSave(local,server,baseRevision){
  const a=validateGarage(local),b=validateGarage(server);
  if (!Number.isSafeInteger(baseRevision)||baseRevision<0) fail('invalid base revision');
  if (b.revision!==baseRevision || a.revision<=baseRevision)
    return {status:'conflict',server:b,local:a};
  // Multiple offline edits are one atomic server write; server revision advances once.
  return {status:'ready',expectedRevision:baseRevision,next:{...a,revision:baseRevision+1}};
}

module.exports={FUELS,ICONS,MAX_VEHICLES,emptyGarage,validateVehicle,validateGarage,addVehicle,editVehicle,removeVehicle,setDefaultVehicle,getDefaultVehicle,migrateLegacy,prepareSave};
