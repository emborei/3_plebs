const CACHE = 'plebs-v2';
const ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-180.png',
  'https://fonts.googleapis.com/css2?family=Permanent+Marker&family=Bebas+Neue&family=Russo+One&family=Press+Start+2P&family=Teko:wght@500;700&display=swap'
];

self.addEventListener('install', e=>{
  e.waitUntil(
    caches.open(CACHE).then(c=> c.addAll(ASSETS).catch(()=>{})).then(()=> self.skipWaiting())
  );
});
self.addEventListener('activate', e=>{
  e.waitUntil(
    caches.keys().then(keys=> Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=> self.clients.claim())
  );
});
self.addEventListener('fetch', e=>{
  const req = e.request;
  // only cache GET
  if(req.method !== 'GET') return;
  // bypass chrome extensions
  if(req.url.startsWith('chrome-extension')) return;
  e.respondWith(
    caches.match(req).then(cached=>{
      const fetchPromise = fetch(req).then(res=>{
        // update cache for same-origin
        if(res.ok && req.url.startsWith(self.location.origin)){
          const clone = res.clone();
          caches.open(CACHE).then(c=> c.put(req, clone));
        }
        return res;
      }).catch(()=> cached);
      return cached || fetchPromise;
    })
  );
});
