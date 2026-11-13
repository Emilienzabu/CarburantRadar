'use strict';
// Explicit, bounded, read-only browser probe; never interprets a timeout as PASS.
const {spawn}=require('node:child_process');
const {createPreviewServer}=require('./preview-server');
async function checkBrowser({binary=process.env.CHROMIUM_BIN||'chromium',timeoutMs=12000}={}){
 const server=createPreviewServer();
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve)});
 const url=`http://127.0.0.1:${server.address().port}/browser-smoke.html`;
 try {
  return await new Promise(resolve=>{
   const child=spawn(binary,['--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-extensions','--no-first-run','--virtual-time-budget=1500','--dump-dom',url],{stdio:['ignore','pipe','pipe']});
   let stdout='',stderr='',finished=false;
   const finish=result=>{if(finished)return;finished=true;clearTimeout(timer);resolve(result)};
   const timer=setTimeout(()=>{child.kill('SIGKILL');finish({status:'timeout',passed:false,timeoutMs})},timeoutMs);
   child.stdout.on('data',chunk=>{stdout+=chunk.toString().slice(0,200000);if(stdout.length>400000)stdout=stdout.slice(-400000)});
   child.stderr.on('data',chunk=>{stderr+=chunk.toString().slice(0,2000);if(stderr.length>4000)stderr=stderr.slice(-4000)});
   child.on('error',error=>finish({status:'unavailable',passed:false,error:error.message}));
   child.on('close',code=>{const match=stdout.match(/<output id="result">([^<]*)<\/output>/);const outcome=match?.[1]||'NO_RESULT';finish({status:outcome==='PASS'&&code===0?'passed':'failed',passed:outcome==='PASS'&&code===0,exitCode:code,outcome,stderrTail:stderr.slice(-500)})});
  });
 }finally{await new Promise(resolve=>server.close(resolve))}
}
if(require.main===module){checkBrowser().then(result=>{console.log(JSON.stringify(result,null,2));if(!result.passed)process.exitCode=1})}
module.exports={checkBrowser};
