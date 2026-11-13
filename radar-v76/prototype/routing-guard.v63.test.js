'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createRoutingGuard}=require('./routing-guard');
const origin={lat:43.3,lon:5.4},station={id:'A',lat:43.31,lon:5.41};
function response(url){const out=url.includes('sources=0&');return {ok:true,json:async()=>({code:'Ok',distances:out?[[1000]]:[[2000]],durations:out?[[60]]:[[120]]})};}
test('V63 moving GPS origin does not reuse cached route',async()=>{
 let calls=0;const guard=createRoutingGuard({fetchFn:async url=>{calls++;return response(url)}});
 await guard.routeBatch({origin,stations:[station]});
 const r=await guard.routeBatch({origin:{...origin,lat:43.3001},stations:[station]});
 assert.equal(calls,4);assert.equal(r[0].fromCache,false);
});
test('V63 same station ID at changed coordinates does not reuse cache',async()=>{
 let calls=0;const guard=createRoutingGuard({fetchFn:async url=>{calls++;return response(url)}});
 await guard.routeBatch({origin,stations:[station]});
 const r=await guard.routeBatch({origin,stations:[{...station,lon:5.42}]});
 assert.equal(calls,4);assert.equal(r[0].fromCache,false);
});
test('V63 expired cache is not used during circuit outage',async()=>{
 let time=0,fail=false;
 const guard=createRoutingGuard({clock:()=>time,ttlMs:100,fetchFn:async url=>fail?{ok:false,status:429,headers:{get:()=> '10'}}:response(url)});
 await guard.routeBatch({origin,stations:[station]});
 time=101;fail=true;await guard.routeBatch({origin,stations:[{...station,id:'B'}]});
 const r=await guard.routeBatch({origin,stations:[station]});
 assert.equal(r[0].status,'route_unavailable');assert.equal(r[0].distanceRoundTripKm,null);
});
test('V63 duplicate IDs are rejected even when circuit is open',async()=>{
 const guard=createRoutingGuard({fetchFn:async()=>({ok:false,status:429,headers:{get:()=> '10'}})});
 await guard.routeBatch({origin,stations:[station]});
 await assert.rejects(guard.routeBatch({origin,stations:[station,{...station,lon:5.42}]}),/dupliqué/);
});
test('V63 invalid GPS coordinates are rejected during outage',async()=>{
 const guard=createRoutingGuard({fetchFn:async()=>({ok:false,status:429,headers:{get:()=> '10'}})});
 await guard.routeBatch({origin,stations:[station]});
 await assert.rejects(guard.routeBatch({origin:{lat:999,lon:5.4},stations:[station]}),/Coordonnées/);
});
