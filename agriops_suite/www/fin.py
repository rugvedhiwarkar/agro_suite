import frappe


def get_context(context):
	"""Financial Cockpit shell (/fin) — Phase 1: the P&L page, live.

	Unlike /slip this is owner-facing: guests bounce to login, and the data
	endpoints (agriops_suite.fin_api.*) are role-guarded besides. no_cache so
	shell edits reach the browser on the next open — there is deliberately no
	service worker in Phase 1; offline snapshots come with the PWA phase.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/fin"
		raise frappe.Redirect
	context.no_cache = 1
	context.show_sidebar = 0
	return context
