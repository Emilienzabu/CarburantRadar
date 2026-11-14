'use strict';
// Module indépendant : aucune requête réseau, aucune modification du site.
const FUELS = Object.freeze(['Gazole','SP95','SP98','E10','E85','GPLc']);
function finitePositive(n) { return typeof n === 'number' && Number.isFinite(n) && n > 0; }
function validateVehicle(v) {
  if (!v || typeof v !== 'object') throw new TypeError('Véhicule manquant');
  if (typeof v.id !== 'string' || !v.id.trim()) throw new TypeError('Identifiant véhicule invalide');
  if (typeof v.name !== 'string' || !v.name.trim() || v.name.length > 80) throw new TypeError('Nom véhicule invalide');
  if (!FUELS.includes(v.fuel)) throw new TypeError('Carburant inconnu');
  if (!finitePositive(v.consumption) || v.consumption > 100) throw new RangeError('Consommation invalide');
  if (!finitePositive(v.tankCapacity) || v.tankCapacity > 1000) throw new RangeError('Réservoir invalide');
  return true;
}
function validatePercent(percent) {
  if (typeof percent !== 'number' || !Number.isFinite(percent) || percent < 1 || percent > 100) throw new RangeError('Pourcentage invalide');
}
function costForStation(vehicle, fillPercent, station) {
  validateVehicle(vehicle); validatePercent(fillPercent);
  if (!station || typeof station !== 'object' || !finitePositive(station.price)) throw new TypeError('Prix station invalide');
  const litersToBuy = vehicle.tankCapacity * fillPercent / 100;
  const purchaseCost = litersToBuy * station.price;
  // distanceRoundTripKm doit provenir d'un itinéraire routier aller + retour, jamais d'une distance à vol d'oiseau.
  const d = station.distanceRoundTripKm;
  if (typeof d !== 'number' || !Number.isFinite(d) || d < 0) {
    return {id:station.id, status:'route_unavailable', litersToBuy, purchaseCost, travelLiters:null, travelCost:null, totalCost:null};
  }
  const travelLiters = d * vehicle.consumption / 100;
  const travelCost = travelLiters * station.price;
  return {id:station.id, status:'estimated', litersToBuy, purchaseCost, travelLiters, travelCost, totalCost:purchaseCost + travelCost};
}
function rankStations(vehicle, fillPercent, stations) {
  if (!Array.isArray(stations)) throw new TypeError('Stations invalides');
  return stations.map(s=>costForStation(vehicle,fillPercent,s)).sort((a,b)=>{
    if (a.totalCost===null) return b.totalCost===null?0:1;
    if (b.totalCost===null) return -1;
    return a.totalCost-b.totalCost;
  });
}
// La borne inférieure permet d'écarter uniquement une station dont le plein seul coûte déjà plus cher que le meilleur total connu.
function canBeatKnownBest(vehicle, fillPercent, stationPrice, bestTotalCost) {
  validateVehicle(vehicle);validatePercent(fillPercent);
  if (!finitePositive(stationPrice) || !Number.isFinite(bestTotalCost) || bestTotalCost < 0) throw new TypeError('Coûts invalides');
  return vehicle.tankCapacity*fillPercent/100*stationPrice <= bestTotalCost;
}
module.exports={FUELS,validateVehicle,validatePercent,costForStation,rankStations,canBeatKnownBest};
