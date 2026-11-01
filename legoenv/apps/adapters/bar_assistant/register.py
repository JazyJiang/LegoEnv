"""Register shared bar-shelf inventory writes for the pack builder."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "bar_assistant"
SERVER[APP] = "bar_inventory"
PFX[APP] = "bar_assistant"
CONTENT[APP] = ["Bar", "BarMembership", "Ingredient", "BarIngredient"]
NOTES[APP] = (
    "{p}__ manages shared bar inventory. Sign in with sign_in(email, password). "
    "bar_show(id) reads the bar description and stock policy; ingredient_index(bar_id, limit) lists its ingredients; "
    "bar_shelfingredients(id) lists currently stocked ingredient ids. "
    "bar_shelfbatchadd(id, ingredient_id) adds one ingredient to the shared shelf, and "
    "bar_shelfbatchdelete(id, ingredient_id) removes one. "
    "Both writes require an Admin or owner membership in that bar; these tools change shelf presence, "
    "not an ingredient's counted quantity or a menu item's availability flag."
)
LOGIN[APP] = ("sign_in", "email")


_previous_obs_report = World.obs_report


def _obs_report(self):
    report, bad = _previous_obs_report(self)
    if APP not in self.apps:
        return report, bad
    env = runtime.Env(self.world)
    env.call(NS(APP, "sign_in"), {"email": self.persona, "password": self.password})
    for tool, args in (
        ("ingredient_index", {"bar_id": 1}),
        ("bar_shelfingredients", {"id": 1}),
    ):
        result = env.call(NS(APP, tool), args)
        report[f"{APP} {tool}"] = len(json.dumps(result, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    """Seed a bar policy, stocked candidates, and a deterministic shelf witness."""
    world.seed(APP, "Bar", [
        {"id": 1, "name": "Harbor Bar", "bar_type_id": 1, "created_user_id": 1,
         "description": "Remove zero-count juniper spirit and dry vermouth from the shared shelf. "
                        "Add verified citrus syrup. Leave tonic stocked and quarantined bitters off the shelf.",
         "status": "active", "is_active": True},
    ])
    world.seed(APP, "BarMembership", [
        {"id": 1, "bar_id": 1, "user_id": 1, "user_role_id": 1, "is_active": True},
    ])
    world.seed(APP, "Ingredient", [
        {"id": 11, "bar_id": 1, "slug": "juniper-spirit", "name": "Juniper spirit", "created_user_id": 1},
        {"id": 12, "bar_id": 1, "slug": "dry-vermouth", "name": "Dry vermouth", "created_user_id": 1},
        {"id": 13, "bar_id": 1, "slug": "citrus-syrup", "name": "Citrus syrup", "created_user_id": 1},
        {"id": 14, "bar_id": 1, "slug": "quarantined-bitters", "name": "Quarantined bitters", "created_user_id": 1},
        {"id": 15, "bar_id": 1, "slug": "tonic", "name": "Tonic", "created_user_id": 1},
    ])
    world.seed(APP, "BarIngredient", [
        {"id": 21, "bar_id": 1, "ingredient_id": 11},
        {"id": 22, "bar_id": 1, "ingredient_id": 12},
        {"id": 23, "bar_id": 1, "ingredient_id": 15},
    ])
    steps = [
        (APP, "bar_shelfbatchdelete", {"id": 1, "ingredient_id": 11}),
        (APP, "bar_shelfbatchdelete", {"id": 1, "ingredient_id": 12}),
        (APP, "bar_shelfbatchadd", {"id": 1, "ingredient_id": 13}),
    ]

    def shelf(ingredient_id):
        return SEL(NS(APP, "BarIngredient"), AND(F("bar_id", "eq", 1), F("ingredient_id", "eq", ingredient_id)))

    preds = [
        ("juniper_removed", "The depleted juniper spirit leaves the shared shelf.", CNT(shelf(11), "eq", 0), False),
        ("vermouth_removed", "The depleted dry vermouth leaves the shared shelf.", CNT(shelf(12), "eq", 0), False),
        ("citrus_added", "The verified citrus syrup enters the shared shelf.", CNT(shelf(13)), False),
        ("quarantine_skipped", "Quarantined bitters do not enter the shelf.", CNT(shelf(14), "eq", 0), True),
        ("tonic_preserved", "Tonic remains stocked.", CNT(shelf(15), "eq", 1), True),
    ]
    return steps, preds
