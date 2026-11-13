'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createRoutingGuard}=require('./routing-guard');
const origin={lat:43.3,lon:5.4},station={id:'A',lat:43.31,lon:5.41};
function mock(url){const outbound=url.includes('sources=0&');return Promise.resolve({ok:true,json:async()=>({code:'Ok',distances:outbound?[[5000]]:[[6000]],durations:outbound?[[300]]:[[360]]})});}
test('distance and time from two OSRM directions',async()=>{const g=createRoutingGuard({fetchFn:mock});const a=await g.routeBatch({origin,stations:[station]});assert.equal(a[0].distanceRoundTripKm,11);assert.equal(a[0].durationOutboundMinutes,5);assert.equal(a[0].durationReturnMinutes,6);});
test('cached second call avoids network',async()=>{let n=0;const g=createRoutingGuard({fetchFn:u=>{n++;return mock(u)}});await g.routeBatch({origin,stations:[station]});const b=await g.routeBatch({origin,stations:[station]});assert.equal(n,2);assert.equal(b[0].fromCache,true);});
test('cache bounded after successful requests',async()=>{const g=createRoutingGuard({fetchFn:mock,cacheLimit:1});await g.routeBatch({origin,stations:[station]});await g.routeBatch({origin,stations:[{...station,id:'B',lon:5.42}]});assert.equal(g.status().cached,1);});
test('failed fetch returns unavailable not fake cost',async()=>{const g=createRoutingGuard({fetchFn:async()=>{throw Error('offline')}});const a=await g.routeBatch({origin,stations:[station]});assert.equal(a[0].status,'route_unavailable');assert.equal(a[0].distanceRoundTripKm,null);});
test('breaker opens after failures and avoids new calls',async()=>{let n=0;const g=createRoutingGuard({fetchFn:async()=>{n++;throw Error('offline')},failureThreshold:2});await g.routeBatch({origin,stations:[station]});await g.routeBatch({origin,stations:[station]});assert.equal(g.status().circuitOpen,true);const before=n;await g.routeBatch({origin,stations:[station]});assert.equal(n,before);});
test('breaker recovers after cooldown',async()=>{let t=1000,good=false;const g=createRoutingGuard({clock:()=>t,fetchFn:u=>good?mock(u):Promise.reject(Error('offline')),failureThreshold:1,cooldownMs:100});await g.routeBatch({origin,stations:[station]});t+=101;good=true;const a=await g.routeBatch({origin,stations:[station]});assert.equal(a[0].status,'routed');assert.equal(g.status().circuitOpen,false);});
test('invalid configuration rejected',()=>{assert.throws(()=>createRoutingGuard({fetchFn:mock,maxConcurrent:0}),RangeError);assert.throws(()=>createRoutingGuard({fetchFn:mock,timeoutMs:-1}),RangeError);});
test('empty list does not fetch',async()=>{const g=createRoutingGuard({fetchFn:()=>{throw Error('should not call')}});assert.deepEqual(await g.routeBatch({origin,stations:[]}),[]);});
test('already aborted request rejected',async()=>{const g=createRoutingGuard({fetchFn:mock});const a=new AbortController();a.abort();await assert.rejects(g.routeBatch({origin,stations:[station],signal:a.signal}),/aborted/);});
test('simultaneous requests limited to one',async()=>{let inFlight=0,max=0;const fetchFn=async u=>{inFlight++;max=Math.max(max,inFlight);await new Promise(r=>setTimeout(r,5));inFlight--;return mock(u)};const g=createRoutingGuard({fetchFn,maxConcurrent:1});await Promise.all([g.routeBatch({origin,stations:[station]}),g.routeBatch({origin,stations:[{...station,id:'B'}]})]);assert.equal(max,1);});
test('bad HTTP response trips failure count',async()=>{const g=createRoutingGuard({fetchFn:async()=>({ok:false}),failureThreshold:1});await g.routeBatch({origin,stations:[station]});assert.equal(g.status().circuitOpen,true);});
test('legitimate unreachable route does not trip breaker',async()=>{const g=createRoutingGuard({fetchFn:async u=>({ok:true,json:async()=>({code:'Ok',distances:u.includes('sources=0&')?[[null]]:[[null]]})}),failureThreshold:1});const r=await g.routeBatch({origin,stations:[station]});assert.equal(r[0].status,'route_unavailable');assert.equal(g.status().circuitOpen,false);});
test('HTTP 429 Retry-After blocks repeated calls until expiry',async()=>{
 let t=1000,n=0;
 const g=createRoutingGuard({clock:()=>t,cooldownMs:1000,fetchFn:async url=>{n++;return n===1?{ok:false,status:429,headers:{get:()=> '5'}}:mock(url)}});
 const a=await g.routeBatch({origin,stations:[station]});assert.equal(a[0].status,'route_unavailable');
 assert.equal(g.status().rateLimited,true);assert.equal(g.status().retryAfterMs,5000);
 await g.routeBatch({origin,stations:[station]});assert.equal(n,1);
 t+=5001;const b=await g.routeBatch({origin,stations:[station]});assert.equal(b[0].status,'routed');assert.equal(n,3);
});
test('HTTP 503 invalid Retry-After uses cooldown',async()=>{
 let t=100,n=0;const g=createRoutingGuard({clock:()=>t,cooldownMs:1200,fetchFn:async()=>{n++;return {ok:false,status:503,headers:{get:()=> 'invalid'}}}});
 await g.routeBatch({origin,stations:[station]});assert.equal(g.status().retryAfterMs,1200);
 await g.routeBatch({origin,stations:[station]});assert.equal(n,1);
});
test('Retry-After duration capped at one hour',async()=>{
 const g=createRoutingGuard({clock:()=>0,fetchFn:async()=>({ok:false,status:429,headers:{get:()=> '9999999'}})});
 await g.routeBatch({origin,stations:[station]});assert.equal(g.status().retryAfterMs,3600000);
});

