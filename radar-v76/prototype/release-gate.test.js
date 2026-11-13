'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const {REQUIRED,evaluateRelease}=require('./release-gate');
test('missing evidence blocks all critical gates',()=>{const r=evaluateRelease({});assert.equal(r.ready,false);assert.deepEqual(r.blockers,REQUIRED);});
test('simulated validation never qualifies as real',()=>{const r=evaluateRelease({browserReal:{status:'passed',reference:'node-vm-test',environment:'simulated'}});assert(r.blockers.includes('browserReal'));});
test('passed without traceable evidence is blocked',()=>{const r=evaluateRelease({routingReal:{status:'passed',reference:'',environment:'real'}});assert(r.blockers.includes('routingReal'));});
test('one failed critical gate prevents readiness',()=>{const all=Object.fromEntries(REQUIRED.map(id=>[id,{status:'passed',reference:'report-123',environment:'real'}]));all.rollback.status='failed';const r=evaluateRelease(all);assert.deepEqual(r.blockers,['rollback']);});
test('complete real traceable evidence allows controlled staging only',()=>{const all=Object.fromEntries(REQUIRED.map(id=>[id,{status:'passed',reference:'report-123',environment:'real'}]));const r=evaluateRelease(all);assert.equal(r.ready,true);assert.equal(r.stage,'ready_for_controlled_staging');});
test('invalid evidence rejected',()=>{assert.throws(()=>evaluateRelease(null),/invalid_evidence/);assert.throws(()=>evaluateRelease([]),/invalid_evidence/);});
