'use strict';
// V51: read-only bridge to the currently deployed legacy proxy; no exhaustiveness claim.
const {createLegacyProxyFetch}=require('./proxy-adapter');
const {resolveRoutes,createRouteCache}=require('./routing');
function createRealProviders({fetchFn,proxyUrl,radiusKm=10,osrmBase,cacheTtlMs=300000}={}){
 if(typeof fetchFn!=='function')throw new TypeError('fetchFn requis');
 if(![5,10,20,50].includes(radiusKm))throw new RangeError('Rayon invalide');
 const fetchLegacy=createLegacyProxyFetch({fetchFn,baseUrl:proxyUrl});
 const routeCache=createRouteCache();
 let stationCache=null;
 async function loadStations({fuel,origin,signal,reloadStations=true}){
  const key=[fuel,origin.lat,origin.lon,radiusKm].join(':');
  if(!reloadStations&&stationCache?.key===key)return {...stationCache.data,stations:stationCache.data.stations.slice()};
  const data=await fetchLegacy({origin,radiusKm,fuel,signal,limit:100});
  if(signal?.aborted)throw new Error('Recherche annulée');
  // Legacy proxy never provides a verifiable complete result set.
  const result={stations:data.stations.map(s=>({...s,name:[s.address,s.city].filter(Boolean).join(' — ')||'Station '+s.id})),complete:false,source:'legacy_proxy',reason:data.reason};
  stationCache={key,data:result};return {...result,stations:result.stations.slice()};
 }
 async function routeBatch({origin,stations,signal}){
  const routes=await resolveRoutes({origin,stations,signal,fetchFn,cache:routeCache,base:osrmBase});
  return routes.filter(r=>r.status==='routed').map(r=>({id:r.id,distanceRoundTripKm:r.distanceRoundTripKm,durationOutboundMinutes:r.durationOutboundMinutes,durationReturnMinutes:r.durationReturnMinutes}));
 }
 return {loadStations,routeBatch,clearStationCache(){stationCache=null}};
}
module.exports={createRealProviders};
