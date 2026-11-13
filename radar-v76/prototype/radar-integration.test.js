'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createLiveRadar}=require('./radar-live');
const {createUiState}=require('./radar-ui');
const vehicle=(id,fuel,fillPercent=80)=>({id,name:'Véhicule '+id,fuel,consumption:6,tankCapacity:50,illustration:'berline',fillPercent});
const garage={schemaVersion:1,revision:0,defaultVehicleId:'diesel',vehicles:[vehicle('diesel','Gazole'),vehicle('essence','SP95',50)]};
const origin={lat:43.3,lon:5.4};
const stations=[{id:'a',name:'A',lat:43.31,lon:5.41,price:1.6},{id:'b',name:'B',lat:43.32,lon:5.42,price:1.7},{id:'c',name:'C',lat:43.33,lon:5.43,price:1.8}];
function harness({complete=true,failId=null}={}){
 let loads=0,routes=0;let ui;const updates=[];
 const live=createLiveRadar({garage,origin,topK:2,loadStations:async()=>{loads++;return {stations,complete}},routeBatch:async({stations:batch})=>{routes++;return batch.filter(s=>s.id!==failId).map(s=>({id:s.id,distanceRoundTripKm:2,durationOutboundMinutes:4}));},onUpdate:s=>{updates.push(s);ui?.setData({garage:s.garage,ranking:s.ranking,stations:s.stations});}});
 ui=createUiState({garage,ranking:null,stations:[],onFillChange:(_,p)=>live.setFillPercent(p),onVehicleChange:id=>live.selectVehicle(id),onCalculate:id=>live.calculateOne(id)});
 return {live,ui,updates,counts:()=>({loads,routes})};
}
test('V64 integrated: load stations, calculate, render cost distance and duration',async()=>{
 const h=harness();await h.live.refresh();const s=h.ui.snapshot();assert.equal(s.status,'verified');assert.equal(s.cards.length,2);assert.ok(s.cards[0].totalCost>0);assert.equal(s.cards[0].distanceRoundTripKm,2);assert.equal(s.cards[0].durationOutboundMinutes,4);
});
test('V64 integrated: fill updates garage, recomputes UI and avoids proxy/route refetch',async()=>{
 const h=harness();await h.live.refresh();const old=h.counts();h.ui.setFillPercent(40);await new Promise(resolve=>setImmediate(resolve));const s=h.ui.snapshot();assert.equal(s.fillPercent,40);assert.equal(h.live.snapshot().garage.vehicles[0].fillPercent,40);assert.equal(h.counts().loads,old.loads);assert.equal(h.counts().routes,old.routes);
});
test('V64 integrated: selecting vehicle updates fuel and clears old cards during loading',async()=>{
 const h=harness();await h.live.refresh();h.ui.selectVehicle('essence');assert.equal(h.ui.snapshot().status,'loading');await new Promise(resolve=>setImmediate(resolve));const s=h.ui.snapshot();assert.equal(s.vehicle.fuel,'SP95');assert.equal(s.fillPercent,50);assert.equal(h.counts().loads,2);
});
test('V64 integrated: see more and individual calculation',async()=>{
 const h=harness();await h.live.refresh();let s=h.ui.snapshot();assert.equal(s.hiddenCount,1);h.ui.toggleMore();s=h.ui.snapshot();assert.equal(s.more.length,1);assert.equal(s.more[0].id,'c');assert.equal(s.more[0].canCalculate,false);assert.ok(h.live.snapshot().ranking.calculated.some(x=>x.id==='c'));assert.throws(()=>h.ui.calculate('c'),/non calculable/);
});
test('V64 integrated: incomplete provider cannot certify UI',async()=>{
 const h=harness({complete:false});await h.live.refresh();assert.equal(h.ui.snapshot().status,'unverified');
});
test('V64 integrated: missing route has no invented total or travel time',async()=>{
 const h=harness({failId:'a'});await h.live.refresh();h.ui.toggleMore();const s=h.ui.snapshot();const card=[...s.cards,...s.more].find(c=>c.id==='a');assert.ok(card);assert.equal(card.totalCost,null);assert.equal(card.distanceRoundTripKm,null);assert.equal(card.durationOutboundMinutes,null);assert.equal(s.status,'unverified');
});
