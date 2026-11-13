'use strict';
// V45: observational freshness metadata, never an automatic price-validity verdict.
const DAY=86400000;
function parseDate(value){
 if(typeof value!=='string'||!/^\d{4}-\d\d-\d\d(?:T|$)/.test(value))return null;
 const n=Date.parse(value);return Number.isFinite(n)?n:null;
}
function evaluateFreshness({snapshotCreatedAt,priceUpdatedAt,now=Date.now(),snapshotWarningAfterMs=24*60*60*1000,priceInfoAfterMs=7*DAY}={}){
 if(!Number.isFinite(now)||!Number.isFinite(snapshotWarningAfterMs)||snapshotWarningAfterMs<0||!Number.isFinite(priceInfoAfterMs)||priceInfoAfterMs<0)throw Error('invalid_freshness_config');
 const snapshotTime=parseDate(snapshotCreatedAt);
 const priceTime=parseDate(priceUpdatedAt);
 const age=t=>t===null?null:Math.max(0,now-t);
 const snapshotAgeMs=age(snapshotTime),priceAgeMs=age(priceTime);
 return Object.freeze({
  snapshot:{known:snapshotTime!==null,ageMs:snapshotAgeMs,status:snapshotTime===null?'unknown':snapshotTime>now+300000?'future_timestamp':snapshotAgeMs>snapshotWarningAfterMs?'update_delayed':'recent'},
  price:{known:priceTime!==null,ageMs:priceAgeMs,status:priceTime===null?'unknown':priceTime>now+300000?'future_timestamp':priceAgeMs>priceInfoAfterMs?'unchanged_for_a_while':'recent_change'},
  // Never infer incorrectness from the date of last price change.
  priceValidity:'not_determined_by_age',
  hideStation:false
 });
}
function publicStatus(meta){
 if(!meta||!meta.snapshot||!meta.price)throw Error('invalid_freshness_metadata');
 const delayed=meta.snapshot.status==='update_delayed';
 return Object.freeze({
  headline:delayed?'Actualisation des données retardée':'',
  details:meta.price.status==='unchanged_for_a_while'?'Ce prix n’a pas été modifié récemment. Cela ne signifie pas qu’il est incorrect.':meta.price.status==='unknown'?'Date du dernier changement de prix inconnue.':'',
  showNotice:delayed,
  infoOnly:!delayed && !!(meta.price.status==='unchanged_for_a_while'||meta.price.status==='unknown')
 });
}
function healthForRefresh({lastSuccessAt,lastErrorAt,now=Date.now(),warnAfterMs=24*60*60*1000}={}){
 if(!Number.isFinite(now)||!Number.isFinite(warnAfterMs)||warnAfterMs<0)throw Error('invalid_health_config');
 const success=Number.isFinite(lastSuccessAt)?lastSuccessAt:null;
 const error=Number.isFinite(lastErrorAt)?lastErrorAt:null;
 const delayed=success===null||now-success>warnAfterMs;
 return Object.freeze({status:delayed?'needs_attention':error!==null&&error>success?'retry_needed':'ok',lastSuccessAt:success,lastErrorAt:error,serveLastValidSnapshot:true});
}
module.exports={evaluateFreshness,publicStatus,healthForRefresh,parseDate};
