'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createLiveRadar}=require('./radar-live');
const {createUiState}=require('./radar-ui');
const garage={schemaVersion:1,revision:0,defaultVehicleId:'v',vehicles:[{id:'v',name:'Auto',fuel:'Gazole',consumption:6,tankCapacity:50,illustration:'berline',fillPercent:80}]};
const origin={lat:43.3,lon:5.4};
const stations=[{id:'s',name:'Station',lat:43.31,lon:5.41,price:1.6}];
function setup(loadStations){let ui;const live=createLiveRadar({garage,origin,loadStations,routeBatch:async({stations})=>stations.map(s=>({id:s.id,distanceRoundTripKm:4,durationOutboundMinutes:5})),onUpdate:s=>ui.setData({garage:s.garage,ranking:s.ranking,stations:s.stations})});ui=createUiState({garage,ranking:null,stations:[]});return {live,ui};}
test('V65: cancelled status appears as cancellation, not indefinite loading',()=>{const ui=createUiState({garage,ranking:{status:'cancelled'},stations});assert.equal(ui.snapshot().status,'cancelled');assert.equal(ui.snapshot().cards.length,0)});
test('V65: network failure produces error without verified cards',async()=>{const h=setup(async()=>{throw Error('Proxy indisponible')});await h.live.refresh();assert.equal(h.ui.snapshot().status,'error');assert.match(h.ui.snapshot().message,/Proxy indisponible/);assert.equal(h.ui.snapshot().cards.length,0)});
test('V65: failed proxy request can recover on next refresh',async()=>{let attempts=0;const h=setup(async()=>{if(++attempts===1)throw Error('temporaire');return {stations,complete:true}});await h.live.refresh();assert.equal(h.ui.snapshot().status,'error');await h.live.refresh();assert.equal(h.ui.snapshot().status,'verified');assert.equal(h.ui.snapshot().cards.length,1)});
test('V65: late old response cannot overwrite newer successful results',async()=>{let firstResolve,call=0;const h=setup(async()=>{if(++call===1)return new Promise(r=>{firstResolve=r});return {stations,complete:true}});const old=h.live.refresh();await Promise.resolve();await h.live.refresh();assert.equal(h.ui.snapshot().status,'verified');firstResolve({stations:[],complete:true});await old;assert.equal(h.ui.snapshot().status,'verified');assert.equal(h.ui.snapshot().cards.length,1)});
test('V65: cancelling a pending request removes previous cards',async()=>{let resolve;const h=setup(async()=>new Promise(r=>resolve=r));const task=h.live.refresh();h.live.cancel();resolve({stations,complete:true});await task;assert.equal(h.ui.snapshot().cards.length,0);assert.notEqual(h.ui.snapshot().status,'verified')});
