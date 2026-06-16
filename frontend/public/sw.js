// Service Worker for PWA support
const CACHE_NAME = 'ai-healthy-v1'
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

  // Skip API calls - always fetch from network
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(JSON.stringify({ error: 'Network error' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      })
    )
    return
  }

  // Cache-first strategy for assets
  event.respondWith(
    caches.match(request).then((response) => {
      return (
        response ||
        fetch(request)
          .then((fetchResponse) => {
            // Cache successful responses
            if (fetchResponse.status === 200) {
              const responseToCache = fetchResponse.clone()
              caches.open(CACHE_NAME).then((cache) => {
                cache.put(request, responseToCache)
              })
            }
            return fetchResponse
          })
          .catch(() => {
            // Return a basic offline page if available
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
  )
})

// Handle messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})
