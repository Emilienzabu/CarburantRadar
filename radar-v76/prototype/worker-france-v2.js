'use strict';
// Standalone endpoint handler. Explicit opt-in: mount ONLY at /v2/france.
const DATASET='https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/records';
const FIELDS={Gazole:'gazole_prix',SP95:'sp95_prix',SP98:'sp98_prix',E10:'e10_prix',E85:'e85_prix',GPLc:'gplc_prix'};
function finite(n){return typeof n==='number'&&Number.isFinite(n);}
function parseRequest(url){
 const u=new URL(url),lat=Number(u.searchParams.get('lat')),lon=Number(u.searchParams.get('lon')),radiusKm=Number(u.searchParams.get('dist')),fuel=u.searchParams.get('fuel');
 if(!u.searchParams.has('lat')||!u.searchParams.has('lon')||!u.searchParams.has('dist')||!finite(lat)||!finite(lon)||Math.abs(lat)>90||Math.abs(lon)>180||!finite(radiusKm)||radiusKm<=0||radiusKm>50||!FIELDS[fuel])throw new RangeError('invalid_parameters');
 return {lat,lon,radiusKm,fuel};
}
function buildUpstream({lat,lon,radiusKm},offset,limit=100){
 const u=new URL(DATASET);
 u.searchParams.set('where',`within_distance(geom,geom'POINT(${lon} ${lat})',${Math.round(radiusKm*1000)}m)`);
 u.searchParams.set('limit',String(limit));u.searchParams.set('offset',String(offset));
 u.searchParams.set('order_by','id ASC');return u.toString();
}
function json(body,status=200){return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','Access-Control-Allow-Origin':'*'}});}
async function handleFranceV2(request,{fetchFn=fetch,maxRecords=9500,maxPages=95,pageSize=100,signal=request.signal}={}){
 let params;try{params=parseRequest(request.url);}catch(e){return json({error:'invalid_parameters'},400);}
 if(!Number.isInteger(pageSize)||pageSize<1||pageSize>100||!Number.isInteger(maxPages)||maxPages<1||!Number.isInteger(maxRecords)||maxRecords<1)return json({error:'invalid_configuration'},500);
 const all=[];let expectedTotal=null;
 try{
  for(let page=0;page<maxPages;page++){
   if(signal?.aborted)throw Error('aborted');
   const offset=page*pageSize;
   const response=await fetchFn(buildUpstream(params,offset,pageSize),{signal,headers:{Accept:'application/json'}});
   if(!response?.ok)throw Error('upstream_http');
   const raw=await response.json();
   if(!raw||!Array.isArray(raw.results)||!Number.isInteger(raw.total_count)||raw.total_count<0||raw.results.length>pageSize)throw Error('invalid_upstream_page');
   if(expectedTotal===null)expectedTotal=raw.total_count;
   if(raw.total_count!==expectedTotal)throw Error('upstream_changed');
   if(expectedTotal>maxRecords)throw Error('result_limit');
   if(raw.results.length===0&&all.length<expectedTotal)throw Error('upstream_short_page');
   all.push(...raw.results);
   if(all.length>expectedTotal)throw Error('upstream_overflow');
   if(all.length===expectedTotal){
    const ids=new Set();for(const row of all){if(row.id===undefined||row.id===null||ids.has(String(row.id)))throw Error('duplicate_or_missing_id');ids.add(String(row.id));}
    // Only retain stations with a usable price for the requested fuel.
    const filtered=all.filter(row=>{const n=Number(row[FIELDS[params.fuel]]);return row[FIELDS[params.fuel]]!==null&&row[FIELDS[params.fuel]]!==undefined&&row[FIELDS[params.fuel]]!==''&&Number.isFinite(n)&&n>0;});
    return json({schemaVersion:2,results:filtered,complete:true,nextCursor:null,total:filtered.length,snapshot:`single-response-${all.length}`,sourceTotal:expectedTotal});
   }
  }
  throw Error('page_limit');
 }catch(e){return json({error:'incomplete_upstream',reason:e.message},503);}
}
module.exports={parseRequest,buildUpstream,handleFranceV2};
