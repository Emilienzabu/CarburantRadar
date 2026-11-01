/* CarburantRadar : véhicules + classement des stations par coût total.
 * Injecté au déploiement dans france/, espagne/ et italie/ index.html par generator/app_patches.py (voir ce module).
 *
 * Coût total d'une station = plein + trajet
 *   plein  = 80 % du réservoir x prix de la station
 *   trajet = distance aller-retour x consommation / 100 x prix de la station
 * Radar : distance aller-retour = 2 x distance de la station (par la route si connue, sinon vol d'oiseau x 1,3).
 * Trajet : distance = kilomètres de détour par rapport au trajet direct (pas d'aller-retour).
 */
(function () {
  'use strict';
  var W = window;
  var LANG = (document.documentElement.getAttribute('lang') || 'fr').slice(0, 2);
  var FILL = 0.8;     // part du réservoir remplie à chaque plein
  var ROAD = 1.3;     // facteur route / vol d'oiseau, pour estimer quand la vraie route n'est pas calculée
  var NCAND = 20;     // nombre de stations dont on calcule la vraie route
  var LS_LIST = 'cr_vehicles', LS_DEF = 'cr_vehicle_default';

  // Type de carburant commun aux trois pays : un véhicule créé en France garde son carburant en Espagne ou en Italie
  var TYPES = ({
    fr: { Gazole: 'diesel', SP95: 'sp95', SP98: 'sp98', E10: 'e10', E85: 'e85', GPLc: 'lpg' },
    es: { GasoleoA: 'diesel', GasoleoPremium: 'dieselplus', Gasolina95: 'sp95', Gasolina98: 'sp98', GLP: 'lpg' },
    it: { benzina: 'sp95', gasolio: 'diesel', gpl: 'lpg', metano: 'methane' }
  })[LANG] || {};

  var I18N = {
    fr: {
      vehicles: 'Véhicules', sub: 'Réservoir, consommation et carburant : ils servent à classer les stations par coût total.',
      add: 'Ajouter un véhicule', edit: 'Modifier', del: 'Supprimer', setDefault: 'Par défaut', defBadge: 'par défaut',
      name: 'Nom', tank: 'Réservoir (L)', conso: 'Consommation (L/100 km)', fuel: 'Carburant', noFuel: 'Aucun (je choisis à chaque fois)',
      save: 'Enregistrer', cancel: 'Annuler', defName: 'Mon véhicule', radar: 'Véhicule',
      eName: 'Donnez un nom au véhicule.', eTank: 'Réservoir : entre 5 et 300 L.', eConso: 'Consommation : entre 1 et 40 L/100 km.',
      eLast: 'Gardez au moins un véhicule.', saved: 'Véhicule enregistré.', confirmDel: 'Supprimer ce véhicule ?',
      total: 'Coût total estimé', fill: 'plein', trip: 'trajet A/R', best: 'meilleur choix', moreThanBest: 'de plus que le meilleur', vsAvg: 'vs moyenne', est: '(estimé)'
    },
    es: {
      vehicles: 'Vehículos', sub: 'Depósito, consumo y combustible: sirven para ordenar las estaciones por coste total.',
      add: 'Añadir un vehículo', edit: 'Editar', del: 'Eliminar', setDefault: 'Predeterminado', defBadge: 'predeterminado',
      name: 'Nombre', tank: 'Depósito (L)', conso: 'Consumo (L/100 km)', fuel: 'Combustible', noFuel: 'Ninguno (lo elijo cada vez)',
      save: 'Guardar', cancel: 'Cancelar', defName: 'Mi vehículo', radar: 'Vehículo',
      eName: 'Pon un nombre al vehículo.', eTank: 'Depósito: entre 5 y 300 L.', eConso: 'Consumo: entre 1 y 40 L/100 km.',
      eLast: 'Conserva al menos un vehículo.', saved: 'Vehículo guardado.', confirmDel: '¿Eliminar este vehículo?',
      total: 'Coste total estimado', fill: 'repostaje', trip: 'trayecto I/V', best: 'mejor opción', moreThanBest: 'más que la mejor', vsAvg: 'vs media', est: '(estimado)'
    },
    it: {
      vehicles: 'Veicoli', sub: 'Serbatoio, consumo e carburante: servono a ordinare i distributori per costo totale.',
      add: 'Aggiungi un veicolo', edit: 'Modifica', del: 'Elimina', setDefault: 'Predefinito', defBadge: 'predefinito',
      name: 'Nome', tank: 'Serbatoio (L)', conso: 'Consumo (L/100 km)', fuel: 'Carburante', noFuel: 'Nessuno (lo scelgo ogni volta)',
      save: 'Salva', cancel: 'Annulla', defName: 'Il mio veicolo', radar: 'Veicolo',
      eName: 'Dai un nome al veicolo.', eTank: 'Serbatoio: tra 5 e 300 L.', eConso: 'Consumo: tra 1 e 40 L/100 km.',
      eLast: 'Tieni almeno un veicolo.', saved: 'Veicolo salvato.', confirmDel: 'Eliminare questo veicolo?',
      total: 'Costo totale stimato', fill: 'pieno', trip: 'tragitto A/R', best: 'scelta migliore', moreThanBest: 'in più rispetto al migliore', vsAvg: 'vs media', est: '(stimato)'
    }
  };
  var T = I18N[LANG] || I18N.fr;

  // ------------------------------------------------------------ utilitaires
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function num(x) { var n = parseFloat(String(x).replace(',', '.')); return isFinite(n) ? n : null; }
  function fmt(n) { return String(Math.round(n * 10) / 10); }
  function money(n) { return n.toFixed(2); }
  function readJSON(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }
  function typeOfKey(k) { return TYPES[k] || null; }
  function keyOfType(t) { for (var k in TYPES) { if (TYPES[k] === t) return k; } return null; }
  function validVehicle(v) {
    return v && typeof v.id === 'string' && typeof v.nom === 'string' && v.nom.trim() &&
      typeof v.reservoir === 'number' && v.reservoir >= 5 && v.reservoir <= 300 &&
      typeof v.conso === 'number' && v.conso >= 1 && v.conso <= 40;
  }
  function newId() { return 'v_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function fuelOptions() {
    var out = [], bs = document.querySelectorAll('#fg .fb');
    for (var i = 0; i < bs.length; i++) {
      var k = bs[i].getAttribute('data-f'), t = typeOfKey(k);
      if (t) out.push({ type: t, key: k, label: bs[i].textContent.trim() });
    }
    return out;
  }
  function fuelLabel(type) { var o = fuelOptions().filter(function (x) { return x.type === type; })[0]; return o ? o.label : null; }

  // ------------------------------------------------------------ stockage
  function saveList(list, defId, quiet) {
    try { localStorage.setItem(LS_LIST, JSON.stringify(list)); localStorage.setItem(LS_DEF, defId); } catch (e) { }
    if (!quiet && typeof W.synchroniserVersServeur === 'function') W.synchroniserVersServeur();
  }
  function migrate() {
    // Premier lancement : l'ancien réglage unique (réservoir + consommation) devient le premier véhicule
    var tank = num(localStorage.getItem('cr_tank_size')), conso = num(localStorage.getItem('cr_consumption'));
    var v = { id: newId(), nom: T.defName, reservoir: tank && tank >= 5 && tank <= 300 ? tank : 50, conso: conso && conso >= 1 && conso <= 40 ? conso : 6, type: typeOfKey(W.fu) };
    saveList([v], v.id, true);
    return [v];
  }
  function getVehicles() {
    var l = readJSON(LS_LIST);
    l = Array.isArray(l) ? l.filter(validVehicle) : [];
    return l.length ? l : migrate();
  }
  function getDefaultId() {
    var l = getVehicles(), d = localStorage.getItem(LS_DEF);
    return l.some(function (v) { return v.id === d; }) ? d : l[0].id;
  }
  var activeId = null;
  function getActive() {
    var l = getVehicles(), a = l.filter(function (v) { return v.id === activeId; })[0] || l.filter(function (v) { return v.id === getDefaultId(); })[0] || l[0];
    activeId = a.id;
    return a;
  }

  // ------------------------------------------------------------ calcul
  function litres(v) { return v.reservoir * FILL; }
  function totalFor(prix, kmAR, v) { return prix * (litres(v) + kmAR * v.conso / 100); }
  function scoreOf(t, mn, mx) { return mx === mn ? 100 : Math.round((1 - (t - mn) / (mx - mn)) * 100); }

  // Radar : stations dont on calcule la vraie route. On les choisit avec une estimation du coût total (et non avec le seul prix),
  // pour qu'une station proche et un peu plus chère ne soit pas écartée avant d'être comparée.
  W.crPickCandidates = function (list) {
    var v = getActive();
    return list.filter(function (s) { return s.prix > 0; })
      .map(function (s) { return { s: s, e: totalFor(s.prix, 2 * s.distance * ROAD, v) }; })
      .sort(function (a, b) { return a.e - b.e; }).slice(0, NCAND).map(function (x) { return x.s; });
  };

  // Radar : classement de toutes les stations avec prix ; les stations sans prix suivent, sans classement
  W.crRankStations = function (wp) {
    var v = getActive();
    var rows = wp.map(function (s) {
      var road = typeof s.distRoute === 'number';
      var km = road ? s.distRoute / 1000 : s.distance * ROAD;
      var plein = s.prix * litres(v), trajet = s.prix * 2 * km * v.conso / 100;
      return { id: s.id, adresse: s.adresse, ville: s.ville, cp: s.cp, lat: s.lat, lon: s.lon, prix: s.prix, distance: s.distance, duree: s.duree, distRoute: s.distRoute,
        automate: s.automate, crTotal: plein + trajet, crPlein: plein, crTrajet: trajet, crKm: km, crEst: !road, score: 0 };
    });
    var anyRoad = rows.some(function (r) { return !r.crEst; });
    rows.sort(function (a, b) { if (anyRoad && a.crEst !== b.crEst) return a.crEst ? 1 : -1; return a.crTotal - b.crTotal; });
    var tots = rows.map(function (r) { return r.crTotal; }), mn = Math.min.apply(null, tots), mx = Math.max.apply(null, tots);
    var avg = tots.reduce(function (a, b) { return a + b; }, 0) / (tots.length || 1);
    rows.forEach(function (r) { r.score = scoreOf(r.crTotal, mn, mx); r.crVsBest = r.crTotal - rows[0].crTotal; r.crVsAvg = avg - r.crTotal; });
    var np = (W.st || []).filter(function (s) { return !s.prix || s.prix <= 0; }).map(function (s) {
      return { id: s.id, adresse: s.adresse, ville: s.ville, cp: s.cp, lat: s.lat, lon: s.lon, prix: s.prix, distance: s.distance, duree: null, distRoute: null, automate: s.automate, score: null };
    });
    return rows.concat(np);
  };

  W.crRankLabel = function (s) { return typeof s.crTotal === 'number' ? money(s.crTotal) + ' €' : ''; };

  // Bloc affiché sur chaque carte à la place de l'ancien « économie vs moyenne » + « score »
  W.crCardBlocks = function (s) {
    if (typeof s.crTotal !== 'number') return '';
    var first = s.crVsBest < 0.005;
    var line2 = (first ? T.best : '+' + money(s.crVsBest) + ' € ' + T.moreThanBest) + ' · ' + T.vsAvg + ' ' + (s.crVsAvg >= 0 ? '+' : '') + money(s.crVsAvg) + ' €';
    return '<div class="metrics" style="background:var(--bg-sunken);border-radius:8px;padding:8px;margin:8px 0;">' +
      '<div class="m" style="grid-column:span 3"><div class="ml">' + T.total + '</div>' +
      '<div class="mv">' + money(s.crTotal) + ' €' + (s.crEst ? ' <span style="font-size:11px;font-weight:400;opacity:.7">' + T.est + '</span>' : '') + '</div>' +
      '<div style="font-size:11px;color:var(--text-muted);margin-top:4px;">' + T.fill + ' ' + money(s.crPlein) + ' € + ' + T.trip + ' ' + money(s.crTrajet) + ' € (2 × ' + fmt(s.crKm) + ' km)</div>' +
      '<div style="font-size:11px;color:var(--text-muted);margin-top:2px;">' + line2 + '</div>' +
      '</div></div>' +
      (s.score !== null ? '<div class="bar"><div class="fill" style="width:' + s.score + '%"></div></div>' : '');
  };

  // Trajet : présélection des stations dont on calcule le détour réel, avec une estimation du coût total
  W.crTrajetPreSort = function (stations, la, lo, dLat, dLon) {
    var v = getActive(), direct = W.hv(la, lo, dLat, dLon);
    stations.forEach(function (s) {
      var det = Math.max(0, (W.hv(la, lo, s.lat, s.lon) + W.hv(s.lat, s.lon, dLat, dLon) - direct) * ROAD);
      s.crEstKm = det;
      s.crEst = totalFor(s.prix, det, v);
    });
    stations.sort(function (a, b) {
      var x = isFinite(a.crEst) ? a.crEst : Infinity, y = isFinite(b.crEst) ? b.crEst : Infinity;
      return x === y ? 0 : x - y;
    });
  };

  // Trajet : classement final (détour réel en km quand il est connu, sinon l'estimation)
  W.crTrajetRank = function (list) {
    var v = getActive();
    list.forEach(function (s) {
      var km = typeof s.detourKm === 'number' ? Math.max(0, s.detourKm) : (s.crEstKm || 0);
      s.crTotal = totalFor(s.prix, km, v);
    });
    var tots = list.map(function (s) { return s.crTotal; }), mn = Math.min.apply(null, tots), mx = Math.max.apply(null, tots);
    list.forEach(function (s) { s.score = scoreOf(s.crTotal, mn, mx); });
    list.sort(function (a, b) { return a.crTotal - b.crTotal; });
  };

  // ------------------------------------------------------------ véhicule actif et carburant
  function applyFuelOfActive() {
    var v = getActive(), k = v.type ? keyOfType(v.type) : null;
    if (!k) return false;
    var tc = document.getElementById('trajetCarb');   // le mode Trajet a sa propre liste de carburants
    if (tc) { for (var j = 0; j < tc.options.length; j++) { if (tc.options[j].value === k) { tc.value = k; break; } } }
    if (W.fu === k) return false;
    W.fu = k;
    try { localStorage.setItem('cr_fu', k); } catch (e) { }
    var bs = document.querySelectorAll('.fb');
    for (var i = 0; i < bs.length; i++) { bs[i].classList.remove('a'); if (bs[i].getAttribute('data-f') === k) bs[i].classList.add('a'); }
    return true;
  }
  function refreshRanking() {
    if (W.la !== null && W.la !== undefined && typeof W.load === 'function') W.load();
    else if (W.st && W.st.length && typeof W.render === 'function') W.render();
  }
  W.crSetActive = function (id) {
    activeId = id;
    applyFuelOfActive();
    renderBar();
    refreshRanking();
    if (typeof W.synchroniserVersServeur === 'function') W.synchroniserVersServeur();
  };

  // ------------------------------------------------------------ sélecteur de véhicule (onglets Radar et Trajet)
  function renderBar() {
    var ids = [['crVehicleBar', 'crVehSel'], ['crVehicleBar2', 'crVehSel2']];
    var list = getVehicles(), a = getActive();
    ids.forEach(function (pair) {
      var bar = document.getElementById(pair[0]);
      if (!bar) return;
      bar.innerHTML = '<label for="' + pair[1] + '">' + esc(T.radar) + '</label><select id="' + pair[1] + '" class="cr-vsel">' +
        list.map(function (v) { return '<option value="' + esc(v.id) + '"' + (v.id === a.id ? ' selected' : '') + '>' + esc(v.nom) + '</option>'; }).join('') + '</select>';
      document.getElementById(pair[1]).onchange = function () { W.crSetActive(this.value); };
    });
  }

  // ------------------------------------------------------------ carte « Véhicules » de la page Personnalisation
  var editing = null;   // null | 'new' | id du véhicule modifié
  function formHtml(v) {
    var opts = '<option value="">' + esc(T.noFuel) + '</option>' + fuelOptions().map(function (o) {
      return '<option value="' + o.type + '"' + (v && v.type === o.type ? ' selected' : '') + '>' + esc(o.label) + '</option>';
    }).join('');
    return '<div class="cr-vform">' +
      '<label>' + T.name + '</label><input id="crVName" class="modal-input" type="text" maxlength="30" value="' + esc(v ? v.nom : '') + '">' +
      '<div class="cr-vtwo"><div><label>' + T.tank + '</label><input id="crVTank" class="modal-input" type="number" inputmode="decimal" step="0.1" min="5" max="300" value="' + (v ? v.reservoir : '') + '" placeholder="50"></div>' +
      '<div><label>' + T.conso + '</label><input id="crVConso" class="modal-input" type="number" inputmode="decimal" step="0.1" min="1" max="40" value="' + (v ? v.conso : '') + '" placeholder="6.0"></div></div>' +
      '<label>' + T.fuel + '</label><select id="crVType" class="modal-input">' + opts + '</select>' +
      '<div class="cr-vact"><button type="button" class="cr-vprimary" data-act="save">' + T.save + '</button><button type="button" data-act="cancel">' + T.cancel + '</button></div></div>';
  }
  function status(msg, bad) {
    var e = document.getElementById('crVStatus');
    if (e) { e.textContent = msg; e.style.color = bad ? 'var(--danger)' : 'var(--text-muted)'; }
  }
  function renderCard() {
    var box = document.getElementById('crVehiclesCard');
    if (!box) return;
    var list = getVehicles(), def = getDefaultId();
    var h = '<div class="side-item-name">' + T.vehicles + '</div><div class="side-item-sub">' + T.sub + '</div>';
    list.forEach(function (v) {
      if (editing === v.id) { h += formHtml(v); return; }
      var fl = v.type ? fuelLabel(v.type) : null;
      h += '<div class="cr-vrow' + (v.id === def ? ' cr-vdef' : '') + '"><div class="cr-vtop"><span class="cr-vname">' + esc(v.nom) + '</span>' +
        (v.id === def ? '<span class="cr-vbadge">' + T.defBadge + '</span>' : '') + '</div>' +
        '<div class="cr-vsub">' + fmt(v.reservoir) + ' L · ' + fmt(v.conso) + ' L/100 km' + (fl ? ' · ' + esc(fl) : '') + '</div>' +
        '<div class="cr-vact">' + (v.id !== def ? '<button type="button" data-act="def" data-id="' + esc(v.id) + '">' + T.setDefault + '</button>' : '') +
        '<button type="button" data-act="edit" data-id="' + esc(v.id) + '">' + T.edit + '</button>' +
        (list.length > 1 ? '<button type="button" data-act="del" data-id="' + esc(v.id) + '">' + T.del + '</button>' : '') + '</div></div>';
    });
    h += editing === 'new' ? formHtml(null) : '<button type="button" class="add-btn" data-act="add">' + T.add + '</button>';
    h += '<div class="cr-vstatus" id="crVStatus"></div>';
    box.innerHTML = h;
  }
  function readForm() {
    var nom = document.getElementById('crVName').value.trim(), tank = num(document.getElementById('crVTank').value), conso = num(document.getElementById('crVConso').value);
    var type = document.getElementById('crVType').value || null;
    if (!nom) return { err: T.eName };
    if (!(tank >= 5 && tank <= 300)) return { err: T.eTank };
    if (!(conso >= 1 && conso <= 40)) return { err: T.eConso };
    return { nom: nom.slice(0, 30), reservoir: tank, conso: conso, type: type };
  }
  function onClick(ev) {
    var b = ev.target.closest ? ev.target.closest('button[data-act]') : null;
    if (!b) return;
    var act = b.getAttribute('data-act'), id = b.getAttribute('data-id'), list = getVehicles(), def = getDefaultId();
    if (act === 'add') { editing = 'new'; renderCard(); var n = document.getElementById('crVName'); if (n) n.focus(); return; }
    if (act === 'edit') { editing = id; renderCard(); return; }
    if (act === 'cancel') { editing = null; renderCard(); return; }
    if (act === 'def') { saveList(list, id); renderCard(); return; }
    if (act === 'del') {
      if (list.length < 2) { status(T.eLast, true); return; }
      if (typeof W.confirm === 'function' && !W.confirm(T.confirmDel)) return;
      var rest = list.filter(function (v) { return v.id !== id; });
      var wasActive = getActive().id === id;
      saveList(rest, def === id ? rest[0].id : def);
      if (wasActive) activeId = null;
      renderCard(); renderBar();
      if (wasActive) { applyFuelOfActive(); refreshRanking(); }
      return;
    }
    if (act === 'save') {
      var f = readForm();
      if (f.err) { status(f.err, true); return; }
      var cur = getActive().id, vid;
      if (editing === 'new') { vid = newId(); list.push({ id: vid, nom: f.nom, reservoir: f.reservoir, conso: f.conso, type: f.type }); }
      else { vid = editing; list = list.map(function (v) { return v.id === vid ? { id: vid, nom: f.nom, reservoir: f.reservoir, conso: f.conso, type: f.type } : v; }); }
      saveList(list, def);
      editing = null;
      renderCard(); renderBar(); status(T.saved, false);
      if (vid === cur) { applyFuelOfActive(); refreshRanking(); }
      return;
    }
  }

  // ------------------------------------------------------------ interface exposée aux correctifs de synchronisation
  W.crGetVehicles = function () { return getVehicles(); };
  W.crGetDefaultId = function () { return getDefaultId(); };
  W.crApplyServer = function (list, defId) {
    var ok = Array.isArray(list) ? list.filter(validVehicle) : [];
    if (!ok.length) return;
    saveList(ok, ok.some(function (v) { return v.id === defId; }) ? defId : ok[0].id, true);
    activeId = null;
    applyFuelOfActive();
    renderBar(); renderCard();
  };
  W.crRenderVehicles = function () { renderCard(); renderBar(); };

  // ------------------------------------------------------------ style + initialisation
  var css = document.createElement('style');
  css.textContent =
    '.cr-vbar{display:flex;align-items:center;gap:8px;margin-bottom:10px}' +
    '.cr-vbar label{font-size:12px;color:var(--text-muted);white-space:nowrap}' +
    '.cr-vsel{flex:1;min-width:0;background:var(--bg-surface);color:var(--text);border:1px solid var(--border);border-radius:10px;padding:9px 10px;font-size:13px}' +
    '.cr-vrow{background:var(--bg-surface);border:1px solid var(--border);border-radius:10px;padding:10px;margin-top:8px}' +
    '.cr-vdef{border-color:var(--accent)}' +
    '.cr-vtop{display:flex;align-items:center;gap:8px}.cr-vname{font-size:14px;font-weight:700}' +
    '.cr-vbadge{font-size:10px;font-weight:700;color:var(--accent-text);background:var(--accent);border-radius:6px;padding:2px 6px}' +
    '.cr-vsub{font-size:12px;color:var(--text-muted);margin-top:2px}' +
    '.cr-vact{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}' +
    '.cr-vact button{background:var(--input-bg);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:7px 10px;font-size:12px;font-weight:600;cursor:pointer}' +
    '.cr-vact button.cr-vprimary{background:var(--accent);color:var(--accent-text);border-color:var(--accent)}' +
    '.cr-vform{background:var(--bg-surface);border:1px solid var(--accent);border-radius:10px;padding:10px;margin-top:8px}' +
    '.cr-vform label{display:block;font-size:11px;color:var(--text-muted);margin-bottom:2px}' +
    '.cr-vtwo{display:flex;gap:8px}.cr-vtwo>div{flex:1;min-width:0}' +
    '.cr-vstatus{font-size:11px;color:var(--text-muted);margin-top:6px;min-height:14px}';
  document.head.appendChild(css);

  function init() {
    getVehicles();
    activeId = getDefaultId();
    applyFuelOfActive();
    var box = document.getElementById('crVehiclesCard');
    if (box) box.addEventListener('click', onClick);
    renderBar(); renderCard();
  }
  init();
})();
