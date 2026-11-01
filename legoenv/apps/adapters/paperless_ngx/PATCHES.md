# paperless_ngx — base-spec patches (workstream B onboarding)

Base built by `make_base.py` from the Env Compiler release spec
(`apps/base_specs/paperless-ngx.spec.json`)
into `pack/base_specs/paperless_ngx.spec.json`. All patches below are applied there;
they mirror the cross-spec ledger in `smoke/PATCHES.md`.

## persona / login
- **Persona account is id 1**: the raw spec's id-1 user (`admin`) is the persona; its
  username is a placeholder (`PAPERLESS_PLACEHOLDER`) and its password is a placeholder
  (`PWDPLACEHOLDER`) chosen so the World persona-rename (`js.replace(username, persona)`)
  cannot corrupt the password or email (both contained the substring `admin`). The base
  otherwise relies on `World.__init__` to swap in `ops@… / pw-operations` like every base.
- **env_id set to `paperless_ngx_ab`** so the merged prefix is `paperless_ngx_ab` (matches
  `PFX`; `ignite.merge_world` derives the prefix from `mvgen.slug(env_id)`).
- Login tool is already named `sign_in` (username, password) — no rename needed.

## cross-spec (shared-world / runtime facts)
- **FK columns retyped id->text** so update tools can re-point them (the runtime's
  `_writable` excludes every `type=id` column on update): `Document.correspondent_id /
  document_type_id / storage_path_id / root_document_id / owner_id`,
  `Note.document_id / user_id`, `CustomFieldInstance.document_id / field_id`,
  `PaperlessTask.owner_id`.
- **Renamed update args copied into `exec_spec.set`** (`ex_field_set` ignores dict-form
  `fields` and only writes args whose name equals a writable column plus `spec.set`):
  `correspondent->correspondent_id`, `document_type->document_type_id`,
  `storage_path->storage_path_id`, `owner->owner_id`, `parent->tn_parent`, across
  `document_update`, `correspondent_update`, `documenttype_update`, `tag_update`,
  `storagepath_update`, `bulkedit_set_*`.
- **Owner scope + default page caps removed from all read/search tools** (a shared world:
  rows owned by colleagues and table tails must be visible), matching the other long-tail
  bases.

## whole-list reads under 12k (brief item)
- **`document_list` rewritten as a filtered list**: the raw spec made it a keyword search
  (`document_list{}` returned nothing) with `pagination.default_limit=20` and an owner scope.
  It is now `search.filtered_list` over a `filter` of optional clauses — `title_search` /
  `q` substrings, `archive_serial_number` exact, `correspondent` id — so an agent can list
  the whole table and narrow it without `page_size` gymnastics, and the obs hook measures it
  against `OBS_CAP`. `tag_list` / `correspondent_list` already expose `id`/`name` filters.

## carrier
- **`policy_doc` carrier = `{Document, content}`**: a document's `content` holds its full
  text, so a policy/rule document seeded as a `Document` row is where literal rule text lives.
