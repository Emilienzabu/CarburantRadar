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
      <p>Les offres Plus sont prévues à <strong>1 €/mois</strong> ou <strong>10 €/an</strong>.</p>
      <button type="button" data-plus-code-toggle aria-expanded="false">J’ai un code</button>
      <form hidden>
        <label for="crPlusCode">Code Plus</label>
        <input id="crPlusCode" name="code" maxlength="64" required spellcheck="false" autocapitalize="characters" autocomplete="off">
        <button type="submit">Vérifier le code</button>
        <button type="button" data-plus-confirm hidden>Activer le code</button>
      </form>
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
    const errors = {
      account_required: 'Connecte-toi pour retrouver tes crédits et activer un code.',
      code_invalid: 'Ce code est introuvable. Vérifie la saisie.',
      code_used: 'Tu as déjà activé ce code.',
      code_expired: 'Ce code a expiré.',
      code_used_up: 'Toutes les utilisations de ce code ont été prises.',
      plus_lifetime_already_active: 'Tu as déjà le Plus à vie.',
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
    }

    function date(timestamp) {
      return new Intl.DateTimeFormat('fr-FR', {dateStyle: 'long', timeZone: 'Europe/Paris'}).format(timestamp);
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
        const response = await fetch(PROXY + '/plus/' + action, {
          method: 'POST',
          headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token},
          body: JSON.stringify(data),
          signal: AbortSignal.timeout(10000),
        });
        const payload = await response.json();
        if (token !== getToken() || !dialog.open) return null;
        if (!response.ok) {
          if (response.status === 401) login.hidden = false;
          throw new Error(payload.error);
        }
        return payload;
      } catch (error) {
        if (token === getToken() && dialog.open) {
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
      login.hidden = true;
      status.textContent = 'Chargement de ton compte…';
      dialog.showModal();
      const data = await act('status');
      if (data) showState(data);
    });
    menu.insertBefore(link, document.getElementById('crV07Install'));
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
