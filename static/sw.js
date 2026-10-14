/**
 * Lokeriva.vercel.app — Service Worker with True Offline Support
 * Created by Xnuvers007
 */

// Build hash acak yang diinjeksikan secara otomatis oleh server (tanpa perlu diubah manual)
const BUILD_HASH = '{{SW_BUILD_HASH}}'.startsWith('{{')
  ? 'auto-random'
  : '{{SW_BUILD_HASH}}';

const STATIC_CACHE = `lokeriva-static-${BUILD_HASH}`;
const DATA_CACHE = `lokeriva-data-${BUILD_HASH}`;

// Aset inti yang wajib di-precache saat Service Worker dipasang
const CORE_ASSETS = [
  '/',
  '/docs',
  '/manifest.json',
  '/static/manifest.json',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/icons/icon-96.png',
  '/static/icons/icon-144.png',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/robots.txt',
  '/robots.txt'
];

// 1. INSTALL EVENT
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(async (cache) => {
      console.log('[Lokeriva SW] Caching core static assets for offline use...');
      // Precache setiap aset secara independen agar toleran terhadap kendala jaringan per file
      await Promise.all(
        CORE_ASSETS.map((url) =>
          cache.add(url).catch((err) => {
            console.warn(`[Lokeriva SW] Gagal precache ${url}:`, err);
          })
        )
      );

      // Precache CDN FontAwesome secara toleran
      try {
        await cache.add('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css');
      } catch (err) {
        console.warn('[Lokeriva SW] CDN cache skipped:', err);
      }
    })
  );
  self.skipWaiting();
});

// 2. ACTIVATE EVENT (Pembersihan cache versi usang)
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== DATA_CACHE)
          .map((key) => {
            console.log('[Lokeriva SW] Menghapus cache usang:', key);
            return caches.delete(key);
          })
      );
    })
  );
  self.clients.claim();
});

// 3. FETCH EVENT
self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Hanya proses metode GET untuk caching
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);

  // A. Endpoints Ekspor File & Refresh (Memerlukan jaringan aktif)
  if (url.pathname.startsWith('/export/') || url.pathname === '/api/refresh') {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(
          'Fitur ekspor file dan pembaruan data memerlukan koneksi internet aktif.',
          { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } }
        );
      })
    );
    return;
  }

  // B. REST API Endpoints (/api/jobs, /api/stats, /api/sources, /api/openapi.json)
  // Strategi: Network First dengan Fallback ke Cache Data Tersimpan
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(DATA_CACHE).then((cache) => {
              cache.put(request, clone);
            });
          }
          return networkResponse;
        })
        .catch(async () => {
          // 1. Cari respons persis di DATA_CACHE
          const cached = await caches.match(request);
          if (cached) {
            return cached;
          }

          // 2. Jika filter spesifik belum ada di cache, cari data /api/jobs apapun yang pernah disimpan
          if (url.pathname === '/api/jobs') {
            const dataCache = await caches.open(DATA_CACHE);
            const cachedRequests = await dataCache.keys();
            const jobReq = cachedRequests.find((r) => r.url.includes('/api/jobs'));
            if (jobReq) {
              const fallbackResponse = await dataCache.match(jobReq);
              if (fallbackResponse) {
                return fallbackResponse;
              }
            }
          }

          // 3. Fallback respons offline JSON terstruktur
          return new Response(
            JSON.stringify({
              status: 'offline',
              is_offline: true,
              data: [],
              pagination: { total_items: 0, total_pages: 0, current_page: 1 },
              message: 'Mode Offline: Anda sedang tidak terhubung ke internet. Menampilkan data tersimpan di perangkat.'
            }),
            { headers: { 'Content-Type': 'application/json' } }
          );
        })
    );
    return;
  }

  // C. Navigasi Halaman HTML (Page Navigation untuk App Shell PWA)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const clone = networkResponse.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        })
        .catch(async () => {
          // Sajikan halaman yang sesuai dari cache
          const cached = await caches.match(request);
          if (cached) return cached;
          // Fallback ke halaman root '/'
          return caches.match('/');
        })
    );
    return;
  }

  // D. Asset Statis (CSS, JS, Gambar, Ikon, Web Fonts)
  // Strategi: Cache First dengan Network Fallback & Runtime Caching
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(request)
        .then((networkResponse) => {
          if (
            networkResponse &&
            (networkResponse.status === 200 || networkResponse.type === 'opaque')
          ) {
            const clone = networkResponse.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, clone));
          }
          return networkResponse;
        })
        .catch(() => {
          // Jika gambar gagal dimuat saat offline, fallback ke ikon aplikasi
          if (request.destination === 'image') {
            return caches.match('/static/icons/icon-192.png');
          }
          return null;
        });
    })
  );
});
