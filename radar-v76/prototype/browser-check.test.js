'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const {checkBrowser}=require('./browser-check');
test('missing browser executable is reported, never a false success',async()=>{
 const result=await checkBrowser({binary:'__carburant_missing_browser_binary__',timeoutMs:500});
 assert.equal(result.passed,false);assert.equal(result.status,'unavailable');
});
