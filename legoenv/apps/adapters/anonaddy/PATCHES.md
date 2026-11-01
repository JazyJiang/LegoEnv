# Current admission correction (2026-10-24)

The app passed onboard with its explicitly declared optional login/carrier.
The original gate failures and test commands below are historical evidence,
not current reproduction instructions. Functional limits remain applicable;
fresh new-package results are recorded in the publication qualification index.

# anonaddy source-bound adapter

Status: BLOCKED_MISSING_PERSONA_AUTH. Prefix `anonaddy`. All 93 original tool names and order retained; no new tool implementation.

Complete persona admission blocked: native credential identifier is User.id; no handle-resolution tool or User username field exists. Preserve numeric source auth and prove persona-string denial.

Independent original strict/dklib and missing-write rejection cover native Alias.description/from_name update and pin. No email forwarding, outbound message delivery, crypto, signed URL validation or external effects certified.

Adapter changes: `evidence/base_spec.patch` is the full source-to-base diff; `evidence/patch_details.json` records identity, panel/binding and source-semantics details:

```json
{
  "ids": "Opaque source FKs integer mapped; original User.id=u1 retained in patched base to avoid original World numeric-username substitution corruption. metadata_smoke_seed restores actual numeric account1 before independent native auth; complete persona auth remains blocked",
  "auth_gap": "Native login username is explicitly User.id, not a handle; preserve source verification, no invented username field/join",
  "scope": "Independent genuine Alias.description update and pin; source signed-link deactivation is anonymous"
}
```

Reproduce from this directory:

```sh
python3 prepare.py
python3 finalize.py
```

`run_namespace.sh` uses private user/mount/pid namespaces and a temporary chroot to map only this app and byte-identical original smoke files onto historical paths. Original runtime/composition are read-only mounts. The host project, /mnt tree and model credentials are absent. No global /data links, original source writes, model calls, benchmark tasks/metadata/assertions or cross-app changes are used. Source `smoke/PATCHES.md` referenced by ONBOARD_BRIEF is absent.

Original onboard/strict/dklib code is unchanged. `evidence/acceptance_code.patch` is empty; `evidence/source_identity.json` has original/staged SHA-256 identities. Original onboard result, strict report, dklib result, actual scalar probes, per-kind coverage and missing-write rejection are in `evidence/`. Blocked admission is not counted as complete PASS even when independent record-state checks pass.

`RESULT.json` gives the final status; `MANIFEST.tsv` hashes every deliverable and evidence file outside disposable `work/`. Original emitted legacy provenance remains only under disposable work.
