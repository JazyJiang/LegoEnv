# Current admission correction (2026-10-24)

The app passed onboard with its explicitly declared optional login/carrier.
The original gate failures and test commands below are historical evidence,
not current reproduction instructions. Functional limits remain applicable;
fresh new-package results are recorded in the publication qualification index.

# btcpayserver source-bound adapter

Status: BLOCKED_MISSING_READABLE_POLICY_CARRIER. Prefix `btcpayserver`. All 67 original tool names and order retained; no new tool implementation.

Complete admission blocked: no native narrative read carrier. Independent Store metadata update/archive passes original strict/dklib and missing-write rejection.

Account approval/confirmation bits and StoreUser/StoreRole fixtures preserved. Native login and Store update only check account credentials/existence; actual pending account cross-store write demonstrates gap.

No Bitcoin/Lightning transfer, invoice/payment execution, wallet signatures, refund, email, webhook network delivery, opaque JSON policy fabrication or external effects certified.

Adapter changes: `evidence/base_spec.patch` is the full source-to-base diff; `evidence/patch_details.json` records identity, panel/binding and source-semantics details:

```json
{
  "binding": "Existing Account.Email credential column renamed email to match unchanged native sign_in(email,password) panel; original source executor otherwise ignores lowercase email",
  "scope": "Native Store name/website/archive metadata only",
  "carrier_gap": "Only Invoice/PaymentRequest/Payout reads; no readable narrative text carrier. Opaque Blob/settings JSON not repurposed as policy",
  "guards": "Account-existence guard retained; no StoreUser ownership binding or account approval gate invented"
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
