'use strict';
// Transport-agnostic station pagination. A page adapter MUST return explicit completion evidence.
const finite = n => typeof n === 'number' && Number.isFinite(n);
function validateOrigin(origin){if(!origin||!finite(origin.lat)||!finite(origin.lon)||Math.abs(origin.lat)>90||Math.abs(origin.lon)>180)throw new TypeError('Origine invalide');}
function normalizeStation(s){
  if(!s||typeof s!=='object'||!['string','number'].includes(typeof s.id)||!String(s.id).trim())throw new TypeError('Identifiant de station invalide');
  if(!finite(s.lat)||!finite(s.lon)||Math.abs(s.lat)>90||Math.abs(s.lon)>180)throw new TypeError('Coordonnées de station invalides');
  return {...s,id:String(s.id)};
}
function normalizePage(page){
  if(!page||!Array.isArray(page.stations)||typeof page.complete!=='boolean')throw new TypeError('Page sans preuve de complétude');
  if(page.nextCursor!==null&&page.nextCursor!==undefined&&typeof page.nextCursor!=='string'&&typeof page.nextCursor!=='number')throw new TypeError('Curseur invalide');
  if(page.complete&&page.nextCursor!==null&&page.nextCursor!==undefined)throw new TypeError('Page complète avec curseur suivant');
  if(!page.complete&&(page.nextCursor===null||page.nextCursor===undefined||String(page.nextCursor)===''))throw new TypeError('Pagination incomplète sans curseur');
  if(page.total!==undefined&&(!Number.isInteger(page.total)||page.total<0))throw new TypeError('Total invalide');
  return page;
}
async function loadAllStations({fetchPage,origin,radiusKm,signal,maxPages=100,maxStations=30000,onProgress=()=>{}}={}){
  if(typeof fetchPage!=='function'||typeof onProgress!=='function')throw new TypeError('Callback invalide');
  validateOrigin(origin);
  if(!finite(radiusKm)||radiusKm<=0||radiusKm>100)throw new RangeError('Rayon invalide');
  if(!Number.isInteger(maxPages)||maxPages<1||!Number.isInteger(maxStations)||maxStations<1)throw new RangeError('Limites invalides');
  const stations=new Map(),cursors=new Set();let cursor=null,pages=0,expectedTotal=null;
  const result=(status,reason)=>({status,reason:reason||null,stations:[...stations.values()],pages,received:stations.size,expectedTotal,complete:status==='complete'});
  while(pages<maxPages){
    if(signal?.aborted)return result('cancelled','aborted');
    let page;
    try{page=normalizePage(await fetchPage({origin,radiusKm,cursor,signal}));}
    catch(e){return result('incomplete',e instanceof Error?e.message:'page_error');}
    if(signal?.aborted)return result('cancelled','aborted');
    pages++;
    if(page.total!==undefined){if(expectedTotal!==null&&expectedTotal!==page.total)return result('incomplete','total_changed');expectedTotal=page.total;}
    try{
      for(const raw of page.stations){const s=normalizeStation(raw);const old=stations.get(s.id);if(old){if(old.lat!==s.lat||old.lon!==s.lon)throw new Error('duplicate_id_conflict');}else stations.set(s.id,s);}
    }catch(e){return result('incomplete',e.message);}
    if(stations.size>maxStations)return result('incomplete','station_limit');
    onProgress(result('loading'));
    if(page.complete){if(expectedTotal!==null&&stations.size!==expectedTotal)return result('incomplete','total_mismatch');return result('complete');}
    const next=String(page.nextCursor);
    if(cursors.has(next))return result('incomplete','cursor_loop');
    cursors.add(next);cursor=next;
  }
  return result('incomplete','page_limit');
}
module.exports={loadAllStations,normalizePage,normalizeStation};
