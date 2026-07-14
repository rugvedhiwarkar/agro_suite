import frappe

# Standard ERPNext reports we run LIVE (prepared_report=0) so Reload shows
# CURRENT data instead of a cached "generated X ago" snapshot with a Rebuild
# step. ERPNext ships some of these as prepared/background reports; a core
# upgrade re-imports the standard report JSON and would flip them back, so we
# re-assert after every migrate. Idempotent and guarded for fresh sites.
#
# To make another report live, just add its exact name here.
LIVE_REPORTS = ["General Ledger"]


def ensure_live_reports():
    """after_migrate hook: force LIVE_REPORTS to prepared_report=0."""
    for name in LIVE_REPORTS:
        if frappe.db.exists("Report", name) and frappe.db.get_value("Report", name, "prepared_report"):
            frappe.db.set_value("Report", name, "prepared_report", 0)
            frappe.logger().info("agriops_suite: Report %r set live (prepared_report=0)" % name)
