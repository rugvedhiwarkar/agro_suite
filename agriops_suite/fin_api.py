"""Financial Cockpit (/fin) — read-only statement API, Phase 1.

Two endpoints:

- bootstrap: chart metadata (book span, fiscal years, bucket names)
- snapshot:  day-wise net movement per balance-sheet bucket and per P&L
  leaf account, for the whole life of the books, in one payload

The heavy lifting the cockpit mock did client-side from a 13 MB REST pull
happens here as two GROUP BYs over `tabGL Entry`, next to the data. The
payload is the same shape the mock embeds (financial-cockpit repo,
data/dist/v3daily.json), so the front end is a drop-in: the page builds
prefix-sum arrays once and answers any day-range query locally.

Read-only by construction: SELECTs only, role-guarded, and no client input
reaches SQL — the only dynamic pieces are account-tree lft/rgt ranges the
server resolves itself. Cached a few minutes keyed on the last GL Entry
modification, because the bench sits on a shared plan and every open of the
page can reuse the same snapshot.

Period Closing Voucher rows are excluded from the three P&L buckets and the
P&L leaves (mirroring the standard statements — otherwise closed years sum
to zero), but stay in the equity bucket where the closing genuinely lands.
"""

import json

import frappe

ROLES = ("System Manager", "Accounts Manager")
COMPANY = "Vijay Agro Centre"
PCV = "Period Closing Voucher"
CACHE_SECONDS = 600

# bucket -> (root account names without company abbr, sign)
# sign +1 = debit-nature stored positive (assets/expenses),
# sign -1 = credit-nature stored positive (income/liabilities/equity)
BUCKETS = {
	"inc": (["Income"], -1),
	"dexp": (["Direct Expenses"], 1),
	"iexp": (["Indirect Expenses"], 1),
	"ar": (["Accounts Receivable"], 1),
	"stock": (["Stock Assets"], 1),
	"cash": (["Bank Accounts", "Cash In Hand", "Cash-in-hand"], 1),
	"depo": (["Securities & Deposits (Asset)"], 1),
	"tax": (["Tax Assets"], 1),
	"fixed": (["Fixed Assets"], 1),
	"susp": (["Suspense Account", "Temporary Accounts"], 1),
	"ap": (["Accounts Payable"], -1),
	"duty": (["Duties and Taxes"], -1),
	"sliab": (["Stock Liabilities"], -1),
	"eq": (["Equity"], -1),
}
PL_BUCKETS = ("inc", "dexp", "iexp")


def _guard():
	frappe.only_for(ROLES)


def _abbr():
	return frappe.get_cached_value("Company", COMPANY, "abbr")


def _ranges():
	"""bucket -> ([(lft, rgt), ...], sign), resolved from the live tree."""
	abbr = _abbr()
	wanted = [f"{root} - {abbr}" for roots, _ in BUCKETS.values() for root in roots]
	rows = frappe.get_all(
		"Account",
		filters={"name": ("in", wanted), "company": COMPANY},
		fields=["name", "lft", "rgt"],
	)
	by_name = {r.name: r for r in rows}
	out = {}
	for bucket, (roots, sign) in BUCKETS.items():
		rr = []
		for root in roots:
			acc = by_name.get(f"{root} - {abbr}")
			if acc:
				rr.append((acc.lft, acc.rgt))
		out[bucket] = (rr, sign)
	return out


def _gl_stamp():
	row = frappe.db.sql(
		"select count(*), max(modified) from `tabGL Entry` where company = %s",
		(COMPANY,),
	)[0]
	return f"{row[0]}:{row[1]}"


@frappe.whitelist(methods=["GET"])
def bootstrap():
	_guard()
	span = frappe.db.sql(
		"""select min(posting_date), max(posting_date)
		from `tabGL Entry` where company = %s and is_cancelled = 0""",
		(COMPANY,),
	)[0]
	return {
		"company": COMPANY,
		"d0": str(span[0]),
		"asof": str(span[1]),
		"today": frappe.utils.today(),
		"buckets": list(BUCKETS),
		"fiscal_years": [
			fy.name
			for fy in frappe.get_all(
				"Fiscal Year", fields=["name"], order_by="year_start_date"
			)
		],
	}


