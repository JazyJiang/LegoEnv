# Current admission correction (2026-10-24)

The app passed onboard with its explicitly declared optional login/carrier.
The original gate failures and test commands below are historical evidence,
not current reproduction instructions. Functional limits remain applicable;
fresh new-package results are recorded in the publication qualification index.

# Minds: source-authentication admission gap

Rank 12 raw source: `pack/base_specs/minds.spec.json` (bundled source copy; public upstream recorded in third_party_licenses/app_sources.json). This source describes Project/Conversation/Skill/Schedule metadata, not a social-post application. It has 16 entities, 51 tools, `auth={}` and `seed_state={}`. It has no account entity or login/authentication tool. No account, persona or login tool is invented; card login strings are deliberately empty and packlib.LOGIN has no Minds entry. Original onboard is therefore expected to reject this app. RESULT.json reports `BLOCKED_MISSING_SOURCE_AUTH`, not a complete onboarding PASS.

Three patch families are reproducible with prepare.py: neutral env_id minds; integer argument identities (including numeric-only source skill_delete lookup); optional actual substring filters on project_list and skill_list. Every original tool is retained; no guard/runtime/acceptance edits. Skill.instructions is the policy carrier. Six original scalar Project/Skill CRUD tools have state-effect probes and kind coverage; this does not certify unavailable authentication or other retained tools.

Local deterministic verification legitimately uses the original sim_gold callable-step API to record actual no-auth calls, beginning with project_list, followed by writes. Original strict acceptance and dklib.check/finish/emit_task/runtime.run_task pass for that synthetic smoke. The missing-write negative retains only project_list and original strict rejects it. These local results do not override the original onboarding rejection. Upstream authentication tooling or an explicitly revised no-auth admission contract would be required for full onboarding; neither is fabricated here.

Known unclaimed source effects: responses_create inserts a Conversation without generating an assistant response; schedule_run_now only creates conversation metadata; external channel delivery, scheduler execution, filesystem rename and binary transfer are absent/incomplete. Project name changes do not update path and activating one project does not deactivate others. Missing functionality is not repaired by inventing tools.

Historical paths are mapped only inside private mount namespace/chroot. Original packlib, accept, argnorm, dklib, onboard_check, fill_witness and emit_task are byte-identical; original runtime/composition are read-only. acceptance_code.patch is empty. Source SHA, source/output diffs and MANIFEST.tsv preserve identity. Source smoke/PATCHES.md referenced by the brief is absent. No model endpoint is used.

Commands from this directory:

```sh
python3 prepare.py
bash run_namespace.sh /out/verify.py
bash run_namespace.sh pack_dpsk/contract/onboard_check.py minds  # expected FAIL
python3 validate_card.py
python3 finalize.py
```

finalize.py saves both the successful deterministic checks and expected original-onboard failure, then emits the honest blocked result. Synthetic emitted smoke packages remain excluded under work/.
