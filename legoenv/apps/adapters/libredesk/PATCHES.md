# libredesk base-spec patches (pack/base_specs/libredesk.spec.json)

Built from `apps/base_specs/libredesk.spec.json`
by `pack/newspecs3/libredesk/build_base.py`. Mirrors the cross-spec fixes in `smoke/PATCHES.md` plus libredesk-specific
link/guard/scoping fixes. Seeding is via `pack/newspecs3/libredesk/register.py`.

- **env_id `libredesk` → `libredesk_ab`**: ignite's merge prefix is the slug of `env_id`; packlib asserts
  `merge().pfx[app] == PFX[app]` (`libredesk_ab`). All existing bases carry the `<app>_ab` env_id.
- **persona account**: `User` id 1 is already `type=agent, enabled=true` with `email/password` — the `user_login`
  tool's `verify` and precondition (enabled agent by email) resolve to it; World rewrites the email/password to the
  running persona like the other bases.
- **whole-list reads cannot stay under 12k** → added a narrowing text arg so agents can scope them:
  - `conversation_list_all` gained `q` (subject substring filter) — was an unfiltered whole-table dump.
  - `contact_list` gained `q` (email substring filter) — was a paged but unfiltered whole-table dump.
- **`conversation_get_messages` ignored its `uuid`** and returned every message of every conversation. Rewrote it as a
  filtered list scoped to one conversation: `conversation_id == $ref(Conversation where uuid=$arg)` + optional
  `private` filter.
- **`conversation_get` owner scope removed** (`scope.owner_col=contact_id` meant a signed-in agent fetched nothing —
  conversations belong to contacts, not the agent session). Dropped so any conversation is fetchable by uuid.
- **`conversation_send_message` wrote orphaned messages**: raw `set_on_create` had no `conversation_id`, so every sent
  message was inserted with `conversation_id=NULL` (NOT NULL at runtime) and never appeared in the thread. Added
  `conversation_id = $ref(Conversation where uuid=$arg cuuid)` and `text_content = $arg content` to `set_on_create`.
- **literal compiler placeholders in `set_on_create`**: dropped string values that start with `<` / `(` (the runtime
  writes them literally and they corrupt new rows), matching the outline/misskey `'<...>'` fixes in `smoke/PATCHES.md`.
- **id-typed args accept integers**: `contactnote_create(id=3)`, `conversation_create(contact_id=3, ...)` and the
  upsert `key` lookups (`conversation_update_status/priority/assignee` by `uuid`) all resolve ints against the seed's
  integer ids — no retype needed; seeds keep integer ids.
- **guards that block a signed-in persona**: all agent write tools gate on
  `requires_auth` + a precondition that `User.id == actor.id AND type == agent`, which the persona (id 1, agent)
  satisfies after `user_login`. The only owner-preconditioned write (`chat_sendmessage` = contact side, requires the
  contact actor to own the conversation) is intentionally left as-is — it is the contact-facing widget, not an agent
  flow.

## Deliberately not patched (noted in the onboarding report)
- `chat_*` tools (widget/contact path) and the report/AI/automation bulk-read tools are outside the kinds this card
  claims; no agents-with-one-tool-per-action gap was found for the helpdesk reply/update/note kinds.
