'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('radar-interface.html','utf8');
test('mode generation prevents delayed geolocation from overwriting demo',()=>{assert.match(html,/const generation=\+\+modeGeneration;clearPendingFill\(\);live\?\.cancel\(\)/);assert.match(html,/if\(generation!==modeGeneration\)return;\s*const origin/)});
test('stale real request does not overwrite status',()=>assert.match(html,/if\(generation===modeGeneration\)\$\('realStatus'\)/));
test('real request does not announce success on failed ranking',()=>assert.match(html,/result\.ranking\?\.status==='error'/));
test('browser smoke executes browser bundles without Node require',()=>{
 const window={};const context=vm.createContext({window,console,AbortController,URL,URLSearchParams,fetch:async()=>{throw Error('Unexpected network')}});
 for(const name of ['radar-ui.browser.js','radar-live.browser.js','radar-real-provider.browser.js'])vm.runInContext(fs.readFileSync(name,'utf8'),context,{filename:name});
 assert.equal(typeof window.CarburantRadarUI.createUiState,'function');assert.equal(typeof window.CarburantRadarLive.createLiveRadar,'function');assert.equal(typeof window.CarburantRadarReal.createRealProviders,'function');
 const garage={schemaVersion:1,revision:0,defaultVehicleId:'v',vehicles:[{id:'v',name:'Auto',fuel:'Gazole',consumption:6,tankCapacity:50,illustration:'berline',fillPercent:80}]};
 const ui=window.CarburantRadarUI.createUiState({garage,stations:[{id:'a',name:'A',price:1.5},{id:'b',name:'B',price:1.6}],ranking:{status:'unverified',certified:false,top:[{id:'a'}],calculated:[{id:'a',totalCost:60,distanceRoundTripKm:5,durationOutboundMinutes:6}],uncalculated:['b'],unavailable:[]}});
 ui.toggleMore();ui.setFillPercent(44);ui.setData({garage});assert.equal(ui.snapshot().more.length,1);assert.equal(ui.snapshot().fillPercent,44);
});
