'use strict';
// V47 local routing guard. Prototype: concurrency and cache are per process, not distributed.
const {resolveRoutes,createRouteCache,coord}=require('./routing');
function createRoutingGuard({fetchFn,clock=()=>Date.now(),maxConcurrent=2,minIntervalMs=0,timeoutMs=8000,cacheLimit=1000,ttlMs=900000,failureThreshold=3,cooldownMs=30000,base}={}){
 if(typeof fetchFn!=='function'||typeof clock!=='function')throw new TypeError('fetchFn/clock invalid');
 for(const [name,value,min,max] of [['maxConcurrent',maxConcurrent,1,20],['minIntervalMs',minIntervalMs,0,60000],['timeoutMs',timeoutMs,1,120000],['cacheLimit',cacheLimit,1,100000],['ttlMs',ttlMs,0,86400000],['failureThreshold',failureThreshold,1,100],['cooldownMs',cooldownMs,0,3600000]])if(!Number.isInteger(value)||value<min||value>max)throw new RangeError(name);
 const cache=createRouteCache();let active=0,failures=0,openUntil=0,lastStart=-Infinity,rateLimitedUntil=0;const queue=[];
 const unavailable=stations=>stations.map(s=>({id:String(s.id),status:'route_unavailable',distanceRoundTripKm:null,durationOutboundMinutes:null,durationReturnMinutes:null,fromCache:false}));
 function drain(){while(active<maxConcurrent&&queue.length){const job=queue.shift();if(job.signal?.aborted){job.reject(new Error('aborted'));continue;}active++;Promise.resolve().then(job.run).then(job.resolve,job.reject).finally(()=>{active--;drain();});}}
 function schedule(run,signal){return new Promise((resolve,reject)=>{queue.push({run,signal,resolve,reject});drain();});}
 async function routeBatch({origin,stations,signal}={}){
  if(!Array.isArray(stations)||!stations.length)return [];
  if(signal?.aborted)throw new Error('aborted');
  // Validate even during an outage: malformed requests must never masquerade as route failures.
  coord(origin);
  const seen=new Set();
  for(const station of stations){
   if(!station || !['string','number'].includes(typeof station.id) || String(station.id)==='')throw new TypeError('Identifiant station invalide');
   coord(station);
   const id=String(station.id);
   if(seen.has(id))throw new Error('Identifiant station dupliqué');
   seen.add(id);
  }
  return schedule(async()=>{
   if(signal?.aborted)throw new Error('aborted');
   if(clock()<Math.max(openUntil,rateLimitedUntil)){
    // A circuit outage must not hide still-valid cached routes.
    coord(origin);
    return stations.map(station=>{
     coord(station);
     const id=String(station.id),key=`${coord(origin)}|${id}|${coord(station)}`;
     const hit=cache.get(key);
     return hit&&clock()<hit.expiresAt?{id,status:'routed',distanceRoundTripKm:hit.distanceRoundTripKm,durationOutboundMinutes:hit.durationOutboundMinutes??null,durationReturnMinutes:hit.durationReturnMinutes??null,fromCache:true}:unavailable([station])[0];
    });
   }
   // Pacing applies to starts, not a claim of a distributed rate limit.
   const wait=Math.max(0,lastStart+minIntervalMs-clock());
   if(wait)await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},wait);function abort(){clearTimeout(timer);reject(new Error('aborted'));}signal?.addEventListener('abort',abort,{once:true});});
   if(signal?.aborted)throw new Error('aborted');
   lastStart=clock();let networkFailed=false;
   const controller=new AbortController();
   const abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});
   const timer=setTimeout(()=>controller.abort(),timeoutMs);
   try{
    const guardedFetch=async(url,opts)=>{
     // A 429 may arrive in the middle of a multi-batch lookup. Stop further requests.
     if(clock()<rateLimitedUntil)throw new Error('OSRM rate limited');
     try{const r=await fetchFn(url,{...opts,signal:controller.signal});if(!r?.ok){
      networkFailed=true;
      if(r?.status===429||r?.status===503){
       // Retry-After can be seconds or an HTTP date. Clamp to avoid indefinite lockout.
       const raw=r.headers?.get?.('retry-after');
       let delay=cooldownMs;
       if(raw!=null){
        const seconds=Number(raw);
        if(Number.isFinite(seconds)&&seconds>=0)delay=seconds*1000;
        else {const date=Date.parse(raw);if(Number.isFinite(date))delay=Math.max(0,date-clock());}
       }
       rateLimitedUntil=Math.max(rateLimitedUntil,clock()+Math.min(3600000,Math.max(cooldownMs,delay)));
      }
     }
     return r;}
     catch(e){networkFailed=true;throw e;}
    };
    const results=await resolveRoutes({origin,stations,fetchFn:guardedFetch,cache,ttlMs,now:clock,signal:controller.signal,...(base?{base}:{})});
    if(signal?.aborted)throw new Error('aborted');
    if(networkFailed||controller.signal.aborted){
     failures++;if(failures>=failureThreshold)openUntil=clock()+cooldownMs;
     // Keep valid completed routes (including cache hits) when another batch fails.
     // resolveRoutes marks failed routes unavailable without inventing distances.
     while(cache.size>cacheLimit)cache.delete(cache.keys().next().value);
     return results;
    }
    failures=0;
    // Map insertion order bounds process memory, keeping newest entries.
    while(cache.size>cacheLimit)cache.delete(cache.keys().next().value);
    return results;
   }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
  },signal);
 }
 return {routeBatch,status:()=>({active,queued:queue.length,cached:cache.size,failures,circuitOpen:clock()<Math.max(openUntil,rateLimitedUntil),rateLimited:clock()<rateLimitedUntil,retryAfterMs:Math.max(0,Math.max(openUntil,rateLimitedUntil)-clock())}),clearCache:()=>cache.clear()};
}
module.exports={createRoutingGuard};
