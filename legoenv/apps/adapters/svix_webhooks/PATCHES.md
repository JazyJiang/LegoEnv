# Current admission correction (2026-10-24)

The app passed onboard with its explicitly declared optional login/carrier.
The original gate failures and test commands below are historical evidence,
not current reproduction instructions. Functional limits remain applicable;
fresh new-package results are recorded in the publication qualification index.

# svix_webhooks source-bound adapter

Status: BLOCKED_MISSING_SOURCE_AUTH. Prefix `svix_webhooks`. All 42 original tool names and order retained; no new tool implementation.

Complete admission blocked because original spec has no authentication interface. Genuine public EventType description reads and metadata create/patch/delete independently pass original strict/dklib/missing-write control.

Native eventtype_delete always hard deletes regardless expunge=false; actual absence is verified. Duplicate active event type and missing target patch denied. No JWT/org isolation invented.

No webhook HTTP delivery, retries, signing keys, endpoint network calls, message broker, API token validation or external effects certified.

Adapter changes: `evidence/base_spec.patch` is the full source-to-base diff; `evidence/patch_details.json` records identity, panel/binding and source-semantics details:

```json
{
  "auth_gap": "Original spec has no auth configuration or login tool; no JWT/API-token auth invented",
  "scope": "Native public EventType description create/patch/delete metadata only"
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
