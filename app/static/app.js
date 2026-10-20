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


// V4.1 - seletor seguro de quantidade do pedido
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

    const setValue = (value) => {
      const n = Math.max(0, Math.trunc(Number(value) || 0));
      input.value = String(n);
      input.dispatchEvent(new Event('change', { bubbles: true }));
    };

    stepper.querySelectorAll('[data-qty-action]').forEach((button) => {
      button.addEventListener('click', () => {
        const current = toInt(input.value) ?? 0;
        const delta = button.dataset.qtyAction === 'plus' ? 1 : -1;
        setValue(Math.max(0, current + delta));
        input.focus({ preventScroll: true });
        input.select();
      });
    });

    // Ao tocar/clicar, seleciona todo o valor. Assim 0 + digitar 5 = 5, nunca 50.
    input.addEventListener('focus', () => input.select());
    input.addEventListener('click', () => input.select());

    input.addEventListener('input', () => {
      const n = toInt(input.value);
      input.value = n === null ? '' : String(n);
    });

    input.addEventListener('blur', () => {
      const n = toInt(input.value);
      input.value = String(n ?? 0);
    });
  });
})();
