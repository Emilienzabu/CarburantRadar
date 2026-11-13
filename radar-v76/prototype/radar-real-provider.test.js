'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createRealProviders}=require('./radar-real-provider');
const origin={lat:43.3,lon:5.4};
const station={id:'A',geom:{lat:43.31,lon:5.41},gazole_prix:1.64,adresse:'Rue A',ville:'Marseille'};
function fakeFetch(url){if(url.includes('/table/'))return Promise.resolve({ok:true,json:async()=>({code:'Ok',distances:[[3000]],durations:[[360]]})});return Promise.resolve({ok:true,json:async()=>({results:[station]})});}
test('le proxy legacy est toujours incomplet',async()=>{const p=createRealProviders({fetchFn:fakeFetch});const r=await p.loadStations({fuel:'Gazole',origin});assert.equal(r.complete,false);assert.equal(r.stations[0].price,1.64);assert.match(r.stations[0].name,/Marseille/)});
test('la jauge réutilise les stations en cache',async()=>{let calls=0;const p=createRealProviders({fetchFn:(...args)=>{calls++;return fakeFetch(...args)}});await p.loadStations({fuel:'Gazole',origin});await p.loadStations({fuel:'Gazole',origin,reloadStations:false});assert.equal(calls,1)});
test('un rechargement explicite contacte le proxy',async()=>{let calls=0;const p=createRealProviders({fetchFn:(...args)=>{calls++;return fakeFetch(...args)}});await p.loadStations({fuel:'Gazole',origin});await p.loadStations({fuel:'Gazole',origin});assert.equal(calls,2)});
test('changement carburant invalide le cache',async()=>{let calls=0;const p=createRealProviders({fetchFn:(...args)=>{calls++;return fakeFetch(...args)}});await p.loadStations({fuel:'Gazole',origin});await p.loadStations({fuel:'E10',origin,reloadStations:false});assert.equal(calls,2)});
test('itinéraires aller et retour et durée',async()=>{const p=createRealProviders({fetchFn:fakeFetch});const r=await p.routeBatch({origin,stations:[{id:'A',lat:43.31,lon:5.41}]});assert.equal(r[0].distanceRoundTripKm,6);assert.equal(r[0].durationOutboundMinutes,6)});
test('rayon non autorisé refusé',()=>assert.throws(()=>createRealProviders({fetchFn:fakeFetch,radiusKm:999}),/Rayon/));
test('erreur réseau proxy propagée',async()=>{const p=createRealProviders({fetchFn:async()=>({ok:false,status:503})});await assert.rejects(p.loadStations({fuel:'Gazole',origin}),/503/)});
test('pas de données si réponse invalide',async()=>{const p=createRealProviders({fetchFn:async()=>({ok:true,json:async()=>({})})});await assert.rejects(p.loadStations({fuel:'Gazole',origin}),/invalide/)});
