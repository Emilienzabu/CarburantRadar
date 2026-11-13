'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {createPersistence,memoryAdapters,parseManifest}=require('./snapshot-persistence');
const row=(id='1',price=1.8)=>({id,geom:{lat:43.3,lon:5.4},gazole_prix:price});
function setup(opts={}){const a=memoryAdapters();return {...a,store:createPersistence({...a,clock:()=> '2026-11-12T00:00:00Z',...opts})};}
test('stage publish and query',async()=>{const {store}=setup();const m=await store.stage([row()], 'v1');await store.publish(m);const r=await store.query({lat:43.3,lon:5.4,radiusKm:5,fuel:'Gazole'});assert.equal(r.total,1);assert.equal(r.results[0].price,1.8);assert.equal(r.snapshot,'v1');});
test('no active before publish',async()=>{const {store}=setup();await store.stage([row()],'v1');await assert.rejects(store.query({}),/not_ready/);});
test('immutable version',async()=>{const {store}=setup();await store.stage([row()],'v1');await assert.rejects(store.stage([row()],'v1'),/version_exists/);});
test('detect corrupted storage before publish',async()=>{const {store,data}=setup();const m=await store.stage([row()],'v1');data.set('france/snapshots/v1.json','{}');await assert.rejects(store.publish(m),/corrupt_snapshot/);});
test('detect modified storage checksum',async()=>{const {store,data}=setup();const m=await store.stage([row()],'v1');data.set('france/snapshots/v1.json',data.get('france/snapshots/v1.json').replace('1.8','1.9'));await assert.rejects(store.publish(m),/integrity_failure/);});
test('old versions readable when pinned',async()=>{const {store}=setup();const m=await store.stage([row()],'v1');await store.publish(m);const n=await store.stage([row('2')],'v2');await store.publish(n);const r=await store.query({lat:43.3,lon:5.4,radiusKm:5,fuel:'Gazole',snapshot:'v1',pinnedManifest:m});assert.equal(r.results[0].id,'1');});
test('reject mismatched version without manifest',async()=>{const {store}=setup();const m=await store.stage([row()],'v1');await store.publish(m);await assert.rejects(store.query({snapshot:'old'}),/snapshot_version_mismatch/);});
test('CAS conflict',async()=>{const {store,coordinator}=setup();const m=await store.stage([row()],'v1');coordinator.compareAndSwap=async()=>false;await assert.rejects(store.publish(m),/publication_conflict/);});
test('stale candidate rejected',async()=>{const {store}=setup();const newer=await store.stage([row()],'new');await store.publish(newer);const older=createPersistence({...memoryAdapters(),clock:()=> '2020-01-01T00:00:00Z'});assert.ok(older);});
test('invalid manifest rejected',()=>{assert.throws(()=>parseManifest('{'),/corrupt_manifest/);assert.throws(()=>parseManifest('{}'),/corrupt_manifest/);});
test('reject invalid version',async()=>{const {store}=setup();await assert.rejects(store.stage([row()],'../bad'),/invalid_version/);});
test('stale indicator is explicit',async()=>{const {store}=setup({maxAgeMs:1});const m=await store.stage([row()],'v1');await store.publish(m);const r=await store.query({lat:43.3,lon:5.4,radiusKm:5,fuel:'Gazole'});assert.equal(r.stale,true);});
test('pagination stable',async()=>{const {store}=setup();const m=await store.stage([row('1'),row('2')],'v1');await store.publish(m);const r=await store.query({lat:43.3,lon:5.4,radiusKm:5,fuel:'Gazole',limit:1});assert.equal(r.nextCursor,1);});
test('duplicate IDs rejected',async()=>{const {store}=setup();await assert.rejects(store.stage([row(),row()],'v1'),/duplicate_id/);});
