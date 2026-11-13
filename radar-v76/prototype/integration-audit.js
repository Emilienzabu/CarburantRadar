'use strict';
// V76: static handoff audit. A successful static audit is NOT a production-readiness decision.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {evaluateRelease}=require('./release-gate');
const REQUIRED_FILES=['radar-interface.html','radar-live.js','radar-live.browser.js','radar-ui.js','radar-ui.browser.js','radar-real-provider.js','radar-real-provider.browser.js','routing-guard.js','snapshot-france.js','source-snapshot-loader.js','garage-sync.js','release-gate.js','V75_CLAUDE_HANDOFF.md'];
const BLOCKERS=[
 {id:'immutable_source',owner:'Claude',requirement:'Atomic, versioned, immutable source verified against upstream'},
 {id:'proxy_staging',owner:'Claude',requirement:'Separate V2 endpoint preserving existing routes, countries and authentication'},
 {id:'garage_auth',owner:'Claude',requirement:'Server-side authenticated garage persistence and conflict handling'},
 {id:'real_browser',owner:'Claude',requirement:'Chromium and Android browser evidence with interactive UI'},
 {id:'real_network',owner:'Claude',requirement:'Proxy/OSRM live contract, errors and rate limits'},
 {id:'rollback',owner:'Claude',requirement:'Measured staging rollback without touching production'}
];
function audit(root=__dirname){
 const files=REQUIRED_FILES.map(name=>{
  const file=path.join(root,name);
  if(!fs.existsSync(file)||!fs.statSync(file).isFile())return {name,present:false,sha256:null};
  return {name,present:true,sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')};
 });
 const missing=files.filter(f=>!f.present).map(f=>f.name);
 const release=evaluateRelease({});
 return {schemaVersion:1,staticComplete:missing.length===0,missing,files,releaseReady:release.ready,releaseBlockers:release.blockers,stagingBlockers:BLOCKERS};
}
if(require.main===module){const result=audit(process.argv[2]||__dirname);process.stdout.write(JSON.stringify(result,null,2)+'\n');process.exitCode=result.staticComplete?0:1;}
module.exports={audit,REQUIRED_FILES,BLOCKERS};
