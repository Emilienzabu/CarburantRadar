'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createLiveRadar}=require('./radar-live');
const v={id:'a',name:'Auto',fuel:'Gazole',consumption:5,tankCapacity:50,illustration:'berline',fillPercent:80};
const garage={schemaVersion:1,revision:0,defaultVehicleId:'a',vehicles:[v]};
const origin={lat:43.3,lon:5.4};
const stations=[{id:'1',lat:43.31,lon:5.41,price:1.5},{id:'2',lat:43.32,lon:5.42,price:1.6},{id:'3',lat:43.33,lon:5.43,price:1.7}];
function fixture(extra={}){let loads=0,routes=0,saves=0;const radar=createLiveRadar({garage,origin,topK:2,
 loadStations:async()=>{loads++;return {stations,complete:true}},
 routeBatch:async({stations:s})=>{routes++;return s.map(x=>({id:x.id,distanceRoundTripKm:Number(x.id)*2,durationOutboundMinutes:Number(x.id)*3}))},
 onGarageChange:()=>{saves++},...extra});return {radar,counts:()=>({loads,routes,saves})};}
test('ranks stations and propagates time and distance',async()=>{const {radar}=fixture();const s=await radar.refresh();assert.equal(s.ranking.certified,true);assert.equal(s.ranking.top.length,2);assert.equal(s.ranking.top[0].durationOutboundMinutes,3);assert.equal(s.ranking.top[0].distanceRoundTripKm,2)});
test('does not certify incomplete provider',async()=>{const {radar}=fixture({loadStations:async()=>({stations,complete:false})});assert.equal((await radar.refresh()).ranking.certified,false)});
test('fill percent persists to garage and recalculates',async()=>{const f=fixture();await f.radar.refresh();const before=f.counts();const s=await f.radar.setFillPercent(60);assert.equal(s.garage.vehicles[0].fillPercent,60);assert.equal(f.counts().saves,1);assert.equal(s.ranking.top[0].litersToBuy,30);assert.equal(f.counts().routes,before.routes)});
test('manual calculation for skipped station works',async()=>{const f=fixture();await f.radar.refresh();const s=await f.radar.calculateOne('3');assert.equal(s.ranking.top.length,2);assert.equal(s.ranking.certified,true)});
test('bad station source is not certified',async()=>{const {radar}=fixture({loadStations:async()=>({stations:null,complete:true})});const s=await radar.refresh();assert.equal(s.ranking.certified,false);assert.equal(s.ranking.status,'error')});
test('empty garage works',async()=>{const {radar}=fixture({garage:{...garage,vehicles:[],defaultVehicleId:null}});assert.equal((await radar.refresh()).ranking,null)});
test('invalid percentage rejected',async()=>{const {radar}=fixture();assert.throws(()=>radar.setFillPercent(101))});
test('cancel invalidates pending result',async()=>{let resolve;const {radar}=fixture({loadStations:()=>new Promise(r=>{resolve=r})});const pending=radar.refresh();radar.cancel();resolve({stations,complete:true});await pending;assert.equal(radar.snapshot().ranking,null)});
test('unknown vehicle rejected',()=>{const {radar}=fixture();assert.throws(()=>radar.selectVehicle('other'))});

test('failed explicit reload never reuses an older station list on next gauge update',async()=>{
 let calls=0;const {radar}=fixture({loadStations:async()=>{calls++;if(calls===2)throw Error('proxy indisponible');return {stations,complete:true};}});
 await radar.refresh();assert.equal((await radar.refresh()).ranking.status,'error');
 const result=await radar.setFillPercent(65);assert.equal(calls,3);assert.equal(result.ranking.certified,true);
});
test('pending reload invalidates old source even if cancelled',async()=>{
 let calls=0,resolve;const {radar}=fixture({loadStations:()=>{calls++;if(calls===2)return new Promise(r=>{resolve=r});return Promise.resolve({stations,complete:true});}});
 await radar.refresh();const pending=radar.refresh();radar.cancel();resolve({stations,complete:true});await pending;
 await radar.setFillPercent(70);assert.equal(calls,3);
});

