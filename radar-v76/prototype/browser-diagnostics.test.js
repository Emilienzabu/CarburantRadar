'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const {runProbe,diagnose}=require('./browser-diagnostics');
test('missing binary is classified as unavailable at startup',async()=>{
 const result=await runProbe({binary:'__missing_carburant_browser__',timeoutMs:300});
 assert.equal(result.status,'unavailable');assert.equal(result.passed,false);
});
test('startup failure never triggers app probe',async()=>{
 const result=await diagnose({binary:'__missing_carburant_browser__',timeoutMs:300});
 assert.equal(result.stage,'chromium_startup');assert.equal(result.app,null);assert.equal(result.passed,false);
});
test('a process exiting successfully without DOM marker is not a pass',async()=>{
 const result=await runProbe({binary:process.execPath,timeoutMs:1000});
 assert.equal(result.passed,false);
});
