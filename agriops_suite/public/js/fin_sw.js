/* Financial Cockpit service worker — offline = last snapshot.
 *
 * Strategy: network-first for both the shell (/fin) and the read-only data
 * GETs, falling back to the last cached copy when the shop wifi drops. The
 * page stamps "as of" from the payload itself, so a stale-served snapshot is
 * visibly stale, never silently wrong. Bump VERSION to invalidate.
 */
var VERSION = "fin-v1";
var DATA_PREFIX = "/api/method/agriops_suite.fin_api.";
var CACHEABLE = ["snapshot", "acct", "tree", "bootstrap", "outstanding", "stock_balance"];

self.addEventListener("install", function (e) {
	self.skipWaiting();
});

self.addEventListener("activate", function (e) {
	e.waitUntil(
		caches.keys().then(function (keys) {
			return Promise.all(keys.filter(function (k) {
				return k !== VERSION;
			}).map(function (k) { return caches.delete(k); }));
		}).then(function () { return self.clients.claim(); })
	);
});

function cacheable(url) {
	var u = new URL(url);
	if (u.pathname === "/fin") return true;
	if (u.pathname.indexOf(DATA_PREFIX) === 0) {
		var method = u.pathname.slice(DATA_PREFIX.length);
		return CACHEABLE.some(function (m) { return method.indexOf(m) === 0; });
	}
	return false;
}

self.addEventListener("fetch", function (e) {
	if (e.request.method !== "GET" || !cacheable(e.request.url)) return;
	e.respondWith(
		fetch(e.request).then(function (resp) {
			if (resp && resp.ok) {
				var copy = resp.clone();
				caches.open(VERSION).then(function (c) { c.put(e.request, copy); });
			}
			return resp;
		}).catch(function () {
			return caches.match(e.request).then(function (hit) {
				return hit || new Response(
					JSON.stringify({ offline: true }),
					{ status: 503, headers: { "Content-Type": "application/json" } }
				);
			});
		})
	);
});