// V57: overlapping requests must never show an older vehicle's stations or ranking.
test('switching vehicles immediately clears old ranking even before new provider resolves',async()=>{
 const second={...v,id:'b',name:'Second',fuel:'SP95',fillPercent:35};
 const two={...garage,vehicles:[v,second]};let finish;const states=[];
 const radar=createLiveRadar({garage:two,origin,topK:2,onUpdate:s=>states.push(s),
  loadStations:({fuel})=>fuel==='SP95'?new Promise(r=>{finish=r}):Promise.resolve({stations,complete:true}),
  routeBatch:async({stations:s})=>s.map(x=>({id:x.id,distanceRoundTripKm:2,durationOutboundMinutes:2}))});
 await radar.refresh();assert.ok(radar.snapshot().ranking.top.length);
 const pending=radar.selectVehicle('b');
 assert.equal(radar.snapshot().selectedVehicleId,'b');
 assert.equal(radar.snapshot().ranking,null);assert.equal(radar.snapshot().stations.length,0);
 assert.ok(states.filter(x=>x.selectedVehicleId==='b').every(x=>x.ranking===null||x.ranking.top.every(y=>y.fuel==='SP95')));
 finish({stations:[{id:'new',lat:43.31,lon:5.41,price:1.6}],complete:true});await pending;
 assert.equal(radar.snapshot().ranking.top[0].id,'new');
});
test('late first vehicle response cannot overwrite a newer vehicle result',async()=>{
 const second={...v,id:'b',name:'Second',fuel:'SP95',fillPercent:25};
 let resolveOld;const radar=createLiveRadar({garage:{...garage,vehicles:[v,second]},origin,
  loadStations:({fuel})=>fuel==='Gazole'?new Promise(r=>{resolveOld=r}):Promise.resolve({stations:[{id:'b1',lat:43.31,lon:5.41,price:1.7}],complete:true}),
  routeBatch:async({stations:s})=>s.map(x=>({id:x.id,distanceRoundTripKm:2,durationOutboundMinutes:2}))});
 const old=radar.refresh();await radar.selectVehicle('b');
 resolveOld({stations,complete:true});await old;
 assert.equal(radar.snapshot().selectedVehicleId,'b');assert.equal(radar.snapshot().ranking.top[0].id,'b1');
});
test('manual cancel clears previously displayed results',async()=>{
 const {radar}=fixture();await radar.refresh();assert.ok(radar.snapshot().ranking);
 const state=radar.cancel();assert.equal(state.ranking,null);assert.equal(state.stations.length,0);assert.equal(state.loading,false);
});
test('rapid fill changes cannot restore a previous percentage ranking',async()=>{
 let resolver;let started;const firstRouteStarted=new Promise(r=>{started=r});let routeCalls=0;const radar=createLiveRadar({garage,origin,loadStations:async()=>({stations,complete:true}),
  routeBatch:({stations:s})=>{routeCalls++;if(routeCalls===1)return new Promise(r=>{resolver=()=>r(s.map(x=>({id:x.id,distanceRoundTripKm:2,durationOutboundMinutes:2})));started()});return Promise.resolve(s.map(x=>({id:x.id,distanceRoundTripKm:2,durationOutboundMinutes:2})));}});
 const first=radar.refresh();await firstRouteStarted;const second=radar.setFillPercent(45);await second;resolver();await first;
 assert.equal(radar.snapshot().garage.vehicles[0].fillPercent,45);
 assert.equal(radar.snapshot().ranking.top[0].litersToBuy,22.5);
});

// V59: concurrent manual route requests must not duplicate API calls.
const manyStations=[...stations,...Array.from({length:9},(_,i)=>({id:String(i+4),lat:43.34+i*.001,lon:5.44,price:3+i*.1}))];
test('two concurrent manual calculations for one station share the same route request',async()=>{
 let release,manualCalls=0;
 const f=fixture({loadStations:async()=>({stations:manyStations,complete:true}),routeBatch:({stations:s})=>{
   if(s.length===1&&s[0].id==='12'){
     manualCalls++;
     return new Promise(resolve=>{release=()=>resolve([{id:'12',distanceRoundTripKm:8,durationOutboundMinutes:6}]);});
   }
   return Promise.resolve(s.map(x=>({id:x.id,distanceRoundTripKm:Number(x.id)*2,durationOutboundMinutes:3})));
 }});
 await f.radar.refresh();
 const first=f.radar.calculateOne('12');const second=f.radar.calculateOne('12');
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(manualCalls,1);release();
 const [a,b]=await Promise.all([first,second]);
 assert.equal(manualCalls,1);assert.deepEqual(a.ranking.top,b.ranking.top);
});
test('cancel while a manual route is pending does not restore obsolete ranking',async()=>{
 let release;
 const f=fixture({loadStations:async()=>({stations:manyStations,complete:true}),routeBatch:({stations:s})=>{
   if(s.length===1&&s[0].id==='12')return new Promise(resolve=>{release=()=>resolve([{id:'12',distanceRoundTripKm:8}]);});
   return Promise.resolve(s.map(x=>({id:x.id,distanceRoundTripKm:2,durationOutboundMinutes:3})));
 }});
 await f.radar.refresh();const pending=f.radar.calculateOne('12');
 await new Promise(resolve=>setImmediate(resolve));
 f.radar.cancel();release();await pending;
 assert.equal(f.radar.snapshot().ranking,null);
});
