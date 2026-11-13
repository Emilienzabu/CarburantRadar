'use strict';
// V44: orchestration only. Production scheduler must provide a distributed lease.
function createRefresher({persistence,download,clock=()=>Date.now(),minimumStations=1,maxDropRatio=0.25,lease,logger=()=>{}}={}){
 if(!persistence||typeof persistence.stage!=='function'||typeof persistence.publish!=='function'||typeof download!=='function'||typeof clock!=='function'||!Number.isInteger(minimumStations)||minimumStations<1||!Number.isFinite(maxDropRatio)||maxDropRatio<0||maxDropRatio>=1)throw Error('invalid_refresh_config');
 let running=false,lastSuccess=null,lastError=null,attempts=0;
 async function run({version,previousCount=null,signal}={}){
  if(running)return {status:'skipped',reason:'already_running'};
  if(signal?.aborted)return {status:'skipped',reason:'aborted'};
  running=true;attempts++;
  let acquired=false;
  try{
   if(lease){if(typeof lease.acquire!=='function'||typeof lease.release!=='function')throw Error('invalid_lease');acquired=await lease.acquire();if(acquired!==true)return {status:'skipped',reason:'lease_unavailable'};}
   if(typeof version!=='string'||!/^[-\w.]{1,100}$/.test(version))throw Error('invalid_version');
   const payload=await download({signal});
   if(signal?.aborted)throw Error('aborted');
   // A source must explicitly attest completeness. Never trust array length alone.
   if(!payload||payload.complete!==true||!Array.isArray(payload.rows)||payload.rows.length<minimumStations)throw Error('incomplete_source');
   if(!Number.isInteger(payload.total)||payload.total!==payload.rows.length)throw Error('count_mismatch');
   if(previousCount!==null){if(!Number.isInteger(previousCount)||previousCount<0)throw Error('invalid_previous_count');if(previousCount>0&&payload.rows.length<previousCount*(1-maxDropRatio))throw Error('suspicious_station_drop');}
   if(signal?.aborted)throw Error('aborted');
   const manifest=await persistence.stage(payload.rows,version);
   if(signal?.aborted)throw Error('aborted');
   await persistence.publish(manifest);
   lastSuccess={version,count:manifest.count,at:clock()};lastError=null;
   logger({type:'refresh_success',version,count:manifest.count});
   return {status:'published',version,count:manifest.count};
  }catch(e){lastError={code:e?.message||'unknown_error',at:clock()};logger({type:'refresh_failed',code:lastError.code});return {status:'failed',reason:lastError.code,keptPrevious:true};}
  finally{try{if(acquired)await lease.release();}finally{running=false;}}
 }
 function status(){return {running,attempts,lastSuccess:lastSuccess&&{...lastSuccess},lastError:lastError&&{...lastError}};}
 return {run,status};
}
module.exports={createRefresher};
