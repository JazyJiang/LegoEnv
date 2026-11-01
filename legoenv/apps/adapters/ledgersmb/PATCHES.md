# LedgerSMB onboard patches (workstream B)

Raw spec: `apps/base_specs/ledgersmb.spec.json`
Patched base: `pack/base_specs/ledgersmb.spec.json`
Register: `pack/newspecs3/ledgersmb/register.py` · Card: `pack/newspecs3/ledgersmb/capability_card.json`

## Patches applied to the base spec
1. **env_id `ledgersmb` → `ledgersmb_ab`.** `ignite.merge_world` derives the merged prefix from
   `mvgen.slug(env_id)`; with the raw `ledgersmb` the merged entity/tool namespace became just
   `ledgersmb__*`, but packlib expects `PFX["ledgersmb"] == "ledgersmb_ab"` — `World.merge()` asserts
   `pfx[app] == PFX[app]` and failed. Other bases already carry `<app>_ab`; this copy did not.
2. **Persona password collision.** `World.__init__` renames the persona by substring-replacing the
   base username `"ada"` everywhere in `seed_state`, then separately replaces the old password
   `"pw-ada"`. Because `"ada" ⊂ "pw-ada"`, the first pass clobbered `pw-ada` → `pw-<persona-email>`
   before the password replace ran, so the real password set was never written and login failed.
   Set User(id 1) password to `"changeme"` (no `ada` substring). (Side effect: `"Canada"` in the
   Country seed also contains `"ada"` and gets renamed to `"C<persona>na"` — harmless reference data.)
3. **id-typed tool args retyped `id` → `int`.** 37 input_schema args declared `type: id` (e.g.
   `reconciliation_create.account_id`, `batch_post.in_batch_id`, `assetitem_save.in_asset_account_id`,
   `role_assign.id`, `user_delete.id`). Per the cross-spec rule (patch ledger) runtime `Env._writable`
   excludes `type=id` columns on write, and the smoke/agent gold must be able to pass back integer ids.
4. **Auth guards on 52 tools.** LedgerSMB's write/read tools carried only an auth *message* (e.g.
   `"auth": "Sign in before creating a reconciliation."`) without `guards.requires_auth`, so an
   unsigned persona could call them. Added `requires_auth: true` to every such tool (except the auth
   tools `sign_in` / `user_logout`), so a signed-in persona is required to mutate/read protected data.

## Patches in register.py / capability_card.json (not to the spec)
- `register.py` registers `ledgersmb` into `SERVER/PFX/CONTENT/NOTES/LOGIN` exactly like
  `pack/newspecs3`'s pattern, adds a `World.obs_report` hook for the whole-list reads
  (`goods_list`, `assetitem_search`, `country_list`, `menu_generate`), exposes seeding helpers
  (`asset_register`, `ap_vouchers`, `checkpoints`, `add_users`) and `smoke_seed(W) -> (steps, preds)`.
- Card declares kinds realised by the stock write tools + two proposed kinds
  (`other:post_batch` → `batch_post`, `other:generate_report` → `gl_report`/`trialbalance_report`/
  `pnl_generate`), the `policy_sheet`/`notes_field` carriers on `Setting.value`, and the
  `tool_families_to_keep` prefixes (a ledgersmb world stays ≤ 350 tools).
- Content needed by a reconciliation/seeding (Account) is seeded in `smoke_seed`, since `Account` is a
  CONTENT entity the base leaves empty.

## Harness fix (one line, not a spec patch)
- `pack_dpsk/contract/onboard_check.py:32` referenced `packlib.LOGIN` but the file only does
  `from packlib import *`, which binds `LOGIN`, not the name `packlib` → `NameError` for every app.
  Changed to `LOGIN` (a semantic no-op).

## Could not make work
- LedgerSMB multi-user approval chains (batch *posting* gated on separate-duties settings, report
  approval `books_reopen`/`assetreport_approve` needing approved-period checkpoints) are present in the
  spec but not exercised by `smoke_seed`; they are left for pack-time seeding when a task needs them.
