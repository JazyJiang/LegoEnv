# pretalx onboarding

Rank 21 raw source: `outputs/env_compiler/releases/v1/repo_specs/pretalx.spec.json`. Prefix pretalx; all 88 original tools and argument names retained. Source/staged SHA, complete spec diff and output MANIFEST.tsv preserve identity. No invented tools or privileged persona.

Five patch families are reproducible with prepare.py: neutral env_id; integer identity schemas plus malformed input dictionaries whose type held a description and description held a required boolean (every repair records source and patched values); synthetic User 1/2/3 preserving original administrator flags; room_create resolves its source slug argument through Event into the actual FK instead of absent session.event_id, in fields as well as set_on_create to avoid the generic same-name argument override; speakerprofile_list retains exact event scope and gains actual optional substring search. All original authentication/permission predicates remain unchanged.

Nine state-tested tools cover create_record (speakerprofile_create/room_create), update_record (speakerprofile_update_orga/room_update), record_status_change (speakerprofile_toggle_arrived/room_toggle_hidden/submission_accept), delete_or_archive_row (speakerprofile_delete/room_delete). SpeakerProfile.internal_notes is the real readable policy carrier. Helpers append integer-id speakers/rooms/known-code submissions.

Limits: Team guards often test globally existing permission flags without joining the signed-in user/event; anonymous speaker creation can succeed, demonstrated in probes. Original User1 is not an administrator; submissioncomment_create requires both a Team flag and administrator=true, so it remains blocked, without role elevation or an invented replacement. No Submission/Room read/list tools exist. Speaker creation omits generated code/user linkage; arrived always sets true and hidden-room toggle cannot reverse after hidden=true. Scheduling, availability checks, invitation delivery, full lifecycle, general ACLs and binary resources are not certified.

Original onboard_check, packlib, accept, argnorm, dklib, fill_witness and emit_task are staged byte-identically; runtime/composition read-only. Private disposable namespace/chroot supplies historical paths only locally; no global symlink/source edits/model endpoint. acceptance_code.patch is empty. Source smoke/PATCHES.md referenced by the brief is absent.

```sh
python3 prepare.py
bash run_namespace.sh /out/verify.py
bash run_namespace.sh "${CONTRACT_ROOT:?set the contract path inside the isolated namespace}/onboard_check.py" pretalx
python3 validate_card.py
python3 finalize.py
```

CPU smoke has three initially-false positives and one nonvacuous preserved-reference predicate. Original strict/dklib.check execute fill_witness/emit_task/runtime.run_task. Missing-write negative retains actual user_login only and must fail strict. Probes cover every declared effect, wrong credentials/anonymous room creation, scoped reads, missing targets and unsupported permissions/code generation. Synthetic emitted packages stay excluded under work/.

## Room update event path

The collected room_update declaration binds event to Event.slug, while Room.event references Event.id. Add the resolved event id to row_key so the existing pinned runtime treats the event argument as a selector and rejects a mismatched event. The room field panel and runtime remain unchanged. Evidence: room_update._binds and exec_spec.fields, route POST /orga/event/{event}/schedule/rooms/{pk}/, collected src/pretalx/orga/views/schedule.py RoomView.

The contract-path placeholder replaces the original private filesystem locator. These historical helper commands require their isolated onboarding harness; use the release installation guide for the standalone bundle.
