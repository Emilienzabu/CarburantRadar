'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const {runFallback}=require('./browser-fallback');
test('browser bundles execute smoke script in isolated simulated DOM',()=>{const r=runFallback();assert.equal(r.passed,true,JSON.stringify(r));assert.equal(r.browserValidated,false)});
test('fallback never claims browser validation',()=>{const r=runFallback();assert.equal(r.environment,'node_vm_simulated_dom');assert.notEqual(r.status,'browser_pass')});
