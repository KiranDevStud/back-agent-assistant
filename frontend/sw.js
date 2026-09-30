// PattuBook Progressive Web App Service Worker
const CACHE_NAME = 'pattubook-v2';
const STATIC_ASSETS = [
  '/',
  '/login',
  '/manifest.json',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/auth.js',
  '/static/js/briefing.js',
  '/static/js/invoices.js',
  '/static/js/mis.js',
  '/static/js/comms.js',
  '/static/js/compliance.js',
  '/static/js/assistant.js',
  '/static/js/integrations.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png'
];

// Install: Cache critical static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Cache addAll partial failure:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean up older cache versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Network-first for APIs, Cache-first / Stale-while-revalidate for static files
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 1. API Requests: Always fetch from network (never serve stale financial/invoice data from cache)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch((err) => {
        return new Response(
          JSON.stringify({ error: 'You are currently offline. Please check your internet connection.' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      })
    );
    return;
  }

  // 2. Static Assets & Pages: Stale-While-Revalidate
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});

// Push Notifications: Support background notifications (e.g. Morning Briefing & GST deadlines)
self.addEventListener('push', (event) => {
  let data = { title: 'PattuBook Morning Briefing', body: 'Your daily back-office summary is ready.', url: '/#briefing' };
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) {
    data.body = event.data.text();
  }

  const options = {
    body: data.body,
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/#briefing'
    },
    actions: [
      { action: 'open', title: 'Open Briefing' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification Click: Open app window to the requested tab
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
