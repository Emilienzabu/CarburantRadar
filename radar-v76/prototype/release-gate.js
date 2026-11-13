'use strict';
// Conservative release readiness gate: evidence is required for every critical dependency.
const REQUIRED=['immutableSource','completeStationCoverage','snapshotPublication','proxyCompatibility','routingReal','browserReal','androidReal','garageAccountSync','performance','rollback'];
function evaluateRelease(evidence){
 if(!evidence||typeof evidence!=='object'||Array.isArray(evidence))throw Error('invalid_evidence');
 const checks=REQUIRED.map(id=>{
  const e=evidence[id];
  const passed=Boolean(e&&e.status==='passed'&&typeof e.reference==='string'&&e.reference.trim().length>=3&&e.environment==='real');
  return {id,status:passed?'passed':'blocked',reason:passed?null:(!e?'missing_evidence':e.environment!=='real'?'not_real_validation':e.status!=='passed'?'not_passed':'missing_reference')};
 });
 const blockers=checks.filter(c=>c.status==='blocked');
 return {ready:blockers.length===0,stage:blockers.length?'integration_not_ready':'ready_for_controlled_staging',checks,blockers:blockers.map(x=>x.id)};
}
module.exports={REQUIRED,evaluateRelease};
