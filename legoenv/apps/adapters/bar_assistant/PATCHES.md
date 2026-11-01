# Bar Assistant onboarding notes

`make_base.py` derives the base spec from the compiler release, keeps one operator plus the required bar-type and role rows, and removes unrelated demo content. The task builder seeds bars, admin memberships, ingredients, and shelf links per pack.

The collected `bar_shelfbatchadd` route calls `insertOrIgnore` on `bar_ingredients`. The release spec instead labelled it an update with no row key, so it could not represent an absent ingredient entering the shelf. This base spec maps one `id` (bar) and one `ingredient_id` to a `BarIngredient` create with the real unique pair. `bar_shelfbatchdelete` retains its composite-key delete. Both tools require an authenticated owner/admin membership. The unused `ingredients` batch-list argument is hidden because this runtime tool handles one ingredient per call.

The release `ingredient_index` tool used keyword ranking even though its normal no-query call is a bar-scoped list. It returned zero rows for five seeded ingredients. The base spec now lists ingredients by `bar_id`; the smoke reads all five ingredients and three existing shelf links. Observation sizes are 503 and 162 characters, below the 12,000-character cap.

The simulator's create action rejects a duplicate shelf pair, whereas the source route's `insertOrIgnore` is idempotent. Builders should select only absent ingredients for `bar_shelfbatchadd`; `mine_hospitality_027` explicitly says this. `mine_hospitality_026` explicitly selects stocked ingredients for deletion. These tools change shelf membership, not counted quantity or a particular menu item's status.

On 2026-09-25, `onboard_check.py bar-assistant` reported `ONBOARD bar-assistant PASS`. The witness used two shelf deletes and one add; three positive predicates and two negative/invariant predicates passed, followed by `accept.py --strict`. No global runtime or pack-library file was changed. The base spec and task text are English; the shared runtime's login-success response remains localized in Chinese.
