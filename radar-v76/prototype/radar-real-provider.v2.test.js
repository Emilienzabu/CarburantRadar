'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');
const {createRealProviders}=require('./radar-real-provider');
const origin={lat:43.3,lon:5.4};
const station=i=>({id:String(i),lat:43.3,lon:5.4,price:1.6,city:'Marseille'});
const sha='a'.repeat(64);
test('V2: pagination complète et certification de couverture',async()=>{
 const urls=[];
 const fetchFn=async url=>{const u=new URL(url);urls.push(u);const offset=Number(u.searchParams.get('cursor'));const total=125;const count=Math.min(100,total-offset);return {ok:true,json:async()=>({schemaVersion:2,complete:true,snapshot:'v1',checksum:sha,createdAt:'2026-11-14T00:00:00Z',total,results:Array.from({length:count},(_,i)=>station(i+offset)),nextCursor:offset+count<total?offset+count:null})}};
 const p=createRealProviders({fetchFn,snapshotV2Url:'https://example.com/v2/france',radiusKm:5});
 const r=await p.loadStations({fuel:'Gazole',origin});assert.equal(r.complete,true);assert.equal(r.stations.length,125);assert.equal(r.source,'snapshot_v2');assert.equal(urls.length,2);assert.equal(urls[1].searchParams.get('snapshot'),'v1');
});
test('V2: pagination invalide interdit la certification',async()=>{
 const fetchFn=async()=>({ok:true,json:async()=>({schemaVersion:2,complete:true,snapshot:'v1',checksum:sha,createdAt:'2026-11-14T00:00:00Z',total:101,results:[station(1)],nextCursor:null})});
 const p=createRealProviders({fetchFn,snapshotV2Url:'https://example.com/v2/france'});
 const r=await p.loadStations({fuel:'Gazole',origin});assert.equal(r.complete,false);assert.equal(r.stations.length,0);assert.match(r.reason,/invalid_snapshot_cursor/);
});
test('legacy proxy stays explicitly uncertified',async()=>{
 const fetchFn=async()=>({ok:true,json:async()=>({})});
 const p=createRealProviders({fetchFn});try{const r=await p.loadStations({fuel:'Gazole',origin});assert.equal(r.complete,false)}catch(e){assert.ok(e)}
});