test('partial OSRM batch failure preserves successful station routes',async()=>{
 const stations=Array.from({length:11},(_,i)=>({id:String(i),lat:43.31+i*.001,lon:5.41+i*.001}));
 let calls=0;
 const fetchFn=async url=>{calls++;if(calls===3)throw Error('temporary outage');
  const count=url.split('?')[0].split('/').pop().split(';').length-1;
  const outbound=url.includes('sources=0&');
  return {ok:true,json:async()=>({code:'Ok',distances:outbound?[Array(count).fill(1000)]:Array.from({length:count},()=>[1200]),durations:outbound?[Array(count).fill(100)]:Array.from({length:count},()=>[120])})};
 };
 const guard=createRoutingGuard({fetchFn,failureThreshold:1});
 const rows=await guard.routeBatch({origin,stations});
 assert.equal(rows.length,11);
 assert.equal(rows.filter(r=>r.status==='routed').length,10);
 assert.equal(rows.filter(r=>r.status==='route_unavailable').length,1);
 assert.equal(guard.status().circuitOpen,true);
});

test('partial failure does not discard valid cached routes',async()=>{
 let fail=false;
 const fetchFn=async url=>fail?{ok:false,status:503}:mock(url);
 const guard=createRoutingGuard({fetchFn});
 await guard.routeBatch({origin,stations:[station]});
 fail=true;
 const rows=await guard.routeBatch({origin,stations:[station,{id:'B',lat:43.32,lon:5.42}]});
 assert.equal(rows[0].status,'routed');assert.equal(rows[0].fromCache,true);
 assert.equal(rows[1].status,'route_unavailable');
});


test('V62 cached routes remain usable during rate limit',async()=>{
 let t=1000,fail=false,calls=0;
 const guard=createRoutingGuard({clock:()=>t,fetchFn:async url=>{calls++;return fail?{ok:false,status:429,headers:{get:()=> '10'}}:mock(url)}});
 await guard.routeBatch({origin,stations:[station]});
 fail=true;
 await guard.routeBatch({origin,stations:[{id:'B',lat:43.32,lon:5.42}]});
 const before=calls;
 const result=await guard.routeBatch({origin,stations:[station,{id:'C',lat:43.33,lon:5.43}]});
 assert.equal(calls,before);
 assert.equal(result[0].status,'routed');assert.equal(result[0].fromCache,true);
 assert.equal(result[1].status,'route_unavailable');
});

test('V62 rate limit mid multi-batch stops further network requests',async()=>{
 let calls=0;
 const stations=Array.from({length:21},(_,i)=>({id:String(i),lat:43.31+i*.001,lon:5.41+i*.001}));
 const guard=createRoutingGuard({fetchFn:async url=>{calls++;return {ok:false,status:429,headers:{get:()=> '10'}}}});
 const result=await guard.routeBatch({origin,stations});
 assert.equal(calls,1);assert.equal(result.length,21);
 assert.ok(result.every(r=>r.status==='route_unavailable'));
});
