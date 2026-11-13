'use strict';
// Storage-independent prototype. CAS must be implemented atomically by production coordinator.
const crypto=require('node:crypto');
const {buildSnapshot,querySnapshot}=require('./snapshot-france');
const hex=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const VERSION=/^[\w.-]{1,100}$/;
function parseManifest(raw){
 if(!raw)return null;
 let m;try{m=JSON.parse(raw);}catch{throw Error('corrupt_manifest');}
 if(!m||!VERSION.test(m.version)||!/^([a-f0-9]{64})$/.test(m.sha256)||!Number.isInteger(m.count)||m.count<0||!Number.isFinite(Date.parse(m.createdAt)))throw Error('corrupt_manifest');
 return m;
}
function createPersistence({objects,coordinator,clock=()=>new Date().toISOString(),maxAgeMs=86400000}){
 if(!objects||!coordinator||typeof objects.put!=='function'||typeof objects.get!=='function'||typeof coordinator.read!=='function'||typeof coordinator.compareAndSwap!=='function')throw Error('invalid_adapters');
 const key=v=>'france/snapshots/'+v+'.json';
 async function stage(rows,version){
  const snapshot=buildSnapshot(rows,{version,createdAt:clock()});
  const body=JSON.stringify({version:snapshot.version,createdAt:snapshot.createdAt,stations:snapshot.stations});
  const sha256=hex(body);const manifest={version,createdAt:snapshot.createdAt,count:snapshot.count,sha256};
  // Immutable create-if-absent; storage adapter must reject overwrite.
  const inserted=await objects.put(key(version),body,{ifAbsent:true});
  if(inserted!==true)throw Error('version_exists');
  return Object.freeze(manifest);
 }
 async function readVersion(version){
  if(!VERSION.test(version))throw Error('invalid_version');
  const body=await objects.get(key(version));if(typeof body!=='string')throw Error('snapshot_missing');
  let decoded;try{decoded=JSON.parse(body);}catch{throw Error('corrupt_snapshot');}
  if(decoded.version!==version||!Array.isArray(decoded.stations)||!Number.isFinite(Date.parse(decoded.createdAt)))throw Error('corrupt_snapshot');
  return {body,decoded,sha256:hex(body)};
 }
 async function publish(manifest){
  if(!manifest||!VERSION.test(manifest.version))throw Error('invalid_manifest');
  const candidate=await readVersion(manifest.version);
  if(candidate.sha256!==manifest.sha256||candidate.decoded.stations.length!==manifest.count||candidate.decoded.createdAt!==manifest.createdAt)throw Error('integrity_failure');
  // Do not publish an older snapshot over a newer active one.
  const state=await coordinator.read();const current=parseManifest(state?.value??null);
  if(current&&Date.parse(manifest.createdAt)<Date.parse(current.createdAt))throw Error('stale_candidate');
  const ok=await coordinator.compareAndSwap(state?.revision??null,JSON.stringify(manifest));
  if(ok!==true)throw Error('publication_conflict');
  return manifest;
 }
 async function query(params){
  // Caller can pin version across pages; no mixing versions.
  const state=await coordinator.read();const active=parseManifest(state?.value??null);
  if(!active)throw Error('not_ready');
  if(params?.snapshot&&params.snapshot!==active.version){
   // A pinned older version is served only if its manifest is explicitly supplied.
   if(!params.pinnedManifest||params.pinnedManifest.version!==params.snapshot)throw Error('snapshot_version_mismatch');
  }
  const manifest=params?.pinnedManifest?parseManifest(JSON.stringify(params.pinnedManifest)):active;
  const {decoded,sha256}=await readVersion(manifest.version);
  if(sha256!==manifest.sha256||decoded.stations.length!==manifest.count)throw Error('integrity_failure');
  const ageMs=Date.now()-Date.parse(manifest.createdAt);
  const normalized=decoded.stations.map(s=>({id:s.id,geom:{lat:s.lat,lon:s.lon},adresse:s.address,ville:s.city,...Object.fromEntries(Object.entries(s.prices).map(([f,v])=>[require('./snapshot-france').FUELS[f],v]))}));
  const snap=buildSnapshot(normalized,{version:manifest.version,createdAt:manifest.createdAt});
  const response=querySnapshot(snap,params);
  return {...response,storageChecksum:sha256,stale:ageMs>maxAgeMs,ageMs:Math.max(0,ageMs)};
 }
 return {stage,publish,query,readVersion};
}
function memoryAdapters(){
 const data=new Map();let value=null,revision=0;
 return {objects:{async put(k,v,{ifAbsent}={}){if(ifAbsent&&data.has(k))return false;data.set(k,v);return true;},async get(k){return data.get(k)??null;}},coordinator:{async read(){return {value,revision};},async compareAndSwap(expected,next){if(expected!==revision)return false;value=next;revision++;return true;}},data};
}
module.exports={createPersistence,memoryAdapters,parseManifest};
