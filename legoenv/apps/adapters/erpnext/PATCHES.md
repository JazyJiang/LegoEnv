# Current admission correction (2026-10-24)

The app passed onboard with its explicitly declared optional login/carrier.
The original gate failures and test commands below are historical evidence,
not current reproduction instructions. Functional limits remain applicable;
fresh new-package results are recorded in the publication qualification index.

# ERPNext: source authentication admission gap

Rank 14 source: `pack/base_specs/erpnext.spec.json` (bundled source copy; public upstream recorded in third_party_licenses/app_sources.json). All 45 original tools are retained. Source has no auth configuration or login tool, and its User entity has no password. No account, login tool or fake mapping is added. The card explicitly leaves login strings empty; original onboard must fail. RESULT reports BLOCKED_MISSING_SOURCE_AUTH rather than a complete onboarding PASS.

prepare.py reproduces three patch families: neutral erpnext env_id; integer internal seed ids without altering ERP business name/FK values or string input schemas; real parent filters for employee_get_children/reports_to and salesorder_get_work_order_items/parent. ERP names such as SO-101 and EMP-101 are business keys, not internal integer ids. No guards/runtime/acceptance predicates are changed. Employee.reason_for_leaving is a real free-text carrier exposed by the employee list, not a fabricated document interface. Most other ERP entities have no read tool.

Nine effect-tested source writes support create_record (employee_create, item_create, warehouse_create), update_record (item_update), record_status_change (employee_save, salesorder_submit, salesorder_cancel, issue_set_status), delete_or_archive_row (warehouse_delete). Probes verify actual rows/fields/removal and invalid FK, duplicate item, missing target and illegal transition controls. Callable steps in original sim_gold record actual no-auth source calls; original strict and complete dklib.check/finish/emit_task/runtime.run_task pass for the synthetic local smoke. Removing writes and retaining only employee_get_children makes original strict reject it. These deterministic checks do not override original onboard rejection.

Limits retained and disclosed: new runtime records synthesize numeric name PKs without naming-series semantics; submit/cancel changes docstatus but not finance/stock/shipments/payments; direct status setters do not implement full workflows. Warehouse-delete stock guard rejects zero-balance Bin rows and can allow a nonzero-stock warehouse to disappear, demonstrated in unsupported_interface_probes.json. This tool is certified only as a scalar row deletion, not stock-safe behavior. No broad ERP lifecycle, permission or accounting claim is made.

Original packlib/accept/argnorm/dklib/onboard_check/fill_witness/emit_task are copied byte-identically. Runtime/composition are read-only. Historical paths exist only inside a private disposable namespace/chroot; no global symlink, source edit or endpoint call. acceptance_code.patch is empty. Source SHA, complete spec diff, logs and MANIFEST.tsv are retained. Source smoke/PATCHES.md referenced by the brief is absent.

Commands from this directory:

```sh
python3 prepare.py
bash run_namespace.sh /out/verify.py
bash run_namespace.sh pack_dpsk/contract/onboard_check.py erpnext  # expected FAIL: login absent
python3 validate_card.py
python3 finalize.py
```

Synthetic smoke contains three initially-false positives and one nonvacuous preserved-reference predicate. Emitted smoke packages remain excluded under work/. A real upstream login tool or explicit revision of no-auth admission requirements is needed for full onboarding.
