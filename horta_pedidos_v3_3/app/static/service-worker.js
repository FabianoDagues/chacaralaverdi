const CACHE='horta-static-v1';
const ASSETS=['/static/style.css','/static/app.js','/static/icons/icon-192.png','/static/icons/icon-512.png'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;if(new URL(e.request.url).pathname.startsWith('/static/')){e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));}});
