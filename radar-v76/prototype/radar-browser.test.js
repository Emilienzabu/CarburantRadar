'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {createUiState}=require('./radar-ui');
const garage={schemaVersion:1,revision:0,defaultVehicleId:'v',vehicles:[{id:'v',name:'Auto',fuel:'Gazole',consumption:5,tankCapacity:50,illustration:'berline',fillPercent:80}]};
const stations=[{id:'1',name:'Station 1',price:1.6},{id:'2',name:'Station 2',price:1.7}];
const ranking={status:'unverified',certified:false,top:[{id:'1'}],calculated:[{id:'1',totalCost:70,distanceRoundTripKm:12,durationOutboundMinutes:8}],uncalculated:['2'],unavailable:[]};
test('Voir plus remains open across background ranking progress',()=>{const ui=createUiState({garage,stations,ranking});ui.toggleMore();assert.equal(ui.snapshot().more.length,1);ui.setData({garage,stations,ranking:{...ranking,status:'verified',certified:true}});assert.equal(ui.snapshot().showMore,true);assert.equal(ui.snapshot().more.length,1)});
test('pending gauge position persists across intermediate render',()=>{const ui=createUiState({garage,stations,ranking});ui.setFillPercent(43);ui.setData({garage,stations,ranking});assert.equal(ui.snapshot().fillPercent,43)});
test('gauge pending override clears once garage confirms value',()=>{const ui=createUiState({garage,stations,ranking});ui.setFillPercent(43);const changed={...garage,vehicles:[{...garage.vehicles[0],fillPercent:43}]};ui.setData({garage:changed});assert.equal(ui.snapshot().fillPercent,43);ui.setData({garage:{...garage,vehicles:[{...garage.vehicles[0],fillPercent:75}]}});assert.equal(ui.snapshot().fillPercent,75)});
test('UI shows error and does not falsely certify',()=>{const ui=createUiState({garage,stations,ranking:{status:'error',error:'Proxy hors ligne'}});assert.equal(ui.snapshot().status,'error');assert.match(ui.snapshot().message,/Proxy/)});
test('HTML debounces gauge and cancels on mode switch',()=>{const html=fs.readFileSync('radar-interface.html','utf8');assert.match(html,/setTimeout\(\(\)=>\{fillTimer=null;state\.setFillPercent\(value\);render\(\)\},250\)/);assert.match(html,/clearPendingFill\(\);live\?\.cancel\(\)/);assert.match(html,/s\.status==='error'/)});
test('browser bundle contains same state behavior as Node module',()=>{assert.equal(fs.readFileSync('radar-ui.browser.js','utf8'),fs.readFileSync('radar-ui.js','utf8'))});

test('browser live bundle contains latest cancellation isolation',()=>{const bundle=fs.readFileSync('radar-live.browser.js','utf8');const module=fs.readFileSync('radar-live.js','utf8');assert.ok(bundle.includes(module));});
