'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {makeTop10}=require('./radar-top10');
const vehicle={id:'a',name:'A',fuel:'Gazole',consumption:6,tankCapacity:50};
const stations=[{id:'a',price:1.5,lat:43.31,lon:5.41},{id:'b',price:1.6,lat:43.32,lon:5.42}];
function make(routes){return makeTop10({vehicle,fillPercent:80,stations,origin:{lat:43.3,lon:5.4},topK:2,routeBatch:async({stations})=>stations.map(s=>({id:s.id,...routes[s.id]}))});}
test('top results include road distance and outbound minutes',async()=>{const e=make({a:{distanceRoundTripKm:5,durationOutboundMinutes:8,durationReturnMinutes:10},b:{distanceRoundTripKm:10,durationOutboundMinutes:12,durationReturnMinutes:14}});const r=await e.run();assert.equal(r.top[0].durationOutboundMinutes,8);assert.equal(r.top[0].distanceRoundTripKm,5)});
test('unknown time is null, not zero',async()=>{const e=make({a:{distanceRoundTripKm:5},b:{distanceRoundTripKm:10}});const r=await e.run();assert.equal(r.top[0].durationOutboundMinutes,null)});
test('manual calculation returns duration',async()=>{const e=make({a:{distanceRoundTripKm:5,durationOutboundMinutes:8},b:{distanceRoundTripKm:10,durationOutboundMinutes:12}});const r=await e.calculateOne('a');assert.equal(r.result.durationOutboundMinutes,8)});
test('cached manual calculation keeps duration',async()=>{const e=make({a:{distanceRoundTripKm:5,durationOutboundMinutes:8},b:{distanceRoundTripKm:10,durationOutboundMinutes:12}});await e.calculateOne('a');const r=await e.calculateOne('a');assert.equal(r.status,'cached');assert.equal(r.result.durationOutboundMinutes,8)});
test('negative time never displayed',async()=>{const e=make({a:{distanceRoundTripKm:5,durationOutboundMinutes:-1},b:{distanceRoundTripKm:10}});const r=await e.run();assert.equal(r.top[0].durationOutboundMinutes,null)});
