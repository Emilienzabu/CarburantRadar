'use strict';
// Direct client for the actual PR #39 /v2/france contract (not the legacy proxy v=2 contract).
const {loadAllStations}=require('./station-pages');
const FUELS=new Set(['Gazole','SP95','SP98','E10','E85','GPLc']);
const SHA=/^[0-9a-f]{64}$/i;
function normalizeSnapshotPage(raw, fuel, requestedOffset, requestedLimit){
  if(!FUELS.has(fuel))throw new RangeError('invalid_fuel');
  if(!raw||raw.schemaVersion!==2||raw.complete!==true||!Array.isArray(raw.results)||
     typeof raw.snapshot!=='string'||!raw.snapshot||!SHA.test(raw.checksum)||
     !Number.isInteger(raw.total)||raw.total<0||!Number.isInteger(requestedOffset)||requestedOffset<0||
     !Number.isInteger(requestedLimit)||requestedLimit<1)throw new TypeError('invalid_snapshot_contract');
  const end=requestedOffset+raw.results.length;
  if(raw.results.length>requestedLimit||end>raw.total)throw new TypeError('invalid_page_size');
  const expectedCursor=end<raw.total?end:null;
  if(raw.nextCursor!==expectedCursor)throw new TypeError('invalid_snapshot_cursor');
  const stations=raw.results.map(s=>{
    if(!s||typeof s.id!=='string'||!s.id||!Number.isFinite(s.lat)||!Number.isFinite(s.lon)||
       Math.abs(s.lat)>90||Math.abs(s.lon)>180||!Number.isFinite(s.price)||s.price<=0)
      throw new TypeError('invalid_snapshot_station');
    return {id:s.id,lat:s.lat,lon:s.lon,price:s.price,updatedAt:s.updatedAt??null,
      address:s.address||'',city:s.city||'',postalCode:s.postalCode||'',distanceIndicativeKm:s.distanceIndicativeKm};
  });
  return {stations,complete:expectedCursor===null,nextCursor:expectedCursor,total:raw.total,
    snapshot:raw.snapshot,checksum:raw.checksum,createdAt:raw.createdAt,stale:raw.stale};
}
function createSnapshotV2PageFetcher({fetchFn,baseUrl,fuel,limit=100}={}){
  if(typeof fetchFn!=='function')throw new TypeError('fetchFn_required');
  if(!FUELS.has(fuel))throw new RangeError('invalid_fuel');
  if(!Number.isInteger(limit)||limit<1||limit>100)throw new RangeError('invalid_limit');
  const base=new URL(baseUrl||'https://example.invalid/v2/france');
  if(base.pathname!=='/v2/france')throw new TypeError('snapshot_endpoint_required');
  let pinned=null,checksum=null,createdAt=null,total=null;
  return async ({origin,radiusKm,cursor,signal})=>{
    const offset=cursor==null?0:Number(cursor);
    if(!Number.isSafeInteger(offset)||offset<0)throw new TypeError('invalid_offset');
    const url=new URL(base);
    url.searchParams.set('lat',String(origin.lat));url.searchParams.set('lon',String(origin.lon));
    url.searchParams.set('dist',String(radiusKm));url.searchParams.set('fuel',fuel);
    url.searchParams.set('cursor',String(offset));url.searchParams.set('limit',String(limit));
    if(pinned)url.searchParams.set('snapshot',pinned);
    const res=await fetchFn(url.toString(),{signal});
    if(!res?.ok)throw new Error('snapshot_http_'+(res?.status??'unknown'));
    const page=normalizeSnapshotPage(await res.json(),fuel,offset,limit);
    if(pinned!==null&&(page.snapshot!==pinned||page.checksum!==checksum||page.createdAt!==createdAt||page.total!==total))
      throw new Error('snapshot_changed');
    pinned=page.snapshot;checksum=page.checksum;createdAt=page.createdAt;total=page.total;
    return page;
  };
}
async function loadSnapshotV2({fetchFn,baseUrl,fuel,limit=100,origin,radiusKm,signal,maxPages=300,onProgress}={}){
  const fetchPage=createSnapshotV2PageFetcher({fetchFn,baseUrl,fuel,limit});
  return loadAllStations({fetchPage,origin,radiusKm,signal,maxPages,onProgress});
}
module.exports={normalizeSnapshotPage,createSnapshotV2PageFetcher,loadSnapshotV2};

// Adapter for the existing Top-10 bridge; preserves the raw Worker contract and pins identity.
function createSnapshotV2QueryPage({fetchFn,baseUrl}={}){
  if(typeof fetchFn!=='function')throw new TypeError('fetchFn_required');
  const base=new URL(baseUrl||'https://example.invalid/v2/france');
  if(base.pathname!=='/v2/france')throw new TypeError('snapshot_endpoint_required');
  return async ({lat,lon,radiusKm,fuel,offset=0,limit=100,snapshot,signal})=>{
    if(!FUELS.has(fuel)||!Number.isSafeInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)throw new TypeError('invalid_query');
    const url=new URL(base);
    for(const [k,v] of Object.entries({lat,lon,dist:radiusKm,fuel,cursor:offset,limit}))url.searchParams.set(k,String(v));
    if(snapshot)url.searchParams.set('snapshot',snapshot);
    const res=await fetchFn(url.toString(),{signal});
    if(!res?.ok)throw new Error('snapshot_http_'+(res?.status??'unknown'));
    const raw=await res.json();
    normalizeSnapshotPage(raw,fuel,offset,limit);
    return raw;
  };
}
module.exports.createSnapshotV2QueryPage=createSnapshotV2QueryPage;
