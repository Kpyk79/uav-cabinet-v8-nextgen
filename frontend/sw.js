const CACHE_NAME = 'uav-v8-cache-v11.0';
const ASSETS_TO_CACHE = [
    '/',
    '/index.html',
    '/report.html',
    '/dashboard.html',
    '/analytics.html',
    '/admin.html',
    '/handbook.html',
    '/support.html',
    '/request.html',
    '/admin_analytics.html',
    '/fleet_management.html',
    '/offline.html',
    '/libs/db.js',
    '/icon.png',
    '/manifest.json',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return Promise.allSettled(ASSETS_TO_CACHE.map(url => cache.add(url)));
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // 1. API - Network first, no caching of POST requests
    if (url.pathname.startsWith('/api/')) {
        // Don't intercept POST method (e.g. generate_docx) - let it pass through
        if (event.request.method !== 'GET') return;

        event.respondWith(
            fetch(event.request)
                .then(response => {
                    // Only cache lightweight option endpoints
                    if (url.pathname === '/api/get_options' || url.pathname === '/api/get_unit_drones') {
                        const clonedResponse = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clonedResponse));
                    }
                    return response;
                })
                .catch(() => caches.match(event.request, { ignoreSearch: true }))
        );
        return;
    }

    // 2. Navigation (HTML pages) - Network first, cache as offline fallback
    // Use event.request.mode === 'navigate' ONLY, to avoid crashes on null accept header
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    if (response.ok) {
                        const cloned = response.clone();
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
                    }
                    return response;
                })
                .catch(() => {
                    return caches.match(event.request, { ignoreSearch: true })
                        .then(cached => cached || caches.match('/offline.html'));
                })
        );
        return;
    }

    // 3. Static Assets (CSS, JS, fonts, images) - Cache first, network fallback
    event.respondWith(
        caches.match(event.request, { ignoreSearch: true }).then(response => {
            return response || fetch(event.request);
        })
    );
});

self.addEventListener('sync', event => {
    if (event.tag === 'sync-reports') {
        // Handled in main script
    }
});
