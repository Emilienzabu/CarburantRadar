'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createLiveRadar}=require('./radar-live');
const origin={lat:43.3,lon:5.4};
const vehicles=[{id:'a',name:'Diesel',fuel:'Gazole',consumption:6,tankCapacity:50,illustration:'berline',fillPercent:80},{id:'b',name:'Essence',fuel:'SP95',consumption:7,tankCapacity:45,illustration:'berline',fillPercent:80}];
const garage={schemaVersion:1,revision:0,defaultVehicleId:'a',vehicles};
function make(){const calls=[];const radar=createLiveRadar({garage,origin,topK:1,loadStations:async args=>{calls.push(args.fuel);return {stations:[{id:args.fuel,lat:43.31,lon:5.41,price:1.6}],complete:true}},routeBatch:async ({stations})=>stations.map(s=>({id:s.id,distanceRoundTripKm:2,durationOutboundMinutes:3}))});return {radar,calls};}
test('V55 gauge reuses station source without another proxy request',async()=>{const {radar,calls}=make();await radar.refresh();await radar.setFillPercent(30);await radar.setFillPercent(40);assert.deepEqual(calls,['Gazole']);assert.equal(radar.snapshot().ranking.top[0].litersToBuy,20)});
test('V55 switching fuel fetches fresh source, never diesel cache',async()=>{const {radar,calls}=make();await radar.refresh();await radar.selectVehicle('b');assert.deepEqual(calls,['Gazole','SP95']);assert.equal(radar.snapshot().stations[0].id,'SP95')});
test('V55 returning to earlier fuel refreshes provider',async()=>{const {radar,calls}=make();await radar.refresh();await radar.selectVehicle('b');await radar.selectVehicle('a');assert.deepEqual(calls,['Gazole','SP95','Gazole'])});
test('V55 explicit refresh reloads proxy',async()=>{const {radar,calls}=make();await radar.refresh();await radar.refresh();assert.deepEqual(calls,['Gazole','Gazole'])});
