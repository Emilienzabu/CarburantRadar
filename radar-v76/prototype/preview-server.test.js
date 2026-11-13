'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {createPreviewServer}=require('./preview-server');
async function withServer(fn){const s=createPreviewServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));try{await fn('http://127.0.0.1:'+s.address().port)}finally{await new Promise(r=>s.close(r))}}
test('real HTTP loopback serves the browser smoke page',async()=>withServer(async base=>{const r=await fetch(base+'/browser-smoke.html');assert.equal(r.status,200);assert.match(await r.text(),/id="result"/);assert.match(r.headers.get('content-type'),/text\/html/)}));
test('all three browser bundles are served with JS content type',async()=>withServer(async base=>{for(const name of ['radar-ui','radar-live','radar-real-provider']){const r=await fetch(base+'/'+name+'.browser.js');assert.equal(r.status,200);assert.match(r.headers.get('content-type'),/javascript/);assert.ok((await r.text()).length>500)}}));
test('preview blocks other files and unsupported methods',async()=>withServer(async base=>{for(const p of ['/garage.js','/../INTEGRATION.md','/package.json'])assert.equal((await fetch(base+p)).status,404);assert.equal((await fetch(base+'/',{method:'POST'})).status,404)}));
test('preview disables external network requests via CSP',async()=>withServer(async base=>{const r=await fetch(base+'/');const csp=r.headers.get('content-security-policy');assert.match(csp,/connect-src 'none'/);assert.match(csp,/default-src 'none'/);assert.equal(r.headers.get('cache-control'),'no-store')}));
