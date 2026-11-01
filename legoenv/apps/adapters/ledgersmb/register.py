"""register.py — attach the LedgerSMB (double-entry bookkeeping / ERP-accounting) spec to packlib
WITHOUT editing packlib.py. LedgerSMB is the stand-in for QuickBooks/Sage/Xero accounting tasks.

    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs3.ledgersmb.register import *     # adds ledgersmb to SERVER/PFX/CONTENT/NOTES/LOGIN + obs hook + seed helpers

The base (pack/base_specs/ledgersmb.spec.json, patched from env_compiler's v1 repo_spec) holds the persona
account (User id 1, signed in with sign_in(username, password)), a chart of accounts, parts & currencies.
Content entities are empty — seed them with the helpers below (asset_register / ap_vouchers / checkpoints)
or W.seed(app, entity, rows).
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, LOGIN, OBS_CAP, F, AND, OR, SEL, CNT

NEW_SERVER = {"ledgersmb": "accounting"}

# entities that hold task content (seeded per pack; listed in packlib CONTENT)
NEW_CONTENT = {"ledgersmb": ["AssetItem", "AccountHeading", "Account", "Part", "Batch", "Reconciliation", "AccTrans", "Transaction", "Jcitems", "Budget"]}

NEW_NOTES = {
    "ledgersmb": "{p}__ is the double-entry accounting system (QuickBooks/Sage/Xero-style): sign in with {p}__sign_in(username, password). "
                 "The chart of accounts is Account: account_get(id) reads one account; account_save(accno, description, category, heading, ...) "
                 "creates or updates one; goods_list searches the parts (services/goods) catalogue. "
                 "assetitem_search(in_tag, in_description, in_purchase_date, ...) lists fixed assets (NULL filters are ignored); "
                 "assetitem_save(in_tag, in_description, in_purchase_value, in_asset_account_id, ...) creates or updates one. "
                 "batch_search searches posting batches; batch_save(batch_number, batch_class, batch_date, description) starts one and "
                 "batch_post(in_batch_id) posts (approves) its transactions. country_list lists countries; country_create(name, short_name) adds one. "
                 "reconciliation_create(account_id, end_date) opens a bank reconciliation. "
                 "menu_generate lists the ERP menu; language_list lists languages. All reads return full rows; filter the larger lists yourself."
}
NEW_LOGIN = {"ledgersmb": ("sign_in", "username")}
for _a in NEW_SERVER:
    SERVER.setdefault(_a, NEW_SERVER[_a]); PFX.setdefault(_a, _a)
    CONTENT.setdefault(_a, NEW_CONTENT[_a]); NOTES.setdefault(_a, NEW_NOTES[_a])
packlib.LOGIN.update(NEW_LOGIN)   # simulate()/login() sign into ledgersmb too

# ───────── whole-list reads the agent will make on ledgersmb (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    if "ledgersmb" not in self.apps: return rep, bad
    env = runtime.Env(self.world)
    t, col = LOGIN["ledgersmb"]; env.call(NS("ledgersmb", t), {col: self.persona, "password": self.password})
    def rd(tool, args): return len(json.dumps(env.call(NS("ledgersmb", tool), args), ensure_ascii=False, default=str))
    rep["ledgersmb goods_list"] = rd("goods_list", {})
    rep["ledgersmb assetitem_search"] = rd("assetitem_search", {})
    rep["ledgersmb country_list"] = rd("country_list", {})
    rep["ledgersmb menu_generate"] = rd("menu_generate", {})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers ─────────
TS = "2026-01-01T00:00:00"
def _ss(W, app): return W.spec[app]["seed_state"]
def _bind(W, app, ent, src, n):
    if src: W.bindings[NS(app, ent)] = {"dataset": src, "rows": n}

def asset_register(W, rows, src=None):
    """ledgersmb fixed-asset register (content rows). rows = [{id, tag, description, purchase_date, purchase_value,
    usable_life, salvage_value, asset_account_id, dep_account_id, exp_account_id}]. The persona is User 1."""
    ss = _ss(W, "ledgersmb")
    for a in rows:
        ss.setdefault("AssetItem", []).append({
            "id": a["id"], "tag": a.get("tag", f"ASSET-{a['id']}"), "description": a.get("description"),
            "purchase_date": a.get("purchase_date", TS), "start_depreciation": a.get("purchase_date", TS),
            "purchase_value": a.get("purchase_value", 0), "salvage_value": a.get("salvage_value", 0),
            "usable_life": a.get("usable_life", 5), "asset_account_id": a.get("asset_account_id"),
            "dep_account_id": a.get("dep_account_id"), "exp_account_id": a.get("exp_account_id"), "obsolete_by": None})
    _bind(W, "ledgersmb", "AssetItem", src, len(rows))

def ap_vouchers(W, rows, src=None):
    """ledgersmb AP vouchers = an unapproved batch whose lines are the content rows.
    rows = [{trans_id, memo, reference, amount, account_id?, transdate?}] -> one Batch + one Transaction per row + AccTrans entries.
    Returns the batch id (the agent posts it with batch_post(in_batch_id=...))."""
    ss = _ss(W, "ledgersmb")
    bid = max([b["id"] for b in ss.get("Batch", [])] + [0]) + 1
    ss.setdefault("Batch", []).append({"id": bid, "batch_class_id": 1, "control_code": f"AP-{bid}", "description": f"AP vouchers {bid}",
                                       "default_date": TS, "approved_on": None, "approved_by": None, "created_by": 1, "created_on": TS})
    for r in rows:
        ss.setdefault("Transaction", []).append({"id": r["trans_id"], "table_name": "ap", "batch_id": bid, "approved": False,
                                                 "transdate": r.get("transdate", TS), "reference": r.get("reference"),
                                                 "description": r.get("memo"), "trans_type_code": "ap", "locked_by": None})
        ss.setdefault("AccTrans", []).append({"entry_id": r["trans_id"], "trans_id": r["trans_id"], "chart_id": r.get("account_id", 3),
                                              "amount": r.get("amount", 0), "amount_bc": r.get("amount", 0), "amount_tc": r.get("amount", 0),
                                              "curr": "USD", "transdate": r.get("transdate", TS), "memo": r.get("memo"), "approved": False})
    _bind(W, "ledgersmb", "Transaction", src, len(rows))
    return bid

def checkpoints(W, rows, src=None):
    """ledgersmb closed accounting periods. rows = [{account_id, end_date, amount}] -> AccountCheckpoint rows
    (so books_reopen / yearend_generate work)."""
    ss = _ss(W, "ledgersmb")
    for r in rows:
        ss.setdefault("AccountCheckpoint", []).append({"end_date": r["end_date"], "account_id": r["account_id"],
                                                       "amount": r.get("amount", 0), "id": len(ss.get("AccountCheckpoint", [])) + 1,
                                                       "debits": 0, "credits": 0, "amount_bc": 0, "amount_tc": 0})
    _bind(W, "ledgersmb", "AccountCheckpoint", src, len(rows))

def add_users(W, rows):
    """ledgersmb colleagues besides the persona (User 1). rows = [{id, username, password?, entity_id?}]. Passwords default to pw-<id>."""
    for r in rows:
        row = dict(r); row.setdefault("password", f"pw-{r['id']}"); row.setdefault("entity_id", r["id"]); row.setdefault("notify_password", "7 days")
        _ss(W, "ledgersmb")["User"].append(row)
    _bind(W, "ledgersmb", "User", None, len(rows))

def smoke_seed(W):
    """seed >= 3 realistic content rows + one policy text in a carrier field (Setting.value under the `notes_field`
    carrier); return gold steps that perform one write and >= 3 contract predicates (incl. one negative)."""
    ss = _ss(W, "ledgersmb")
    # the chart of accounts is content but a seeded Account is needed for the reconciliation write below
    ss.setdefault("Account", []).extend([
        {"id": 1, "accno": "1000", "description": "Cash", "is_temp": False, "category": "A", "heading": 1, "contra": False, "tax": False, "obsolete": False},
        {"id": 2, "accno": "1200", "description": "Accounts Receivable", "is_temp": False, "category": "A", "heading": 1, "contra": False, "tax": False, "obsolete": False, "open_item_managed": True},
    ])
    asset_register(W, [
        {"id": 101, "tag": "FORKLIFT-01", "description": "Toyota 8FGU25 forklift", "purchase_date": "2025-03-01", "purchase_value": 18500, "usable_life": 5, "asset_account_id": 1, "dep_account_id": 4, "exp_account_id": 4},
        {"id": 102, "tag": "SCAN-102", "description": "Zebra barcode scanner", "purchase_date": "2025-06-15", "purchase_value": 1200, "usable_life": 3, "asset_account_id": 1, "dep_account_id": 4, "exp_account_id": 4},
        {"id": 103, "tag": "DESK-103", "description": "Standing desk riser", "purchase_date": "2025-09-01", "purchase_value": 850, "usable_life": 5, "asset_account_id": 1, "dep_account_id": 4, "exp_account_id": 4},
    ], src=None)
    # policy text in the notes_field carrier (Setting.value), appending to the base settings rows
    ss.setdefault("Setting", []).append({"setting_key": "asset_policy",
        "value": "Capitalize any fixed asset whose purchase_value is 1500 or more; depreciate it over its usable_life years."})
    steps = [("ledgersmb", "reconciliation_create", {"account_id": 1, "end_date": "2026-09-30", "ending_balance": 1234.5})]
    preds = [
        ("rec1", "a bank reconciliation for account 1 at 2026-09-30 exists",
         CNT(SEL(NS("ledgersmb", "Reconciliation"), AND(F("chart_id", "eq", 1), F("end_date", "eq", "2026-09-30"))), "gte", 1), False),
        ("noasset", "no fixed asset with tag 'SURPLUS-X' is registered (negative)",
         CNT(SEL(NS("ledgersmb", "AssetItem"), F("tag", "eq", "SURPLUS-X")), "eq", 0), True),
        ("norec2", "no reconciliation exists for account 2 (negative)",
         CNT(SEL(NS("ledgersmb", "Reconciliation"), F("chart_id", "eq", 2)), "eq", 0), True),
    ]
    return steps, preds

__all__ = ["NEW_SERVER", "asset_register", "ap_vouchers", "checkpoints", "add_users", "smoke_seed"]
