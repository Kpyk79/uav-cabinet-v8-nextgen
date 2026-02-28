const CACHE_NAME = 'uav-v8-cache-v3';
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
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(ASSETS_TO_CACHE);
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

    // Skip API calls for default fetch-caching, handle them with Network-First logic
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
                .catch(() => {
                    return caches.match(event.request, { ignoreSearch: true });
                })
        );
        return;
    }

    // Navigation requests: handle extensionless URLs and fallback to offline.html
    if (event.request.mode === 'navigate') {
        event.respondWith(
            caches.match(event.request, { ignoreSearch: true }).then(response => {
                if (response) return response;

                // Fallback to .html if requested without extension
                const path = url.pathname === '/' ? '/index.html' : url.pathname + '.html';
                return caches.match(path, { ignoreSearch: true }).then(htmlResponse => {
                    return htmlResponse || fetch(event.request).catch(() => caches.match('/offline.html'));
                });
            })
        );
        return;
    }

    // Default: Cache-First for assets
    event.respondWith(
        caches.match(event.request, { ignoreSearch: true }).then(response => {
            return response || fetch(event.request);
        })
    );
});

// Sync logic (optional if using simple window.online listener, but good for robust PWA)
self.addEventListener('sync', event => {
    if (event.tag === 'sync-reports') {
        // This will be handled in the main script
    }
});
