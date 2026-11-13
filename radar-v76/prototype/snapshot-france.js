'use strict';
// Prototype: immutable versioned dataset and atomic in-process pointer swap.
const crypto=require('node:crypto');
const FUELS={Gazole:'gazole_prix',SP95:'sp95_prix',SP98:'sp98_prix',E10:'e10_prix',E85:'e85_prix',GPLc:'gplc_prix'};
const finite=n=>typeof n==='number'&&Number.isFinite(n);
function coord(row){
 const lat=Number(row?.geom?.lat??(row?.latitude!==undefined?Number(row.latitude)/100000:NaN));
 const lon=Number(row?.geom?.lon??(row?.longitude!==undefined?Number(row.longitude)/100000:NaN));
 return finite(lat)&&finite(lon)&&Math.abs(lat)<=90&&Math.abs(lon)<=180?{lat,lon}:null;
}
function normalize(rows){
 if(!Array.isArray(rows))throw Error('invalid_dataset');
 const ids=new Set(),out=[];
 for(const row of rows){
  if(!row||row.id===undefined||row.id===null||!String(row.id))throw Error('invalid_id');
  const id=String(row.id);if(ids.has(id))throw Error('duplicate_id');ids.add(id);
  const location=coord(row);if(!location)throw Error('invalid_coordinates');
  const prices={};for(const [fuel,key] of Object.entries(FUELS)){
   const value=row[key];if(value===undefined||value===null||value===''){prices[fuel]=null;continue;}
   const price=Number(value);if(!finite(price)||price<=0)throw Error('invalid_price');prices[fuel]=price;
  }
  out.push(Object.freeze({id,...location,prices:Object.freeze(prices),address:String(row.adresse??''),city:String(row.ville??'')}));
 }
 out.sort((a,b)=>a.id.localeCompare(b.id));return Object.freeze(out);
}
function haversineKm(a,b){const rad=Math.PI/180,dLat=(b.lat-a.lat)*rad,dLon=(b.lon-a.lon)*rad;const x=Math.sin(dLat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dLon/2)**2;return 6371*2*Math.asin(Math.min(1,Math.sqrt(x)));}
function buildSnapshot(rows,{version,createdAt=new Date().toISOString()}={}){
 if(typeof version!=='string'||!/^[-\w.]{1,100}$/.test(version))throw Error('invalid_version');
 if(!Number.isFinite(Date.parse(createdAt)))throw Error('invalid_timestamp');
 const stations=normalize(rows);
 const checksum=crypto.createHash('sha256').update(JSON.stringify(stations)).digest('hex');
 return Object.freeze({version,createdAt,checksum,count:stations.length,stations});
}
function querySnapshot(snapshot,{lat,lon,radiusKm,fuel,offset=0,limit=100}={}){
 if(!snapshot||!Array.isArray(snapshot.stations))throw Error('missing_snapshot');
 if(!finite(lat)||!finite(lon)||Math.abs(lat)>90||Math.abs(lon)>180||!finite(radiusKm)||radiusKm<=0||radiusKm>50||!FUELS[fuel]||!Number.isInteger(offset)||offset<0||!Number.isInteger(limit)||limit<1||limit>100)throw Error('invalid_query');
 const origin={lat,lon};const eligible=[];
 for(const s of snapshot.stations){const price=s.prices[fuel];if(price===null)continue;const km=haversineKm(origin,s);if(km<=radiusKm)eligible.push({id:s.id,lat:s.lat,lon:s.lon,price,distanceIndicativeKm:km,address:s.address,city:s.city});}
 eligible.sort((a,b)=>a.id.localeCompare(b.id));
 return {schemaVersion:2,snapshot:snapshot.version,checksum:snapshot.checksum,createdAt:snapshot.createdAt,complete:true,total:eligible.length,results:eligible.slice(offset,offset+limit),nextCursor:offset+limit<eligible.length?offset+limit:null};
}
function createSnapshotStore(){let active=null;const versions=new Map();return {
  stage(snapshot){if(!snapshot||!snapshot.version||!Object.isFrozen(snapshot.stations))throw Error('invalid_snapshot');if(versions.has(snapshot.version))throw Error('version_exists');versions.set(snapshot.version,snapshot);return snapshot.version;},
  publish(version){if(!versions.has(version))throw Error('unknown_version');active=versions.get(version);return active;},
  getActive(){return active;},
  query(params){if(!active)throw Error('not_ready');return querySnapshot(active,params);},
  getVersion(version){return versions.get(version)??null;}
};}
module.exports={FUELS,coord,normalize,haversineKm,buildSnapshot,querySnapshot,createSnapshotStore};
