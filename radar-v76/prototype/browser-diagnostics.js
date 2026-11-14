'use strict';
// Separate browser startup from application loading. Read-only local diagnostics.
const {spawn}=require('node:child_process');
const {checkBrowser}=require('./browser-check');
function runProbe({binary=process.env.CHROMIUM_BIN||'chromium',timeoutMs=5000,url='data:text/html,%3Coutput%20id%3D%22result%22%3EPASS%3C%2Foutput%3E'}={}){
 return new Promise(resolve=>{
  const args=['--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--disable-extensions','--no-first-run','--dump-dom',url];
  let child,done=false,stdout='',stderr='';
  const finish=result=>{if(done)return;done=true;clearTimeout(timer);resolve(result)};
  try{child=spawn(binary,args,{stdio:['ignore','pipe','pipe']})}catch(error){resolve({status:'unavailable',passed:false,error:error.message});return}
  const timer=setTimeout(()=>{child.kill('SIGKILL');finish({status:'startup_timeout',passed:false,timeoutMs,stderrTail:stderr.slice(-800)})},timeoutMs);
  child.stdout.on('data',chunk=>{stdout=(stdout+chunk.toString()).slice(-100000)});
  child.stderr.on('data',chunk=>{stderr=(stderr+chunk.toString()).slice(-2000)});
  child.on('error',error=>finish({status:'unavailable',passed:false,error:error.message}));
  child.on('close',code=>{const passed=code===0&&/<output id="result">PASS<\/output>/.test(stdout);finish({status:passed?'startup_ok':'startup_failed',passed,exitCode:code,stderrTail:stderr.slice(-800)})});
 });
}
async function diagnose(opts={}){
 const startup=await runProbe(opts);
 if(!startup.passed)return {stage:'chromium_startup',startup,app:null,passed:false};
 const app=await checkBrowser(opts);
 return {stage:app.passed?'validated':'application',startup,app,passed:app.passed};
}
if(require.main===module)diagnose().then(result=>{console.log(JSON.stringify(result,null,2));if(!result.passed)process.exitCode=1});
module.exports={runProbe,diagnose};
