"""Register CKAN dataset publication and resource writes for the pack builder."""

import json

import runtime
from packlib import AND, CNT, CONTENT, F, LOGIN, NOTES, NS, OBS_CAP, PFX, SEL, SERVER, World


APP = "ckan"
SERVER[APP] = "open_data"
PFX[APP] = "ckan"
CONTENT[APP] = ["Package", "Resource", "Group", "Member", "PackageTag", "Tag"]
NOTES[APP] = (
    "{p}__ is the open-data catalog. Sign in with sign_in(email, password). "
    "package_package_list(limit) lists datasets; package_package_search(q) finds datasets by a nonempty query; "
    "package_show(id) reads a dataset and its notes; "
    "package_create(name, title, private, notes) creates a dataset; "
    "package_patch(id, title, notes, private, state) changes existing metadata or visibility; "
    "resource_create(package_id, url, name, format) attaches a resource to an existing dataset. "
    "Use the dataset id returned by package_create for later writes. "
    "Use resource_resource_search(query) or resource_show(id) to inspect resources."
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
        ("package_package_list", {"limit": 20}),
        ("resource_resource_search", {"query": {}, "limit": 20}),
    ):
        result = env.call(NS(APP, tool), args)
        report[f"{APP} {tool}"] = len(json.dumps(result, ensure_ascii=False, default=str))
    bad = {name: size for name, size in report.items() if size > OBS_CAP}
    return report, bad


World.obs_report = _obs_report


def smoke_seed(world):
    """Seed a public-data review and return a three-write deterministic witness."""
    policy = (
        "Publish approved datasets after privacy and metadata review. Attach the "
        "validated CSV only to the approved dataset. Keep restricted source records private."
    )
    world.seed(APP, "Package", [
        {"id": "ds-policy", "name": "publication-policy", "title": "Publication policy",
         "notes": policy, "private": True, "state": "active", "creator_user_id": 1},
        {"id": "ds-ready", "name": "validated-service-metrics", "title": "Validated service metrics",
         "notes": "Privacy and quality reviews are complete.", "private": True,
         "state": "active", "creator_user_id": 1},
        {"id": "ds-restricted", "name": "restricted-source-records", "title": "Restricted source records",
         "notes": "Contains records pending privacy review.", "private": True,
         "state": "active", "creator_user_id": 1},
    ])
    world.seed(APP, "Resource", [
        {"id": "res-internal", "package_id": "ds-restricted",
         "url": "https://data.example/internal-source.csv", "name": "internal-source.csv", "format": "CSV"},
    ])
    steps = [
        (APP, "package_create", {"name": "approved-reference-map", "title": "Approved reference map",
                                  "notes": "Privacy and quality reviews are complete.", "private": False}),
        (APP, "package_patch", {"id": "ds-ready", "private": False,
                                 "notes": "Released after privacy and metadata sign-off."}),
        (APP, "resource_create", {"package_id": "ds-ready", "url": "https://data.example/service-metrics.csv",
                                   "name": "service-metrics.csv", "format": "CSV"}),
    ]
    created = SEL(NS(APP, "Package"), AND(F("name", "eq", "approved-reference-map"), F("private", "eq", False)))
    published = SEL(NS(APP, "Package"), AND(F("id", "eq", "ds-ready"), F("private", "eq", False)))
    attached = SEL(NS(APP, "Resource"), AND(F("package_id", "eq", "ds-ready"),
                                            F("url", "eq", "https://data.example/service-metrics.csv")))
    restricted_published = SEL(NS(APP, "Package"), AND(F("id", "eq", "ds-restricted"), F("private", "eq", False)))
    preds = [
        ("new_public_dataset", "A reviewed dataset is created publicly.", CNT(created), False),
        ("ready_published", "The approved existing dataset becomes public.", CNT(published), False),
        ("resource_attached", "The validated CSV is attached to the approved dataset.", CNT(attached), False),
        ("restricted_private", "The restricted dataset is not made public.", CNT(restricted_published, "eq", 0), True),
    ]
    return steps, preds