@frappe.whitelist(methods=["GET"])
def snapshot():
	_guard()
	cache_key = f"agriops_fin_snapshot:{COMPANY}:{_gl_stamp()}"
	cached = frappe.cache().get_value(cache_key)
	if cached:
		out = json.loads(cached)
		out["from_cache"] = True
		return out

	ranges = _ranges()

	# --- pass 1: one row per posting day, one column per bucket ---
	col_sql, params = [], []
	for bucket, (rr, sign) in ranges.items():
		if not rr:
			col_sql.append(f"0 as `{bucket}`")
			continue
		cond = "(" + " or ".join(["a.lft between %s and %s"] * len(rr)) + ")"
		pcv_guard = ""
		if bucket in PL_BUCKETS:
			pcv_guard = "gl.voucher_type != %s and "
			params.append(PCV)
		col_sql.append(
			f"round(sum(case when {pcv_guard}{cond} "
			f"then ({sign}) * (gl.debit - gl.credit) else 0 end)) as `{bucket}`"
		)
		for lft, rgt in rr:
			params.extend([lft, rgt])

	day_rows = frappe.db.sql(
		f"""select gl.posting_date as d, {", ".join(col_sql)}
		from `tabGL Entry` gl
		join `tabAccount` a on a.name = gl.account
		where gl.company = %s and gl.is_cancelled = 0
		group by gl.posting_date
		order by gl.posting_date""",
		params + [COMPANY],
		as_dict=True,
	)
	if not day_rows:
		frappe.throw("No GL entries found for {0}".format(COMPANY))

	d0 = day_rows[0].d
	asof = day_rows[-1].d
	nd = (asof - d0).days + 1
	daily = {b: {} for b in BUCKETS}
	for row in day_rows:
		idx = str((row.d - d0).days)
		for b in BUCKETS:
			v = int(row[b] or 0)
			if v:
				daily[b][idx] = v

	# --- pass 2: P&L leaves, day-wise (drives lines / drill / overheads) ---
	pl_rr = [r for b in PL_BUCKETS for r in ranges[b][0]]
	cond = "(" + " or ".join(["a.lft between %s and %s"] * len(pl_rr)) + ")"
	lp = []
	for lft, rgt in pl_rr:
		lp.extend([lft, rgt])
	leaf_rows = frappe.db.sql(
		f"""select gl.posting_date as d, gl.account as acct, a.root_type as rt,
			round(sum(gl.debit - gl.credit)) as net
		from `tabGL Entry` gl
		join `tabAccount` a on a.name = gl.account
		where gl.company = %s and gl.is_cancelled = 0
			and gl.voucher_type != %s and {cond}
		group by gl.posting_date, gl.account""",
		[COMPANY, PCV] + lp,
		as_dict=True,
	)
	leaf = {}
	for row in leaf_rows:
		v = int(row.net or 0)
		if row.rt == "Income":
			v = -v
		if v:
			leaf.setdefault(row.acct, {})[str((row.d - d0).days)] = v

	# --- self-audit: whole-book debits must equal credits, to the rupee ---
	tot = frappe.db.sql(
		"""select round(sum(debit), 2), round(sum(credit), 2)
		from `tabGL Entry` where company = %s and is_cancelled = 0""",
		(COMPANY,),
	)[0]
	dr, cr = float(tot[0] or 0), float(tot[1] or 0)

	out = {
		"company": COMPANY,
		"d0": str(d0),
		"asof": str(asof),
		"nd": nd,
		"daily": daily,
		"leaf": leaf,
		"audit": {"dr": dr, "cr": cr, "balanced": abs(dr - cr) < 1},
		"generated": frappe.utils.now(),
		"from_cache": False,
	}
	frappe.cache().set_value(cache_key, json.dumps(out), expires_in_sec=CACHE_SECONDS)
	return out
