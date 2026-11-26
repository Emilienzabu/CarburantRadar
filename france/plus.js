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
      <section data-plus-billing hidden aria-label="Abonnement de test">
        <p>Abonnement de test Stripe. Aucun paiement réel.</p>
        <button type="button" data-plus-plan="month">Tester à 1 €/mois</button>
        <button type="button" data-plus-plan="year">Tester à 10 €/an</button>
        <button type="button" data-plus-portal hidden>Gérer mon abonnement de test</button>
      </section>
      <p data-plus-message role="status" aria-live="polite"></p>`;
    document.body.append(dialog);
    const select = selector => dialog.querySelector(selector);
    const form = select('form');
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
      unlock.hidden = !analysisState || hasDetailedAnalysis();
    }

    function date(timestamp) {
      return new Intl.DateTimeFormat('fr-FR', {dateStyle: 'long', timeZone: 'Europe/Paris'}).format(timestamp);
    }

    async function requestPlus(action, token, data = {}) {
        const response = await fetch(PROXY + '/plus/' + action, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token},
          body: JSON.stringify(data),
          signal: AbortSignal.timeout(10000),
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
        const payload = await requestPlus(action, token, data);
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
      login.hidden = true;
      billing.hidden = true;
      status.textContent = 'Chargement de ton compte…';
      dialog.showModal();
      const data = await act('status');
      if (data) showState(data);
    });
    menu.insertBefore(link, document.getElementById('crV07Install'));
    const unlock = document.createElement('button');
    unlock.type = 'button';
    unlock.textContent = 'Débloquer l’analyse détaillée pour 24 h · 1 crédit';
    unlock.hidden = true;
    claim.after(unlock);
    function hasDetailedAnalysis() {
      return analysisState?.token === getToken() &&
        (analysisState.lifetime || analysisState.expires > Date.now() || analysisState.plusUntil > Date.now());
    }
    const setPeriod = window.setPeriodeItem;
    if (typeof setPeriod === 'function') window.setPeriodeItem = async function (id, period) {
      const token = getToken();
      if (period <= 7 || !token || hasDetailedAnalysis()) return setPeriod(id, period);
      let state;
      try {
        state = await requestPlus('status', token);
      } catch {
        return;
      }
      if (token !== getToken() || analyseOpenId !== id) return;
      showState(state);
      if (!state.analysis || hasDetailedAnalysis()) return setPeriod(id, period);
      pendingPeriod = {id, period, token};
      openMenu();
      link.click();
    };
    dialog.addEventListener('close', () => { pendingPeriod = undefined; });
    unlock.addEventListener('click', async () => {
      const state = await act('unlock-analysis');
      if (!state) return;
      showState(state);
      message.textContent = 'Analyse détaillée débloquée pour 24 h.';
      if (pendingPeriod?.token === getToken() && hasDetailedAnalysis()) {
        setPeriod(pendingPeriod.id, pendingPeriod.period);
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
