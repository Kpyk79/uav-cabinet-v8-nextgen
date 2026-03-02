const CACHE_NAME = 'uav-v8-cache-v10.1';
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
    'https://cdn.tailwindcss.com',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            // Using a more resilient approach: cache what we can
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

    // 1. API - Network first, then fallback to cache
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    const clonedResponse = response.clone();
                    if (url.pathname === '/api/get_options' || url.pathname === '/api/get_unit_drones') {
                        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clonedResponse));
                    }
                    return response;
                })
                .catch(() => caches.match(event.request, { ignoreSearch: true }))
        );
        return;
    }

    // 2. Navigation - Cache first, with extensionless & manual fallback
    if (event.request.mode === 'navigate' || (event.request.method === 'GET' && event.request.headers.get('accept').includes('text/html'))) {
        event.respondWith(
            caches.match(event.request, { ignoreSearch: true }).then(cacheResponse => {
                if (cacheResponse) return cacheResponse;

                // Try common extensions
                const possiblePaths = [
                    url.pathname + '.html',
                    url.pathname === '/' ? '/index.html' : url.pathname
                ];

                return (async () => {
                    for (const path of possiblePaths) {
                        const hit = await caches.match(path, { ignoreSearch: true });
                        if (hit) return hit;
                    }

                    try {
                        return await fetch(event.request);
                    } catch (e) {
                        return caches.match('/offline.html');
                    }
                })();
            })
        );
        return;
    }

    // 3. Static Assets - Cache first
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

