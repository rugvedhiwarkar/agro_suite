/* Cash Desk POS extension — "Fast Journal" button on the Point of Sale screen.
 *
 * Opens the global Fast Journal dialog (payment / receipt / contra / journal,
 * shipped by fast_journal.bundle.js) without leaving the POS.
 *
 * Self-gating: the button renders only on sites where the Server Script API
 * `fast_voucher_config` exists and returns enabled=1 (staging-first contract).
 *
 * The earlier "Log Payment" button (expense / customer receipt / supplier
 * payment via the pos_* Server Scripts) was retired 2026-07-16 once Fast
 * Journal covered all three flows with party types: its four "POS Cash Desk *"
 * Server Scripts are disabled on both sites (kept as the rollback path) and
 * its client code was removed from this file.
 */

(function () {
	const PAGE = "point-of-sale";

	function fj_setup(wrapper) {
		fetch("/api/method/fast_voucher_config", { headers: { "X-Frappe-CSRF-Token": frappe.csrf_token } })
			.then((r) => (r.ok ? r.json() : null))
			.then((j) => {
				const cfg = j && j.message;
				if (cfg && cfg.enabled) fj_add_button(wrapper);
			})
			.catch(() => {});
	}

	function fj_add_button(wrapper) {
		if (wrapper.__fast_journal_ready) return;
		wrapper.__fast_journal_ready = true;
		const ensure = () => {
			const host =
				wrapper.page &&
				wrapper.page.wrapper &&
				wrapper.page.wrapper.find(".page-actions")[0];
			if (!host || host.querySelector(".fast-journal-btn")) return;
			const $btn = wrapper.page.add_button(
				__("Fast Journal"),
				() => {
					if (window.__fast_journal_open) window.__fast_journal_open();
				},
				{ btn_class: "btn-primary" }
			);
			if ($btn && $btn.addClass) $btn.addClass("fast-journal-btn");
		};
		ensure();
		const host = wrapper.page.wrapper.find(".page-actions")[0];
		if (host) {
			const obs = new MutationObserver(ensure);
			obs.observe(host, { childList: true, subtree: true });
			wrapper.__fast_journal_observer = obs;
		}
	}

	// run after ERPNext's own on_page_load builds the POS
	const page_wrapper = frappe.pages[PAGE];
	if (page_wrapper) {
		const orig = page_wrapper.on_page_load;
		page_wrapper.on_page_load = function (wrapper) {
			if (orig) orig.call(this, wrapper);
			fj_setup(wrapper);
		};
	}
})();
