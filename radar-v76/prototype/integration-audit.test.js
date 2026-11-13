'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
const {audit,REQUIRED_FILES}=require('./integration-audit');
test('audit V76: all handoff files exist',()=>{const a=audit();assert.equal(a.staticComplete,true);assert.equal(a.missing.length,0);assert.equal(a.files.length,REQUIRED_FILES.length);});
test('audit V76: SHA256 stable and valid',()=>{const a=audit();for(const f of a.files)assert.match(f.sha256,/^[a-f0-9]{64}$/);assert.deepEqual(a.files,audit().files);});
test('audit V76: missing file blocks static readiness',()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'radar-audit-'));try{const a=audit(dir);assert.equal(a.staticComplete,false);assert.equal(a.missing.length,REQUIRED_FILES.length);}finally{fs.rmSync(dir,{recursive:true,force:true});}});
test('audit V76: static success never means release ready',()=>{const a=audit();assert.equal(a.releaseReady,false);assert.ok(a.releaseBlockers.includes('androidReal'));assert.ok(a.stagingBlockers.some(b=>b.id==='immutable_source'));});
