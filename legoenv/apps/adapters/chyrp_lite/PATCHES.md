# Current admission correction (2026-10-24)

The app passed onboard with its explicitly declared optional login/carrier.
The original gate failures and test commands below are historical evidence,
not current reproduction instructions. Functional limits remain applicable;
fresh new-package results are recorded in the publication qualification index.

# Chyrp Lite original scalar writes; admission blocked

Source chyrp-lite.spec.json is logical chyrp_lite. **BLOCKED_MISSING_READABLE_POLICY_CARRIER**: post_manage reads only metadata, not PostAttribute; no Page or Comment body read/list. No policy carrier is fabricated from slug/group/user names; carriers={} and smoke_seed reports the actual gap. metadata_smoke_seed independently verifies source writes but RESULT stays passed=false and original onboard fails.

Patches preserve all 41 tools and role predicates: neutral prefix, integer id arguments, synthetic original users, Permission semantic id preserved in code with new integer internal id and exactly equivalent Permission-select field rename, existing executor {lit:v} constants normalized to scalar v, actual post metadata filters. No role predicate/value relaxed. User2 denied page/category admin writes in actual probes.

Seven declared writes are state-probed. Page bodies persist, Post bodies do not: post_update status metadata only is claimed and PostAttribute body retention is explicitly tested. No invented body update, publication, confirmation-value validation or notification effects.

Reproduce `python3 prepare.py`, `python3 finalize.py`. Original onboard/strict/dklib business bytes and read-only original runtime are preserved via isolated namespace. SHA identities, full base diff, empty acceptance diff, missing-write rejection, coverage and MANIFEST included; no models/benchmarks. Source smoke/PATCHES.md is absent; untouched emit provenance remains disposable under work/.
