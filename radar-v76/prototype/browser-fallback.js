'use strict';
// Explicitly a simulated DOM/VM check, NOT Chromium or Android validation.
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const ROOT=__dirname;
const SCRIPTS=['radar-ui.browser.js','radar-live.browser.js','radar-real-provider.browser.js'];
function runFallback({root=ROOT}={}){
 const html=fs.readFileSync(path.join(root,'browser-smoke.html'),'utf8');
 const result={textContent:'PENDING'};
 const document={getElementById(id){if(id!=='result')throw Error('Unexpected element '+id);return result}};
 const globals={document,console,AbortController,URL,URLSearchParams,setTimeout,clearTimeout};globals.window=globals;const context=vm.createContext(globals);
 try{
  for(const filename of SCRIPTS){vm.runInContext(fs.readFileSync(path.join(root,filename),'utf8'),context,{filename,timeout:2000});}
  const inline=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)].map(x=>x[1]).filter(x=>x.trim());
  if(inline.length!==1)throw Error('Expected exactly one smoke script');
  vm.runInContext(inline[0],context,{filename:'browser-smoke-inline.js',timeout:2000});
  return {passed:result.textContent==='PASS',status:result.textContent==='PASS'?'simulated_pass':'simulated_fail',result:result.textContent,environment:'node_vm_simulated_dom',browserValidated:false};
 }catch(error){return {passed:false,status:'simulated_error',error:error.message,environment:'node_vm_simulated_dom',browserValidated:false};}
}
if(require.main===module){const result=runFallback();console.log(JSON.stringify(result,null,2));if(!result.passed)process.exitCode=1}
module.exports={runFallback};
