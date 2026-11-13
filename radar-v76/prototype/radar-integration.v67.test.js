'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {createPreviewServer}=require('./preview-server');
const html=fs.readFileSync(__dirname+'/radar-interface.html','utf8');
test('demo and real callbacks both reject late updates from previous mode',()=>{
 const matches=html.match(/onUpdate:s=>\{if\(generation===modeGeneration\)setData\(/g)||[];
 assert.equal(matches.length,2);
});
test('demo switch restores real button after previous pending geolocation',()=>{
 assert.match(html,/generation=\+\+modeGeneration;clearPendingFill\(\);\$\('real'\)\.disabled=false/);
});
test('obsolete real-mode finally cannot alter current mode button',()=>{
 assert.match(html,/finally\{if\(generation===modeGeneration\)\$\('real'\)\.disabled=false/);
});
test('preview serves disabled real-mode button with explicit explanation',async()=>{
 const server=createPreviewServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{const response=await fetch('http://127.0.0.1:'+server.address().port+'/');const page=await response.text();assert.match(page,/id="real" type="button" disabled/);assert.match(page,/Prévisualisation isolée : données réelles désactivées/);assert.match(response.headers.get('content-security-policy'),/connect-src 'none'/)}finally{await new Promise(r=>server.close(r))}
});
