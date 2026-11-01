# planka — patch ledger (workstream B onboarding)

Base: `pack/base_specs/planka.spec.json` (patched from
`apps/base_specs/planka.spec.json`). Register:
`pack/newspecs3/planka/register.py` → `capability_card.json`. The same facts are appended to the
top-level `smoke/PATCHES.md`.

## env / persona
- `env_id: planka` → `planka_ab` (the prefix merge_world derives comes off env_id; packlib asserts
  PFX["planka"] == "planka_ab"). Account entity `User` already has the persona at id 1 with a known
  password (`email`/`password`, role `admin`), so `sign_in(email, password)` works as-is.
- Content entities keep only the seeded rows the persona needs; a built pack seeds its own via the
  register helpers (`kanban_board`, `add_users`, `comments`).

## id-typed args that must accept integers
- planka's id args (`listId`, `projectId`, `boardId`, `cardId`, `userId`, `labelId`, `taskListId`,
  `customFieldGroupId`, `customFieldId`, `id`, …) are typed `id` in the spec. The runtime accepts
  integers for these (ids are seeded as ints), so no retype of the args was needed.

## guards that block a signed-in persona
- `create_*` and most read tools carry a BoardMembership precondition: the actor must be a member
  of the target board with `role=editor`. The persona (id 1, admin) is seeded as a board editor on
  every board via `kanban_board` (a `BoardMembership` row with `user_id=1, role=editor`), so these
  pass for the persona in a built pack.
- `list_users` / `create_user` / user-admin tools gate on `User.role in (admin, projectOwner)`.
  The persona is `admin`, so it passes; kept unchanged.
- `show_project`/`update_project`/`delete_project`/`create_board` gate on `ProjectManager` for the
  actor. The persona (id 1) is seeded as a project manager (ProjectManager rows with `user_id=1`);
  new projects created via `create_project` need a matching ProjectManager row to be writable —
  noted in the register NOTES so a builder/agent adds one when operating on a brand-new project.

## id-typed FK columns that update tools must write → retyped id → text (fk_to kept)
Runtime `Env._writable` excludes every `type=id` column, so `update.*` can never re-point an FK.
- `Card.list_id` (id → text): `update_card(listId=…)` moves a card between lists.
- `Task.assignee_user_id` (id → text): `update_task(assigneeUserId=…)` reassigns a task.

## exec_spec.set for renamed update args (cross-spec #2)
`ex_field_set` ignores dict-form `exec_spec.fields`; a renamed arg (`listId` → `list_id`) was
silently dropped. Every update tool's rename mappings are copied into `exec_spec.set`:
- `update_card`: list_id←listId, due_date←dueDate, is_due_completed←isDueCompleted
- `update_task`: is_completed←isCompleted, assignee_user_id←assigneeUserId
- `update_user`: is_deactivated←isDeactivated, default_editor_mode←defaultEditorMode, auto_logout_mode←autoLogoutMode
- `update_project`: background_type←backgroundType, background_gradient←backgroundGradient, is_hidden←isHidden
- `update_board`: default_view←defaultView, default_card_type←defaultCardType
- `update_board_member`: can_comment←canComment
- `update_checklist`: show_on_front_of_card←showOnFrontOfCard, hide_completed_tasks←hideCompletedTasks

## whole-list reads that cannot stay under 12k (add a filter arg)
`list_projects`, `list_users`, `list_webhooks`, `list_notifications` had no filter (whole-table
reads; blow past the 12k observation cap as the table grows). Added a `search` substring filter
arg (on `Project.name`, `User.name`, `Webhook.name`, `Notification.type`) to each, so the register's
obs hook (and a real agent) can scope them:
- `list_projects(q?=search)` / `list_users(search)` / `list_webhooks(search)` / `list_notifications(search)`.
The obs hook calls `list_projects`/`list_users`/`list_cards` per seeded board under 12k.

## what could not be made to work
- There is no real "move card" tool distinct from `update_card`; moving a card is done by
  `update_card(id, listId)` (board is fixed and cannot change). Cross-board moves are out of scope.
- `Attachment`/`UploadedFile` have no create tool (only `update_attachment`/`delete_attachment` and
  `delete_background_image`); attaching a file to a card is not scriptable from the spec's tools —
  noted, not fabricated.
- `delete_attachment` takes only `id`; there is no create, so attachments seeded per card are the
  only ones that exist.
