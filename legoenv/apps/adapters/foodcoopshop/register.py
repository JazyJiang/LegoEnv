"""Register tested catalog and available-stock writes for isolated task packs."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "foodcoopshop"
SERVER[APP] = "cooperative catalog"
PFX[APP] = "foodcoopshop"
CONTENT[APP] = ["Product", "StockAvailable"]
NOTES[APP] = (
    "{p}__ is a cooperative product catalog. Sign in with customer_login(email, password). "
    "catalog_product_search(keyword) and catalog_product_detail(product_id) inspect items, including the policy reference item. "
    "product_edit_quantity(product_id, quantity) changes the available-stock record; "
    "product_edit_status(product_id, status) sets listing activity; "
    "product_edit_name(product_id, name, description) changes catalog text; "
    "product_add(manufacturer_id, name, storage_location_id, unity, is_declaration_ok) creates an inactive draft product. "
    "These actions do not amend existing order totals or execute supplier purchasing."
)
LOGIN[APP] = ("customer_login", "email")


_old_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _old_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "customer_login"), {"email": self.persona, "password": self.password})
    for name, args in (("catalog_product_search", {}), ("catalog_product_detail", {"product_id": 5})):
        response = env.call(NS(APP, name), args)
        report[f"{APP} {name}"] = len(json.dumps(response, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    """Seed a catalog, an embedded stock policy, and near-miss items."""
    common = {"id_manufacturer": 1, "id_tax": 1, "id_storage_location": 1, "unity": "kg", "is_stock_product": 1}
    world.seed(APP, "Product", [
        {"id_product": 1, "name": "Carrots", "description": "Regular stock item.", "active": 1, "is_declaration_ok": 1, **common},
        {"id_product": 2, "name": "Cherry tomatoes", "description": "Signed physical count is complete.", "active": 1, "is_declaration_ok": 1, **common},
        {"id_product": 3, "name": "Leafy greens", "description": "Supplier declaration is missing.", "active": 1, "is_declaration_ok": 0, **common},
        {"id_product": 4, "name": "Potatoes", "description": "The supplier issued a corrected label.", "active": 1, "is_declaration_ok": 1, **common},
        {"id_product": 5, "name": "Stock control policy", "description": "For the signed count, set cherry tomatoes to twelve available units. Hide leafy greens until the supplier declaration arrives. Update the potatoes listing to Farm potatoes with its corrected origin note. Add Winter squash from the approved supplier as an inactive draft. Leave carrots unchanged.", "active": 0, "is_declaration_ok": 1, **common},
    ])
    world.seed(APP, "StockAvailable", [
        {"id_stock_available": n, "id_product": n, "id_product_attribute": 0, "quantity": q, "quantity_limit": 0, "sold_out_limit": 0, "always_available": 0}
        for n, q in ((1, 40), (2, 20), (3, 8), (4, 30))
    ])
    steps = [
        (APP, "product_edit_quantity", {"product_id": 2, "quantity": 12}),
        (APP, "product_edit_status", {"product_id": 3, "status": 0}),
        (APP, "product_edit_name", {"product_id": 4, "name": "Farm potatoes", "description": "Corrected origin label received from the supplier."}),
        (APP, "product_add", {"manufacturer_id": 1, "name": "Winter squash", "storage_location_id": 1, "unity": "kg", "is_declaration_ok": True}),
    ]
    preds = [
        ("stock_count", "Tomato available stock reflects the signed count.", CNT(SEL(NS(APP, "StockAvailable"), AND(F("id_product", "eq", 2), F("quantity", "eq", 12)))), False),
        ("hide_greens", "Undeclared greens are inactive.", CNT(SEL(NS(APP, "Product"), AND(F("id_product", "eq", 3), F("active", "eq", 0)))), False),
        ("correct_label", "Potato catalog label is corrected.", CNT(SEL(NS(APP, "Product"), AND(F("id_product", "eq", 4), F("name", "eq", "Farm potatoes")))), False),
        ("draft_squash", "Winter squash exists as an inactive draft.", CNT(SEL(NS(APP, "Product"), AND(F("name", "eq", "Winter squash"), F("active", "eq", 0), F("id_manufacturer", "eq", 1)))), False),
        ("preserve_carrots", "Unselected carrot stock is not changed.", CNT(SEL(NS(APP, "StockAvailable"), AND(F("id_product", "eq", 1), F("quantity", "eq", 12))), "eq", 0), True),
        ("preserve_policy", "Policy reference item stays inactive.", CNT(SEL(NS(APP, "Product"), AND(F("id_product", "eq", 5), F("active", "eq", 1))), "eq", 0), True),
    ]
    return steps, preds
