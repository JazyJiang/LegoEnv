"""register.py — attach the akaunting accounting spec to packlib WITHOUT editing packlib.py.

    import sys; sys.path.insert(0, "/builder/smoke/pack")
    from packlib import *
    from newspecs3.akaunting.register import *     # akaunting + seed helpers + smoke_seed

akaunting is the accounting/ERP (QuickBooks/Xero/FreshBooks stand-in): invoices & bills (Document),
payments (Transaction), contacts (customer/vendor), items, accounts, currencies, taxes, categories,
reconciliations, transfers. The base (pack/base_specs/akaunting.spec.json) carries only the persona
account (id 1, ops@akaunting.example / pw-operations) and the small seed - the content tables are empty;
seed them with the helpers below or W.seed(app, entity, rows).

Login: user_login(email, password); the session account (id 1) is both the signed-in user and the
"current company" (akaunting's company_id tenant key maps to the session account_id).
"""
import json, runtime
import packlib
from packlib import World, NS, SERVER, PFX, CONTENT, NOTES, OBS_CAP

NEW_SERVER = {"akaunting": "accounting"}
NEW_CONTENT = {"akaunting": ["Document", "Contact", "Item", "Account", "Transaction", "Category",
                             "Currency", "Tax", "Transfer", "Reconciliation", "Report", "Dashboard", "Widget", "Setting"]}
NEW_NOTES = {
    "akaunting": "{p}__ is the accounting suite (QuickBooks/Xero-style): sign in with {p}__user_login(email, password). "
                 "contact_search / item_search / account_search / currency_search / tax_search / category (no list tool - use category_create) list or search the master data; "
                 "document_search(q, status) lists invoices & bills (type invoice/bill); document_show(id) opens one; "
                 "document_create(type, document_number, issued_at, due_at, amount, currency_code, currency_rate, contact_id, category_id, contact_name, notes) makes a draft invoice/bill; "
                 "document_sent(id) / document_received(id) / document_cancel(id) move status; documenttransaction_create(document_id, amount, paid_at, account_id) records a payment against a document. "
                 "transaction_search(type, search) lists bank transactions; account_search lists bank accounts; setting_search reads settings (company.name etc). "
                 "A customer/vendor is created with contact_create(type, name, email, currency_code).",
}
LOGIN = {"akaunting": ("user_login", "email")}
for _a in NEW_SERVER:
    SERVER.setdefault(_a, NEW_SERVER[_a]); PFX.setdefault(_a, _a); CONTENT.setdefault(_a, NEW_CONTENT[_a]); NOTES.setdefault(_a, NEW_NOTES[_a])
packlib.LOGIN.update(LOGIN)

# ───────── whole-list reads the agent will make (12k observation cap) ─────────
_orig_obs = World.obs_report
def _obs_report(self):
    rep, bad = _orig_obs(self)
    if "akaunting" not in self.apps: return rep, bad
    env = runtime.Env(self.world)
    def rd(tool, args): return len(json.dumps(env.call(NS("akaunting", tool), args), ensure_ascii=False, default=str))
    env.call(NS("akaunting", "user_login"), {"email": self.persona, "password": self.password})
    for t in ("contact_search", "item_search", "account_search", "currency_search", "tax_search",
              "document_search", "transaction_search", "setting_search", "report_search",
              "transfer_search", "reconciliation_search", "user_search", "company_search", "module_list"):
        rep[f"akaunting {t}"] = rd(t, {})
    bad = {k: v for k, v in rep.items() if v > OBS_CAP}
    return rep, bad
World.obs_report = _obs_report

# ───────── seeding helpers ─────────
TS = "2026-01-01T00:00:00"
def _ss(W): return W.spec["akaunting"]["seed_state"]
def _bind(W, ent, src, n, where=None):
    if src: W.bindings[NS("akaunting", ent) + (f"({where})" if where else "")] = {"dataset": src, "rows": n}

def contacts(W, rows, src=None):
    """rows = [{id (int), type: customer|vendor|employee, name, email?, currency_code?, phone?, address?, city?, zip_code?, state?, country?, tax_number?, enabled?}]"""
    ss = _ss(W)
    for r in rows:
        ss.setdefault("Contact", []).append({"id": r["id"], "company_id": 1, "type": r["type"], "name": r["name"], "email": r.get("email"),
            "currency_code": r.get("currency_code", "USD"), "enabled": r.get("enabled", 1), "phone": r.get("phone"), "address": r.get("address"),
            "city": r.get("city"), "zip_code": r.get("zip_code"), "state": r.get("state"), "country": r.get("country"), "tax_number": r.get("tax_number")})
    _bind(W, "Contact", src, len(rows))
def items(W, rows, src=None):
    """rows = [{id, name, type?: product|service, sku?, description?, sale_price?, purchase_price?, enabled?}]"""
    ss = _ss(W)
    for r in rows:
        ss.setdefault("Item", []).append({"id": r["id"], "company_id": 1, "type": r.get("type", "product"), "name": r["name"], "sku": r.get("sku"),
            "description": r.get("description"), "sale_price": r.get("sale_price"), "purchase_price": r.get("purchase_price"), "enabled": r.get("enabled", 1)})
    _bind(W, "Item", src, len(rows))
def accounts(W, rows, src=None):
    """rows = [{id, name, type?: bank, number?, currency_code?, opening_balance?, bank_name?, enabled?}]"""
    ss = _ss(W)
    for r in rows:
        ss.setdefault("Account", []).append({"id": r["id"], "company_id": 1, "type": r.get("type", "bank"), "name": r["name"], "number": r.get("number") or "",
            "currency_code": r.get("currency_code", "USD"), "opening_balance": r.get("opening_balance", 0.0), "bank_name": r.get("bank_name"), "enabled": r.get("enabled", 1)})
    _bind(W, "Account", src, len(rows))
