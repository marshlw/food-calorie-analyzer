// Service Worker for PWA support
const CACHE_NAME = 'ai-healthy-v2'
const urlsToCache = [
  '/',
  '/index.html',
  '/manifest.json',
]

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache).catch(() => {
        // Ignore errors for offline-first PWA
      })
    })
  )
  self.skipWaiting()
})

// Activate event
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName)
          }
        })
      )
    })
  )
  self.clients.claim()
})

// Fetch event
self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return
  }

  // Skip API calls - let the browser handle them natively so that real
  // network errors propagate to the HTTP client instead of a synthetic 503.
  if (url.pathname.startsWith('/api/')) {
    return
  }

  // Network-first: всегда пытаемся взять свежую версию из сети, кэш — только
  // фолбэк офлайн. Это исключает «залипание» старого бандла после деплоя.
  event.respondWith(
    fetch(request)
      .then((fetchResponse) => {
        if (fetchResponse.status === 200) {
          const responseToCache = fetchResponse.clone()
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache)
          })
        }
        return fetchResponse
      })
      .catch(() => {
        return caches.match(request).then((cachedResponse) => {
          return (
            cachedResponse ||
            new Response('Offline - please check your connection', {
              status: 503,
              headers: { 'Content-Type': 'text/plain' },
            })
          )
        })
      })
  )
})

// Handle messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
