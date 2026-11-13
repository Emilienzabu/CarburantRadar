'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createLiveRadar}=require('./radar-live');
const {createUiState}=require('./radar-ui');
const garage={schemaVersion:1,revision:0,defaultVehicleId:'a',vehicles:[{id:'a',name:'Auto',fuel:'Gazole',consumption:5,tankCapacity:50,illustration:'berline',fillPercent:80}]};
const origin={lat:43.3,lon:5.4};
const stations=[{id:'1',lat:43.31,lon:5.41,price:1.5},{id:'2',lat:43.32,lon:5.42,price:1.6}];
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
test('error state is displayed instead of infinite loading',()=>{const ui=createUiState({garage,ranking:{status:'error',error:'Service indisponible'}});assert.equal(ui.snapshot().status,'error');assert.match(ui.snapshot().message,/indisponible/)});
test('cancel immediately emits loading false',async()=>{const wait=deferred(),updates=[];const radar=createLiveRadar({garage,origin,loadStations:()=>wait.promise,routeBatch:async()=>[],onUpdate:s=>updates.push(s)});const pending=radar.refresh();assert.equal(radar.snapshot().loading,true);radar.cancel();assert.equal(radar.snapshot().loading,false);assert.equal(updates.at(-1).loading,false);wait.resolve({stations,complete:true});await pending;assert.equal(radar.snapshot().ranking,null)});
test('late manual result cannot overwrite a newer search',async()=>{const wait=deferred();let hold=false;const radar=createLiveRadar({garage,origin,topK:1,loadStations:async()=>({stations,complete:true}),routeBatch:async({stations:batch})=>{if(hold){hold=false;await wait.promise;}return batch.map(s=>({id:s.id,distanceRoundTripKm:2}))}});await radar.refresh();hold=true;const pending=radar.calculateOne('2');const newer=await radar.refresh();assert.equal(newer.ranking.certified,true);wait.resolve();await pending;assert.equal(radar.snapshot().ranking.certified,true)});
test('failed station provider yields explicit error and no verified ranking',async()=>{const radar=createLiveRadar({garage,origin,loadStations:async()=>{throw Error('API indisponible')},routeBatch:async()=>[]});const s=await radar.refresh();assert.equal(s.ranking.status,'error');assert.equal(s.ranking.certified,false);assert.equal(createUiState({garage,ranking:s.ranking}).snapshot().status,'error')});
