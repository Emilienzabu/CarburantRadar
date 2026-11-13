'use strict';
// V74: download a complete, consistently ordered source before publishing a snapshot.
// Count stability is necessary but NOT sufficient to prove an atomic upstream snapshot.
const crypto=require('node:crypto');
function hash(rows){return crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex');}
async function loadSourceSnapshot({fetchPage,pageSize=100,maxPages=150,maxRecords=15000,signal,verifySecondPass=true}={}){
 if(typeof fetchPage!=='function'||!Number.isInteger(pageSize)||pageSize<1||pageSize>100||!Number.isInteger(maxPages)||maxPages<1||!Number.isInteger(maxRecords)||maxRecords<1)throw Error('invalid_source_config');
 async function pass(){
  let total=null;const rows=[],ids=new Set();
  for(let page=0;page<maxPages;page++){
   if(signal?.aborted)throw Error('aborted');
   const offset=page*pageSize;
   const response=await fetchPage({offset,limit:pageSize,signal});
   if(signal?.aborted)throw Error('aborted');
   if(!response||!Array.isArray(response.results)||!Number.isInteger(response.total_count)||response.total_count<0||response.results.length>pageSize)throw Error('invalid_source_page');
   if(total===null){total=response.total_count;if(total>maxRecords)throw Error('source_limit');}
   if(response.total_count!==total)throw Error('source_total_changed');
   if(offset+response.results.length>total)throw Error('source_overflow');
   if(response.results.length!==Math.min(pageSize,total-offset))throw Error('source_short_page');
   for(const item of response.results){
    if(!item||item.id===undefined||item.id===null||!String(item.id))throw Error('source_missing_id');
    const id=String(item.id);if(ids.has(id))throw Error('source_duplicate_id');ids.add(id);rows.push(item);
   }
   if(rows.length===total)return {rows,total,checksum:hash(rows),pages:page+1};
  }
  throw Error('source_page_limit');
 }
 const first=await pass();
 if(verifySecondPass){const second=await pass();if(first.total!==second.total||first.checksum!==second.checksum)throw Error('source_changed_between_passes');}
 return {rows:first.rows,total:first.total,complete:true,checksum:first.checksum,pages:first.pages,verifiedTwice:verifySecondPass};
}
module.exports={loadSourceSnapshot};
