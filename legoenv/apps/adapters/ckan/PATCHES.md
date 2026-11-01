# CKAN onboarding notes

The base spec is derived from the compiler release by `make_base.py`. It keeps a single sysadmin account with id `1`, removes demo catalog data, and strips compiler-only evidence fields. No runtime or shared pack library changes are required.

Validated writes:

1. `package_create` creates a public dataset when `private=false`; its reply contains the generated `Package.id`.
2. `package_patch(id, private, notes, ...)` persists supported scalar metadata and visibility changes on an existing dataset.
3. `resource_create(package_id, url, name, format)` attaches a resource to an existing dataset. A fresh dataset's generated id can be passed as `package_id` in a later call.

Tool and observation boundaries:

- `package_package_search(q="")` returns an empty list even when datasets exist. Use `package_package_list(limit)` to discover catalog entries, then `package_show(id)` for full notes. A nonempty query searches datasets.
- `package_create` advertises `resources` and `tags` arguments, but its compiled write spec does not persist them. `package_patch` likewise does not persist nested resources or tags. Use `resource_create` for resource writes.
- `package_patch` and `package_show` resolve a seeded or returned dataset `id`; do not assume a name works as an id. The generated id is an integer in this runtime even though the collected CKAN entity labels its id column as text. The tested FK path from that generated id to `Resource.package_id` succeeds.
- The runtime-generated successful `sign_in` response contains a short Chinese confirmation string. All CKAN package content, tool descriptions, policy text, and capability-card content in this base spec are English; changing this login response would require a shared runtime change outside this onboarding scope.
- The smoke observation reads are 750 characters for `package_package_list` and 178 for `resource_resource_search`, both below the 12,000-character cap.

Validation on 2026-09-25: `onboard_check.py ckan` reported `ONBOARD ckan PASS`, replayed one login plus three writes, satisfied three positive predicates and one negative predicate, and ran `accept.py --strict` successfully. The generated smoke pack is cleaned by the checker.
