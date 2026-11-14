const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const html=fs.readFileSync(__dirname+'/index.html','utf8');
const body=html.match(/async function chargerStationsRadar\([\s\S]*?\n}\n(?=\S)/)?.[0];assert.ok(body,'chargerStationsRadar introuvable dans index.html');
const fn=body;
async function run(pages,url='https://staging.example/v2/france'){
 let calls=[];const ctx={URL,Set,PK:{Gazole:'gazole_prix'},PROXY:'https://proxy.example',SNAPSHOT_V2_URL:url,fetch:async u=>{calls.push(u);return {ok:true,json:async()=>pages.shift()};}};
 vm.runInNewContext(fn+'\nthis.execute=chargerStationsRadar',ctx);
 return {value:await ctx.execute(43,5,20,'Gazole'),calls};
}
const page=(rows,next,total=rows.length)=>({schemaVersion:2,complete:true,snapshot:'v1',checksum:'abc',total,results:rows,nextCursor:next});
test('V2 pages pinned, stations converted, unknown hours not marked open 24/7',async()=>{
 const {value,calls}=await run([page([{id:'a',lat:43,lon:5,price:1.5}],1,2),page([{id:'b',lat:43.1,lon:5.1,price:1.6}],null,2)]);
 assert.equal(value.results.length,2);assert.equal(value.results[0].gazole_prix,1.5);assert.equal(value.results[0]._v2HorairesInconnus,true);assert.equal(value.results[0].horaires_automate_24_24,null);
 assert.equal(new URL(calls[1]).searchParams.get('snapshot'),'v1');
});
test('V2 rejects incomplete count',async()=>{await assert.rejects(run([page([],null,1)]),/v2_total_incomplet/)});
test('V2 rejects duplicate station IDs',async()=>{await assert.rejects(run([page([{id:1},{id:1}],null,2)]),/v2_doublon/)});
test('V2 rejects non HTTPS endpoints',async()=>{await assert.rejects(run([], 'http://test.example/v2/france'),/v2_url_invalide/)});
test('V2 rejects inconsistent cursors',async()=>{await assert.rejects(run([page([{id:1}],3,2)]),/v2_curseur_invalide/)});
