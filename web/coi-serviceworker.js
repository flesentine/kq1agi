/*
 * Cross-origin isolation service worker for the kq1agi GitHub Pages build.
 * GitHub Pages cannot set COOP/COEP response headers itself, so this worker
 * adds them to same-site responses before AGILE starts its SharedArrayBuffer
 * based interpreter worker.
 */

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', event => {
  const request = event.request;

  // Chrome can emit this request shape for cached subresources. Passing it to
  // fetch() from a service worker throws, so leave it alone.
  if (request.cache === 'only-if-cached' && request.mode !== 'same-origin') {
    return;
  }

  event.respondWith(
    fetch(request).then(response => {
      // Opaque responses cannot be reconstructed with custom headers.
      if (response.status === 0) {
        return response;
      }

      const headers = new Headers(response.headers);
      headers.set('Cross-Origin-Opener-Policy', 'same-origin');
      headers.set('Cross-Origin-Embedder-Policy', 'require-corp');
      headers.set('Cross-Origin-Resource-Policy', 'cross-origin');

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers
      });
    }).catch(error => {
      console.error('kq1agi service worker fetch failed', error);
      return Response.error();
    })
  );
});