def documents(W, rows, src=None):
    """rows = [{id, type: invoice|bill, document_number, status?: draft|sent|received|partial|paid|cancelled, issued_at?, due_at?,
                amount, currency_code?, currency_rate?, contact_id?, contact_name?, category_id?, notes?}]"""
    ss = _ss(W)
    for r in rows:
        ss.setdefault("Document", []).append({"id": r["id"], "company_id": 1, "type": r["type"], "document_number": r["document_number"],
            "status": r.get("status", "draft"), "issued_at": r.get("issued_at", TS), "due_at": r.get("due_at", TS),
            "amount": r["amount"], "currency_code": r.get("currency_code", "USD"), "currency_rate": r.get("currency_rate", 1.0),
            "contact_id": r.get("contact_id"), "contact_name": r.get("contact_name"), "category_id": r.get("category_id", 1),
            "notes": r.get("notes")})
    _bind(W, "Document", src, len(rows))
def transactions(W, rows, src=None):
    """rows = [{id, type: income|expense, amount, paid_at?, account_id?, description?, number?, currency_code?}]"""
    ss = _ss(W)
    for r in rows:
        ss.setdefault("Transaction", []).append({"id": r["id"], "company_id": 1, "type": r["type"], "amount": r["amount"],
            "paid_at": r.get("paid_at", TS), "account_id": r.get("account_id"), "description": r.get("description"),
            "number": r.get("number"), "currency_code": r.get("currency_code", "USD"), "currency_rate": r.get("currency_rate", 1.0),
            "category_id": r.get("category_id", 1), "reconciled": bool(r.get("reconciled", False))})
    _bind(W, "Transaction", src, len(rows))
def categories(W, rows, src=None):
    """rows = [{id, name, type: income|expense|item|other, code?, color?}]"""
    ss = _ss(W)
    for r in rows:
        ss.setdefault("Category", []).append({"id": r["id"], "company_id": 1, "code": r.get("code"), "name": r["name"], "type": r["type"],
            "color": r.get("color", "#000000"), "enabled": r.get("enabled", 1)})
    _bind(W, "Category", src, len(rows))
def policy(W, key, text, src=None):
    """seed a policy / notes as a Setting row (carrier notes_field -> Setting.value)."""
    ss = _ss(W)
    ss.setdefault("Setting", []).append({"id": 1 + len(ss.get("Setting", [])), "company_id": 1, "key": key, "value": text})
    _bind(W, "Setting", src, 1, where=key)
    return text

# ───────── smoke_seed: build a small world + gold steps + contract predicates ─────────
from packlib import SEL, F, AND, CNT
def smoke_seed(W):
    """seed >= 3 content rows + one policy text in the carrier; returns (steps, preds)."""
    contacts(W, [
        {"id": 10, "type": "customer", "name": "Northwind Traders", "email": "ap@northwind.example"},
        {"id": 11, "type": "customer", "name": "Contoso Ltd", "email": "billing@contoso.example"},
        {"id": 12, "type": "vendor", "name": "PaperCo", "email": "sales@paperco.example"},
    ])
    items(W, [
        {"id": 20, "name": "Consulting", "type": "service", "sale_price": 120.0},
        {"id": 21, "name": "Printer Paper", "sku": "PP-100", "sale_price": 8.0},
    ])
    accounts(W, [{"id": 30, "name": "Operating", "number": "1001"}, {"id": 31, "name": "Savings", "number": "1002"}])
    policy(W, "policy.invoicing", "Invoices for customers in the 'Enterprise' tier must be issued within 7 days of the order. Apply a 10% late-payment fee to any invoice beyond 30 days unpaid.")

    # Gold: step 1 creates an invoice for the Northwind customer; step 2 (callable) creates one for
    # Contoso and immediately marks it sent (document_sent needs the created id, so it must be a
    # callable that inspects the create reply).
    def _create_and_send(env):
        r = env.call(NS("akaunting", "document_create"), {"type": "invoice", "document_number": "INV-2026-002",
            "issued_at": "2026-09-21", "due_at": "2026-10-06", "amount": 990.0, "currency_code": "USD",
            "currency_rate": 1.0, "contact_id": 11, "category_id": 1, "contact_name": "Contoso Ltd"})
        did = r.get("result", {}).get("id")
        env.call(NS("akaunting", "document_sent"), {"id": did})
    steps = [
        ("akaunting", "document_create", {"type": "invoice", "document_number": "INV-2026-001", "issued_at": "2026-09-20",
                                          "due_at": "2026-10-05", "amount": 2450.0, "currency_code": "USD",
                                          "currency_rate": 1.0, "contact_id": 10, "category_id": 1,
                                          "contact_name": "Northwind Traders", "notes": "Enterprise order"}),
        _create_and_send,
    ]
    preds = [
        ("p1", "an invoice document for Northwind Traders with amount 2450 exists",
         CNT(SEL(NS("akaunting", "Document"), AND(F("contact_name", "eq", "Northwind Traders"), F("amount", "eq", 2450.0)))), False),
        ("p2", "a document marked sent exists (the Contoso invoice was sent)",
         CNT(SEL(NS("akaunting", "Document"), AND(F("contact_name", "eq", "Contoso Ltd"), F("status", "eq", "sent")))), False),
        ("p3", "no invoice exists for a vendor (negative: PaperCo vendor has no invoice)",
         CNT(SEL(NS("akaunting", "Document"), F("contact_id", "eq", 12)), "eq", 0), True),
    ]
    return steps, preds

__all__ = ["NEW_SERVER", "contacts", "items", "accounts", "documents", "transactions", "categories", "policy", "smoke_seed"]
