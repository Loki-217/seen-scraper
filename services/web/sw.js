// Service Worker for SeenFetch
// Intercepts and proxies requests to bypass CORS restrictions

const PROXY_API = 'http://localhost:8000/api/proxy/forward';
const PROXY_DOMAINS = ['unsplash.com', 'images.unsplash.com'];
const CACHE_NAME = 'seenfetch-cache-v1';

// ============ 1. Install Event ============
self.addEventListener('install', event => {
    console.log('[Service Worker] Installing...');
    // Force the waiting service worker to become the active service worker
    event.waitUntil(self.skipWaiting());
});

// ============ 2. Activate Event ============
self.addEventListener('activate', event => {
    console.log('[Service Worker] Activating...');
    event.waitUntil(
        // Clean up old caches
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(cacheName => cacheName !== CACHE_NAME)
                    .map(cacheName => caches.delete(cacheName))
            );
        }).then(() => {
            // Take control of all pages immediately
            return self.clients.claim();
        })
    );
});

// ============ 3. Fetch Event (Core Logic) ============
self.addEventListener('fetch', event => {
    const requestUrl = new URL(event.request.url);

    // Check if this request needs to be proxied
    const needsProxy = PROXY_DOMAINS.some(domain =>
        requestUrl.hostname.includes(domain)
    );

    if (needsProxy) {
        console.log('[Service Worker] Proxying request:', event.request.url);
        event.respondWith(proxyFetch(event.request));
    } else {
        // Let other requests pass through normally
        event.respondWith(fetch(event.request));
    }
});

// ============ 4. Proxy Function ============
async function proxyFetch(request) {
    try {
        // Build proxy request
        const proxyUrl = `${PROXY_API}?url=${encodeURIComponent(request.url)}`;

        // Forward the request through our proxy API
        const proxyRequest = new Request(proxyUrl, {
            method: 'GET',
            headers: {
                'Accept': request.headers.get('Accept') || '*/*',
            },
            mode: 'cors',
            credentials: 'omit'
        });

        const response = await fetch(proxyRequest);

        // Check if proxy request was successful
        if (!response.ok) {
            console.error('[Service Worker] Proxy request failed:', response.status, response.statusText);
            throw new Error(`Proxy request failed: ${response.status} ${response.statusText}`);
        }

        // Get the actual content from proxy response
        const responseData = await response.json();

        if (!responseData.success) {
            throw new Error(responseData.error || 'Proxy request failed');
        }

        // Decode base64 content if present
        let content;
        if (responseData.content_base64) {
            // Decode base64 to binary
            const binaryString = atob(responseData.content_base64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            content = bytes.buffer;
        } else if (responseData.content) {
            content = responseData.content;
        } else {
            throw new Error('No content in proxy response');
        }

        // Create response with CORS headers
        const headers = new Headers({
            'Content-Type': responseData.content_type || 'application/octet-stream',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': '*',
            'Cache-Control': 'public, max-age=31536000'
        });

        return new Response(content, {
            status: 200,
            statusText: 'OK',
            headers: headers
        });

    } catch (error) {
        console.error('[Service Worker] Proxy error:', error);

        // Return error response
        return new Response(
            JSON.stringify({
                error: error.message,
                url: request.url
            }),
            {
                status: 500,
                statusText: 'Proxy Error',
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                }
            }
        );
    }
}

// ============ Helper: Check if URL needs proxy ============
function shouldProxy(url) {
    try {
        const urlObj = new URL(url);
        return PROXY_DOMAINS.some(domain => urlObj.hostname.includes(domain));
    } catch (e) {
        return false;
    }
}

// ============ Message Handler (Optional) ============
self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[Service Worker] Loaded and ready');
