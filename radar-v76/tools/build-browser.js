'use strict';
// Rebuilds the two browser bundles from the CommonJS modules (format of V50-V76 archives).
const fs=require('node:fs'),path=require('node:path');
const dir=process.argv[2]||'.';
const out=process.argv[3]||dir;
const read=n=>fs.readFileSync(path.join(dir,n+'.js'),'utf8');
function bundle(mods,entry,global,loader){
  let s='(function(){"use strict";const modules={};\n';
  for(const m of mods)s+="modules['"+m+"']=function(require,module,exports){\n"+read(m)+"\n};\n";
  return s+loader+'window.'+global+'=load("'+entry+'");})();';
}
const L1='const cache={};function load(n){if(cache[n])return cache[n].exports;const m={exports:{}};cache[n]=m;modules[n](x=>load(x.replace(/^\\.\\//,"")),m,m.exports);return m.exports;}';
const L2='const cache={};function load(name){name=name.replace(/^\\.\\//,"");if(cache[name])return cache[name].exports;const m={exports:{}};cache[name]=m;modules[name](load,m,m.exports);return m.exports;}';
const files={
 'radar-live.browser.js':bundle(['radar-live','garage','radar-top10','radar-cost','radar-search'],'radar-live','CarburantRadarLive',L1),
 'radar-real-provider.browser.js':bundle(['radar-real-provider','proxy-adapter','routing','snapshot-v2-client','station-pages'],'radar-real-provider','CarburantRadarReal',L2),
 'radar-ui.browser.js':read('radar-ui')
};
for(const [n,c] of Object.entries(files))fs.writeFileSync(path.join(out,n),c);
