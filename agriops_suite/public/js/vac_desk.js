// Desk breadcrumb "home" -> the user's default workspace.
//
// frappe v16 hardcodes the breadcrumb home icon to "/desk" (breadcrumbs.js
// append_breadcrumb_element("/desk", icon("home"))), which lands on the tile
// desktop. VAC users' home is the VAC hub workspace, carried per-user in
// User.default_workspace (already in boot). Self-gating like the other
// includes: when no default_workspace is set for the user (e.g. production
// before the VAC hub promotion), this never intercepts and stock behaviour
// is untouched.
//
// Capture-phase listener so we win against the SPA router's own anchor
// handler; full navigation keeps it correct on every page type.
(function () {
	function home_route() {
		var ws = frappe.boot && frappe.boot.user && frappe.boot.user.default_workspace;
		if (!ws) return null;
		var label = ws.title || ws.name;
		if (!label) return null;
		return "/desk/" + frappe.router.slug(label);
	}

	document.addEventListener(
		"click",
		function (e) {
			var a = e.target && e.target.closest && e.target.closest('a[href="/desk"]');
			if (!a) return;
			var route = home_route();
			if (!route) return;
			e.preventDefault();
			e.stopPropagation();
			window.location.assign(route);
		},
		true
	);
})();
