'use strict';
// V46: bridge between a versioned snapshot endpoint and the existing Top-10 engine.
// Completeness is a prerequisite for certification; freshness is informational only.
const {makeTop10}=require('./radar-top10');
const {evaluateFreshness,publicStatus}=require('./freshness');
const {validateStations}=require('./radar-search');
const FUELS=new Set(['Gazole','SP95','SP98','E10','E85','GPLc']);
function checkOrigin(o){if(!o||!Number.isFinite(o.lat)||Math.abs(o.lat)>90||!Number.isFinite(o.lon)||Math.abs(o.lon)>180)throw Error('invalid_origin');}
function parsePage(p){
 if(!p||p.schemaVersion!==2||p.complete!==true||typeof p.snapshot!=='string'||!p.snapshot||typeof p.checksum!=='string'||!p.checksum||!Number.isInteger(p.total)||p.total<0||!Array.isArray(p.results))throw Error('invalid_snapshot_page');
 if(p.nextCursor!==null&&(!Number.isInteger(p.nextCursor)||p.nextCursor<0))throw Error('invalid_cursor');
 return p;
}
async function loadSnapshotStations({queryPage,origin,radiusKm,fuel,pageSize=100,maxPages=500,signal}={}){
 if(typeof queryPage!=='function'||!FUELS.has(fuel)||!Number.isFinite(radiusKm)||radiusKm<=0||radiusKm>50||!Number.isInteger(pageSize)||pageSize<1||pageSize>100||!Number.isInteger(maxPages)||maxPages<1)throw Error('invalid_loader_config');
 checkOrigin(origin);
 let cursor=0,identity=null,createdAt=null,total=null,pages=0;
 const stations=[],ids=new Set(),visited=new Set();
 while(true){
  if(signal?.aborted)throw Error('aborted');
  if(pages>=maxPages)throw Error('page_limit');
  if(visited.has(cursor))throw Error('cursor_loop');visited.add(cursor);
  const p=parsePage(await queryPage({lat:origin.lat,lon:origin.lon,radiusKm,fuel,offset:cursor,limit:pageSize,snapshot:identity?.snapshot,signal}));
  if(signal?.aborted)throw Error('aborted');
  const key={snapshot:p.snapshot,checksum:p.checksum};
  if(identity&&(key.snapshot!==identity.snapshot||key.checksum!==identity.checksum||p.total!==total||p.createdAt!==createdAt))throw Error('snapshot_changed');
  if(!identity){identity=key;total=p.total;createdAt=p.createdAt;}
  if(p.results.length>pageSize||cursor+p.results.length>total)throw Error('invalid_page_size');
  if(p.nextCursor!==null&&(p.nextCursor!==cursor+p.results.length||p.results.length===0))throw Error('invalid_page_progress');
  for(const s of validateStations(p.results)){
   if(ids.has(s.id))throw Error('duplicate_station');ids.add(s.id);stations.push(s);
  }
  pages++;
  if(p.nextCursor===null){if(stations.length!==total)throw Error('incomplete_snapshot');break;}
  if(stations.length===total)throw Error('unexpected_next_cursor');
  cursor=p.nextCursor;
 }
 return {stations,metadata:{...identity,createdAt,total,pages,complete:true}};
}
async function rankSnapshot({queryPage,origin,radiusKm,fuel,vehicle,fillPercent,routeBatch,now=Date.now(),signal,pageSize,maxPages,onProgress}={}){
 const loaded=await loadSnapshotStations({queryPage,origin,radiusKm,fuel,pageSize,maxPages,signal});
 if(vehicle?.fuel!==fuel)throw Error('vehicle_fuel_mismatch');
 if(signal?.aborted)throw Error('aborted');
 const engine=makeTop10({vehicle,fillPercent,stations:loaded.stations,origin,routeBatch,signal,onProgress});
 const ranking=await engine.run();
 const freshness=evaluateFreshness({snapshotCreatedAt:loaded.metadata.createdAt,now});
 return {metadata:loaded.metadata,freshness,notice:publicStatus(freshness),ranking:{...ranking,certified:ranking.certified&&loaded.metadata.complete},calculateOne:engine.calculateOne};
}
module.exports={loadSnapshotStations,rankSnapshot};
