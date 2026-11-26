(function () {
  function init() {
    const menu = document.getElementById('crV07Main');
    if (!menu) return;

    const dialog = document.createElement('dialog');
    dialog.className = 'cr-plus';
    dialog.setAttribute('aria-labelledby', 'crPlusTitle');
    dialog.innerHTML = `
      <header>
        <h2 id="crPlusTitle">CarburantRadar Plus</h2>
        <button type="button" class="cr-plus-close" aria-label="Fermer">×</button>
      </header>
      <p data-plus-status>Chargement de ton compte…</p>
      <p data-plus-balance hidden></p>
      <button type="button" data-plus-claim hidden>Réclamer mon crédit du jour</button>
      <button type="button" data-plus-login hidden>Me connecter</button>
      <button type="button" data-plus-code-toggle aria-expanded="false">J’ai un code</button>
      <form hidden>
        <label for="crPlusCode">Code Plus</label>
        <input id="crPlusCode" name="code" maxlength="64" required spellcheck="false" autocapitalize="characters" autocomplete="off">
        <button type="submit">Vérifier le code</button>
        <button type="button" data-plus-confirm hidden>Activer le code</button>
      </form>
      <section data-plus-alerts hidden aria-labelledby="crExtraAlertsTitle">
        <h3 id="crExtraAlertsTitle">Alertes supplémentaires</h3>
        <ul data-plus-alert-list></ul>
        <form data-plus-alert-form>
          <label for="crPlusAlertPlace">Lieu à surveiller</label>
          <select id="crPlusAlertPlace" name="place" required></select>
          <label for="crPlusAlertFuel">Carburant</label>
          <select id="crPlusAlertFuel" name="carburant"></select>
          <label for="crPlusAlertRadius">Rayon</label>
          <select id="crPlusAlertRadius" name="rayon">
            <option value="5">5 km</option><option value="10">10 km</option>
            <option value="20">20 km</option><option value="50">50 km</option>
          </select>
          <label for="crPlusAlertThreshold">Baisse par rapport à la moyenne</label>
          <select id="crPlusAlertThreshold" name="seuil">
            <option value="2">2 %</option><option value="3" selected>3 %</option>
            <option value="5">5 %</option><option value="8">8 %</option>
          </select>
          <button type="submit" data-plus-add-alert></button>
        </form>
      </section>
      <section data-plus-billing hidden aria-label="Abonnement de test">
        <p>Abonnement de test Stripe. Aucun paiement réel.</p>
        <button type="button" data-plus-plan="month">Tester à 1 €/mois</button>
        <button type="button" data-plus-plan="year">Tester à 10 €/an</button>
        <button type="button" data-plus-portal hidden>Gérer mon abonnement de test</button>
      </section>
      <p data-plus-message role="status" aria-live="polite"></p>`;
    document.body.append(dialog);
    const select = selector => dialog.querySelector(selector);
    const form = select('#crPlusCode').form;
    const code = select('#crPlusCode');
    const claim = select('[data-plus-claim]');
    const balance = select('[data-plus-balance]');
    const status = select('[data-plus-status]');
    const message = select('[data-plus-message]');
    const confirm = select('[data-plus-confirm]');
    const login = select('[data-plus-login]');
    const toggle = select('[data-plus-code-toggle]');
    const billing = select('[data-plus-billing]');
    const portal = select('[data-plus-portal]');
    const plans = dialog.querySelectorAll('[data-plus-plan]');
    const alertSection = select('[data-plus-alerts]');
    const alertForm = select('[data-plus-alert-form]');
    const alertPlace = alertForm.elements.place;
    const alertList = select('[data-plus-alert-list]');
    const addAlert = select('[data-plus-add-alert]');
    let alertPlaces = [];
    let alertRetry;
    let tripComparison;
    let analysisState;
    let pendingPeriod;
    const errors = {
      account_required: 'Connecte-toi pour retrouver tes crédits et activer un code.',
      code_invalid: 'Ce code est introuvable. Vérifie la saisie.',
      code_used: 'Tu as déjà activé ce code.',
      code_expired: 'Ce code a expiré.',
      code_used_up: 'Toutes les utilisations de ce code ont été prises.',
      plus_lifetime_already_active: 'Tu as déjà le Plus à vie.',
      plus_already_active: 'Ton accès Plus est déjà actif.',
      checkout_other_plan_pending: 'Un autre paiement de test est déjà en cours. Tu peux reprendre la même offre.',
      credits_insufficient: 'Il te faut 1 crédit pour débloquer cette analyse.',
      analysis_unavailable: 'L’analyse détaillée est indisponible pour le moment.',
      extra_alert_invalid: 'Choisis un repère valide et un appareil compatible avec les notifications.',
      extra_alert_limit: 'Ton compte a atteint la limite d’alertes supplémentaires.',
      extra_alert_duplicate: 'Une alerte identique existe déjà.',
      extra_alert_missing: 'Cette alerte a déjà été supprimée.',
      advanced_no_data: 'Pas assez de données pour afficher ce résultat. Aucun crédit débité.',
      advanced_service_unavailable: 'Les données sont indisponibles. Aucun crédit débité.',
      advanced_in_progress: 'Un calcul détaillé est déjà en cours.',
    };
    let busy = false;
    let checked = '';

    function showState(data) {
      const {credits, canClaimToday, plus} = data;
      status.textContent = plus.lifetime ? 'Ton accès Plus est actif à vie.'
        : plus.active ? 'Ton accès Plus est actif jusqu’au ' + date(plus.until) + '.'
        : 'Ton compte est en offre gratuite.';
      balance.textContent = credits + (credits === 1 ? ' crédit disponible' : ' crédits disponibles');
      balance.hidden = false;
      claim.hidden = !canClaimToday;
      billing.hidden = data.billing?.test !== true;
      portal.hidden = !data.billing?.hasCustomer;
      plans.forEach(button => { button.hidden = plus.active || !data.billing?.canCheckout; });
      analysisState = data.analysis ? {token: getToken(), expires: data.analysis.expires,
        plusUntil: plus.until, lifetime: plus.lifetime} : null;
      unlock.hidden = !pendingPeriod || !analysisState;
      unlock.textContent = hasDetailedAnalysis() ? 'Afficher l’analyse détaillée' : 'Débloquer l’analyse détaillée pour 24 h · 1 crédit';
      alertSection.hidden = !Array.isArray(data.alerts);
      if (!alertSection.hidden) renderAlerts(data.alerts, plus.active);
    }

    function date(timestamp) {
      return new Intl.DateTimeFormat('fr-FR', {dateStyle: 'long', timeZone: 'Europe/Paris'}).format(timestamp);
    }

    async function requestPlus(action, token, data = {}, timeout = 10000) {
        const response = await fetch(PROXY + '/plus/' + action, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token},
          body: JSON.stringify(data),
        signal: AbortSignal.timeout(timeout),
        });
        const payload = await response.json();
      if (!response.ok) throw Object.assign(new Error(payload.error), {status: response.status});
      return payload;
    }

    async function act(action, data = {}) {
      if (busy) return null;
      const token = getToken();
      if (!token) {
        status.textContent = errors.account_required;
        login.hidden = false;
        return null;
      }
      busy = true;
      dialog.setAttribute('aria-busy', 'true');
      message.textContent = '';
      try {
        const payload = await requestPlus(action, token, data, action === 'analysis' ? 35000 : 10000);
        if (token !== getToken() || !dialog.open) return null;
        return payload;
      } catch (error) {
        if (token === getToken() && dialog.open) {
          if (error.status === 401) login.hidden = false;
          message.textContent = errors[error.message] || 'Le service Plus est indisponible. Réessaie dans un instant.';
          if (action === 'status') status.textContent = 'Solde indisponible.';
        }
        return null;
      } finally {
        busy = false;
        dialog.removeAttribute('aria-busy');
      }
    }

    function clearPreview() {
      checked = '';
      confirm.hidden = true;
      message.textContent = '';
    }

    code.addEventListener('input', clearPreview);
    toggle.addEventListener('click', () => {
      form.hidden = !form.hidden;
      toggle.setAttribute('aria-expanded', String(!form.hidden));
      clearPreview();
      if (!form.hidden) code.focus();
    });
    select('.cr-plus-close').addEventListener('click', () => dialog.close());
    async function openBilling(action, fields, host) {
      const session = await act(action, fields);
      if (!session) return;
      const target = URL.canParse(session.url) ? new URL(session.url) : null;
      if (target?.origin === 'https://' + host) window.location.assign(target.href);
      else message.textContent = 'Le lien Stripe est indisponible.';
    }
    plans.forEach(button => button.addEventListener('click', () =>
      openBilling('checkout', {plan: button.dataset.plusPlan}, 'checkout.stripe.com')));
    portal.addEventListener('click', () => openBilling('portal', {}, 'billing.stripe.com'));
    login.addEventListener('click', () => {
      dialog.close();
      openMenu('compte');
    });
    claim.addEventListener('click', async () => {
      const data = await act('claim');
      if (!data) return;
      showState(data);
      message.textContent = data.claimed ? 'Ton crédit du jour a été ajouté.' : 'Ton crédit du jour a déjà été réclamé.';
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy) return;
      clearPreview();
      const value = code.value.trim();
      const gift = await act('preview', {code: value});
      if (!gift || form.hidden || code.value.trim() !== value) return;
      checked = value;
      confirm.hidden = false;
      message.textContent = gift.lifetime ? 'Ce code te donne le Plus à vie.'
        : 'Ce code ajoute ' + gift.months + ' mois de Plus, jusqu’au ' + date(gift.until) + '.';
    });
    confirm.addEventListener('click', async () => {
      if (!checked || checked !== code.value.trim() || busy) return;
      const data = await act('redeem', {code: checked});
      checked = '';
      confirm.hidden = true;
      if (!data) return;
      code.value = '';
      showState(data);
      message.textContent = 'Ton accès Plus est activé.';
    });

    const link = document.createElement('button');
    link.type = 'button';
    link.className = 'cr-v07-row';
    link.innerHTML = '<span class="cr-v07-icon" aria-hidden="true">★</span><span class="cr-v07-label">CarburantRadar Plus</span><span class="cr-v07-chevron" aria-hidden="true">›</span>';
    link.addEventListener('click', async () => {
      if (busy || dialog.open) return;
      form.hidden = true;
      code.value = '';
      toggle.setAttribute('aria-expanded', 'false');
      clearPreview();
      balance.hidden = true;
      claim.hidden = true;
      unlock.hidden = true;
      alertSection.hidden = true;
      login.hidden = true;
      billing.hidden = true;
      status.textContent = 'Chargement de ton compte…';
      dialog.showModal();
      const data = await act('status');
      if (data) showState(data);
    });
    menu.insertBefore(link, document.getElementById('crV07Install'));
    function renderAlerts(alerts, hasPlus) {
      alertList.replaceChildren();
      for (const item of alerts) {
        const row = document.createElement('li');
        const label = document.createElement('p');
        label.textContent = item.name + ' · ' + (FL[item.carburant] || item.carburant) + ' · ' + item.rayon + ' km'
          + (item.active ? item.until && !hasPlus ? ' · jusqu’au ' + date(item.until) : ' · active' : ' · expirée');
        row.append(label);
        const actions = item.active ? [['remove', 'Supprimer']] : [['renew', 'Renouveler · 2 crédits'], ['remove', 'Supprimer']];
        actions.forEach(([action, caption]) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = caption;
          button.addEventListener('click', async () => {
            const state = await act('alerts/' + action, {id: item.id});
            if (state) showState(state);
          });
          row.append(button);
        });
        alertList.append(row);
      }
      const current = alertPlace.value;
      alertPlaces = getReps().slice();
      if (Number.isFinite(la) && Number.isFinite(lo)) alertPlaces.unshift({name: 'Position actuelle', lat: la, lon: lo});
      alertPlace.replaceChildren(...alertPlaces.map((location, i) => new Option(location.name, String(i))));
      if (current && alertPlace.options[current]) alertPlace.value = current;
      if (!alertPlaces.length) alertPlace.append(new Option('Localise-toi ou ajoute un repère', ''));
      addAlert.disabled = !alertPlaces.length;
      addAlert.textContent = hasPlus ? 'Activer l’alerte' : 'Activer 7 jours · 2 crédits';
    }
    alertForm.elements.carburant.replaceChildren(...Object.entries(FL).map(([key, label]) => new Option(label, key)));
    alertForm.elements.carburant.value = fu;
    let preparingAlert = false;
    alertForm.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy || preparingAlert) return;
      const token = getToken();
      const values = new FormData(alertForm);
      const place = alertPlaces[values.get('place')];
      if (!place) return;
      preparingAlert = true;
      addAlert.disabled = true;
      try {
        if (!('Notification' in window) || !navigator.serviceWorker || !('PushManager' in window)) {
          throw new Error('Cet appareil ne prend pas en charge les notifications.');
        }
        const permission = Notification.permission === 'default' ? await Notification.requestPermission() : Notification.permission;
        if (permission !== 'granted') throw new Error('Autorise les notifications pour activer cette alerte.');
        const registration = await crAlertTimeout(navigator.serviceWorker.ready, 10000, 'Le service de notifications ne répond pas.');
        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
        if (token !== getToken() || !dialog.open) return;
        const settings = {name: place.name, lat: place.lat, lon: place.lon, sub: subscription.toJSON(),
          carburant: values.get('carburant'), rayon: Number(values.get('rayon')), seuil: Number(values.get('seuil'))};
        const fingerprint = JSON.stringify(settings);
        if (alertRetry?.fingerprint !== fingerprint || alertRetry?.token !== token) {
          alertRetry = {fingerprint, token, id: crypto.randomUUID()};
        }
        const state = await act('alerts/add', {id: alertRetry.id, settings});
        if (!state) return;
        alertRetry = undefined;
        showState(state);
        message.textContent = 'Alerte supplémentaire activée.';
      } catch (error) {
        if (dialog.open && token === getToken()) message.textContent = error.message || 'Impossible d’activer l’alerte.';
      } finally {
        preparingAlert = false;
        addAlert.disabled = !alertPlaces.length;
      }
    });

    function showTripResult(section, result) {
      const title = document.createElement('h3');
      title.textContent = 'Comparaison de ' + result.verified + ' stations vérifiées';
      section.replaceChildren(title);
      for (const {label, station} of result.choices) {
        const row = document.createElement('p');
        row.textContent = label + ' · ' + (station.address || station.city) + ' · ' +
          station.total.toFixed(2) + ' € au total · ' + station.price.toFixed(3) + ' €/L · +' +
          Math.round(station.minutes) + ' min';
        section.append(row);
      }
      section.hidden = false;
    }

    const renderAlternatives = window.crTripRenderAlternatives;
    window.crTripRenderAlternatives = function (candidates) {
      renderAlternatives(candidates);
      const alternatives = document.getElementById('crTripAlternatives');
      const token = getToken();
      document.querySelector('[data-plus-trip-button]')?.remove();
      if (!alternatives || candidates.length < 2 || !token) return;
      if (tripComparison?.run !== crTripRun || tripComparison?.token !== token) {
        tripComparison = {run: crTripRun, token, id: crypto.randomUUID()};
      }
      const comparison = tripComparison;
      if (comparison.result) return showTripResult(alternatives, comparison.result);
      alternatives.hidden = true;
      requestPlus('status', token).then(state => {
        if (!alternatives.isConnected || comparison.run !== crTripRun || token !== getToken()) return;
        if (comparison.result) return showTripResult(alternatives, comparison.result);
        if (!state.trip) {
          alternatives.hidden = false;
          return;
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'add-btn';
        button.dataset.plusTripButton = '';
        const stateIsPlus = state.plus.active;
        const caption = stateIsPlus ? 'Comparer les autres stations · inclus dans Plus' : 'Comparer les autres stations · 1 crédit';
        button.textContent = caption;
        alternatives.before(button);
        button.addEventListener('click', async () => {
          button.disabled = true;
          button.textContent = 'Comparaison en cours…';
          try {
            const vehicle = radarVehicleConfig();
            if (!vehicle) throw new Error('vehicle');
            comparison.params ||= {origin: {lat: la, lon: lo},
              destination: {lat: trajetDestLat, lon: trajetDestLon}, fuel: crFuelForActive(), ...vehicle};
            const state = await requestPlus('trip', token, {id: comparison.id, confirm: !stateIsPlus,
              params: comparison.params}, 42000);
            if (token !== getToken() || comparison.run !== crTripRun) return;
            comparison.result = state.result;
            const currentAlternatives = document.getElementById('crTripAlternatives');
            if (currentAlternatives) showTripResult(currentAlternatives, state.result);
            document.querySelector('[data-plus-trip-button]')?.remove();
            button.remove();
          } catch (error) {
            button.textContent = caption;
            const notice = document.createElement('p');
            notice.setAttribute('role', 'status');
            notice.dataset.plusTripButton = '';
            notice.textContent = error.message === 'vehicle' ? 'Configure ton véhicule pour comparer.'
              : errors[error.message] || 'La comparaison est indisponible.';
            button.before(notice);
            button.addEventListener('click', () => notice.remove(), {once: true});
            button.disabled = false;
          }
        });
      }).catch(() => { alternatives.hidden = false; });
    };
    const unlock = document.createElement('button');
    unlock.type = 'button';
    unlock.textContent = 'Débloquer l’analyse détaillée pour 24 h · 1 crédit';
    unlock.hidden = true;
    claim.after(unlock);
    function hasDetailedAnalysis() {
      return analysisState?.token === getToken() &&
        (analysisState.lifetime || analysisState.expires > Date.now() || analysisState.plusUntil > Date.now());
    }
    function showAnalysisError(message) {
      const target = document.getElementById('analyseLoading');
      if (target) target.textContent = message;
    }

    function showAnalysis(result, params) {
      if (params.stationId === null) afficherResultatZone(result.dates, result.average, params.period);
      else afficherResultatStation(result.dates, result.prices, result.average, params.period, {rang: null, total: 0});
    }

    function protectAnalysis(original, args, params, req) {
      const token = getToken();
      if (params.period <= 7 || !token) return original(...args);
      const current = () => token === getToken() && req === analyseReqId;
      (async () => {
        try {
          const state = await requestPlus('status', token);
          if (!current()) return;
          if (!state.analysis) return original(...args);
          showState(state);
          if (hasDetailedAnalysis()) {
            const data = await requestPlus('analysis', token, {params}, 35000);
            if (current()) showAnalysis(data.result, params);
            return;
          }
          pendingPeriod = {params, token, req};
          openMenu();
          link.click();
        } catch (error) {
          if (!current()) return;
          if (analysisState?.token !== token) return original(...args);
          showAnalysisError(errors[error.message] || 'L’analyse détaillée est indisponible.');
        }
      })();
    }
    const analyzeZone = window.chargerSerieZone;
    window.chargerSerieZone = function (lat, lon, radius, period, fuel, req) {
      return protectAnalysis(analyzeZone, arguments, {center: {lat, lon}, radius, period, fuel, stationId: null}, req);
    };
    const analyzeStation = window.chargerSerieStation;
    window.chargerSerieStation = function (station, period, fuel, req) {
      return protectAnalysis(analyzeStation, arguments, {center: {lat: station.lat, lon: station.lon}, radius: 5,
        period, fuel, stationId: String(station.id)}, req);
    };
    dialog.addEventListener('close', () => {
      if (pendingPeriod?.req === analyseReqId) showAnalysisError('Sélectionne une période pour afficher le graphique.');
      pendingPeriod = undefined;
    });
    unlock.addEventListener('click', async () => {
      const pending = pendingPeriod;
      if (!pending || pending.token !== getToken()) return;
      const state = await act('analysis', {params: pending.params, confirm: !hasDetailedAnalysis()});
      if (!state) return;
      showState(state);
      message.textContent = 'Analyse détaillée débloquée pour 24 h.';
      if (pending.req === analyseReqId && pending.token === getToken()) {
        showAnalysis(state.result, pending.params);
        pendingPeriod = undefined;
        dialog.close();
        closeMenu();
      }
    });
    const back = new URL(location.href);
    if (['retour', 'annule'].includes(back.searchParams.get('plus'))) {
      back.searchParams.delete('plus');
      history.replaceState(history.state, '', back);
      openMenu();
      link.click();
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
