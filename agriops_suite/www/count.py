import frappe


def get_context(context):
	"""Stock Count PWA shell (/count).

	A self-contained single-file app (inline CSS+JS, Marathi-first) for the
	counter's phone. Deliberately guest-viewable: with no stored pairing token
	and no desk session it shows only the pairing screen.

	Two authentication paths are supported (user decision 2026-07-23):
	  - a paired shop phone sends the counter's own API token;
	  - an office user opens /count inside their normal desk session, where the
	    cookie authenticates but a POST additionally needs a CSRF token. A
	    website page does not get one for free, so it is handed to the page
	    here. Guests get an empty string and never reach a POST.

	Served no_cache so edits reach phones on their next online open (the
	service worker layers stale-while-revalidate on top).
	"""
	context.no_cache = 1
	# standalone page — no website header/footer wrapper
	context.show_sidebar = 0
	context.csrf_token = ""
	if frappe.session.user and frappe.session.user != "Guest":
		try:
			context.csrf_token = frappe.sessions.get_csrf_token()
		except Exception:
			context.csrf_token = ""
	return context
