'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createLiveRadar}=require('./radar-live');
const garage={schemaVersion:1,revision:0,defaultVehicleId:'a',vehicles:[{id:'a',name:'Auto',fuel:'Gazole',consumption:5,tankCapacity:50,illustration:'berline',fillPercent:80}]};
const origin={lat:43.3,lon:5.4};
const stations=[{id:'1',lat:43.31,lon:5.41,price:1.5}];
function setup(){let clock=1000,calls=0;const radar=createLiveRadar({garage,origin,routeCacheTtlMs:100,now:()=>clock,loadStations:async()=>({stations,complete:true}),routeBatch:async({stations:s})=>{calls++;return s.map(x=>({id:x.id,distanceRoundTripKm:calls*2,durationOutboundMinutes:3}));}});return {radar,tick:n=>clock+=n,calls:()=>calls};}
test('V71: route reused within TTL',async()=>{const x=setup();await x.radar.refresh();await x.radar.setFillPercent(50);assert.equal(x.calls(),1)});
test('V71: expired route recalculated after TTL',async()=>{const x=setup();await x.radar.refresh();x.tick(101);await x.radar.setFillPercent(50);assert.equal(x.calls(),2);assert.equal(x.radar.snapshot().ranking.top[0].distanceRoundTripKm,4)});
test('V71: TTL boundary expires exactly at deadline',async()=>{const x=setup();await x.radar.refresh();x.tick(100);await x.radar.setFillPercent(50);assert.equal(x.calls(),2)});
test('V71: invalid cache configuration rejected',()=>{assert.throws(()=>createLiveRadar({garage,origin,loadStations:()=>{},routeBatch:()=>{},routeCacheTtlMs:-1}),/cache invalide/)});
