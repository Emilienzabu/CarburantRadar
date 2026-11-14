'use strict';
// Local-only, read-only preview. Never forwards requests to production services.
const http=require('node:http');
const fs=require('node:fs/promises');
const path=require('node:path');
const ROOT=__dirname;
const ALLOWED=new Map([
 ['/', ['radar-interface.html','text/html; charset=utf-8']],
 ['/radar-interface.html',['radar-interface.html','text/html; charset=utf-8']],
 ['/browser-smoke.html',['browser-smoke.html','text/html; charset=utf-8']],
 ...['radar-ui.browser.js','radar-live.browser.js','radar-real-provider.browser.js'].map(n=>['/'+n,[n,'text/javascript; charset=utf-8']])
]);
function createPreviewServer(){return http.createServer(async(req,res)=>{
  const url=(req.url||'').split('?')[0];
  const entry=ALLOWED.get(url);
  res.setHeader('Cache-Control','no-store');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Content-Security-Policy',"default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'none'; img-src 'self' data:; base-uri 'none'; form-action 'none'");
  if(req.method!=='GET'||!entry){res.writeHead(404);res.end('Not found');return;}
  try{let body=await fs.readFile(path.join(ROOT,entry[0]));if(entry[0]==='radar-interface.html'){body=Buffer.from(body.toString('utf8').replace('id="real" type="button"','id="real" type="button" disabled').replace('Les données réelles nécessitent votre autorisation de localisation et une connexion réseau.','Prévisualisation isolée : données réelles désactivées. Utilisez la démonstration fictive.'))}res.writeHead(200,{'Content-Type':entry[1]});res.end(body)}
  catch{res.writeHead(500);res.end('Preview unavailable')}
 })}
if(require.main===module){const server=createPreviewServer();server.listen(0,'127.0.0.1',()=>console.log('Local preview: http://127.0.0.1:'+server.address().port+'/browser-smoke.html'))}
module.exports={createPreviewServer};
