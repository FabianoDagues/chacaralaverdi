if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js').catch(() => {}));
}
let deferredPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; document.querySelectorAll('[data-install-app]').forEach(b => b.hidden = false); });
window.installHortaApp = async function(){ if(!deferredPrompt) return; deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt = null; };

// Menu lateral responsivo
(function(){
  const toggles = document.querySelectorAll('[data-sidebar-toggle]');
  const overlay = document.querySelector('[data-sidebar-overlay]');
  const close = () => {
    document.body.classList.remove('sidebar-open');
    toggles.forEach(b => b.setAttribute('aria-expanded','false'));
  };
  const toggle = () => {
    const willOpen = !document.body.classList.contains('sidebar-open');
    document.body.classList.toggle('sidebar-open', willOpen);
    toggles.forEach(b => b.setAttribute('aria-expanded', willOpen ? 'true' : 'false'));
  };
  toggles.forEach(b => b.addEventListener('click', toggle));
  if (overlay) overlay.addEventListener('click', close);
  document.addEventListener('keydown', e => { if(e.key === 'Escape') close(); });
  document.querySelectorAll('.sidebar-nav a').forEach(a => a.addEventListener('click', () => { if(window.innerWidth <= 900) close(); }));
})();


// V4.6 - seletor seguro de quantidade com saldo de estoque em tempo real
(function(){
  const toInt = (value) => {
    const clean = String(value ?? '').replace(/\D/g, '');
    if (!clean) return null;
    const n = Number.parseInt(clean, 10);
    return Number.isFinite(n) ? Math.max(0, n) : 0;
  };

  document.querySelectorAll('[data-qty-stepper]').forEach((stepper) => {
    const input = stepper.querySelector('.qty-step-input');
    if (!input || input.disabled) return;

    const hasMax = stepper.dataset.maxQty !== undefined;
    const maxQty = hasMax ? Math.max(0, Number.parseInt(stepper.dataset.maxQty || '0', 10) || 0) : null;
    const unit = stepper.dataset.unit || 'un';
    const limitMessage = stepper.parentElement?.querySelector('[data-qty-limit-message]');
    const plusButton = stepper.querySelector('[data-qty-action="plus"]');

    const showLimit = () => {
      if (!hasMax || !limitMessage) return;
      limitMessage.textContent = `Este é o estoque máximo disponível: ${maxQty} ${unit}.`;
      limitMessage.classList.add('show');
    };
    const hideLimit = () => {
      if (!limitMessage) return;
      limitMessage.textContent = '';
      limitMessage.classList.remove('show');
    };
    const syncPlusState = (value) => {
      if (!plusButton || !hasMax) return;
      plusButton.setAttribute('aria-disabled', value >= maxQty ? 'true' : 'false');
    };
    const setValue = (value, notifyAtMax = false) => {
      let n = Math.max(0, Math.trunc(Number(value) || 0));
      if (hasMax && n >= maxQty) {
        n = maxQty;
        if (notifyAtMax) showLimit();
      } else {
        hideLimit();
      }
      input.value = String(n);
      syncPlusState(n);
      input.dispatchEvent(new Event('change', { bubbles: true }));
    };

    stepper.querySelectorAll('[data-qty-action]').forEach((button) => {
      // Botões nunca focam o campo de quantidade; o teclado abre só ao tocar no número.
      button.addEventListener('pointerdown', (event) => {
        event.preventDefault();
        if (document.activeElement === input) input.blur();
      });
      button.addEventListener('click', (event) => {
        event.preventDefault();
        if (document.activeElement === input) input.blur();
        const current = toInt(input.value) ?? 0;
        if (button.dataset.qtyAction === 'plus') {
          if (hasMax && current >= maxQty) {
            showLimit();
            syncPlusState(current);
            return;
          }
          const next = current + 1;
          setValue(next, hasMax && next >= maxQty);
        } else {
          setValue(Math.max(0, current - 1), false);
        }
      });
    });

    // Ao tocar/clicar, seleciona todo o valor. Assim 0 + digitar 5 = 5, nunca 50.
    input.addEventListener('focus', () => input.select());
    input.addEventListener('click', () => input.select());

    input.addEventListener('input', () => {
      const n = toInt(input.value);
      if (n === null) {
        input.value = '';
        hideLimit();
        syncPlusState(0);
        return;
      }
      if (hasMax && n >= maxQty) {
        input.value = String(maxQty);
        showLimit();
        syncPlusState(maxQty);
      } else {
        input.value = String(n);
        hideLimit();
        syncPlusState(n);
      }
    });

    input.addEventListener('blur', () => {
      const n = toInt(input.value);
      setValue(n ?? 0, false);
    });

    syncPlusState(toInt(input.value) ?? 0);
  });
})();
