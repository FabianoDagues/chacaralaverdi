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
