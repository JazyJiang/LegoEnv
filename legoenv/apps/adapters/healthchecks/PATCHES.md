# Healthchecks base-spec patches

- Derived only the isolated `smoke/pack/base_specs/healthchecks.spec.json` from the compiler release; the release spec and global runtime were not changed.
- Set `env_id` to `healthchecks_ab` for namespaced world merging.
- Renamed the `sign_in` input from `password_hash` to `password`, matching the pack runner's login call. The verifier still compares against `User.password_hash`.
- Renamed `check_create(project)` to `check_create(project_code)` in the input schema, required guard, precondition arguments and bind metadata. Its `set_on_create.project` now resolves the external `Project.code` to the internal `Project.id` through a `$ref`. This avoids the runtime's same-named-argument merge taking precedence over `set_on_create`.
- Required a unique `slug` for check creation and persisted it as both `code` and `badge_key`. The release spec marks these fields with `uuid4` defaults, which this isolated simulator does not materialize. This deterministic surrogate makes a newly created check addressable by subsequent tools; it is a local simulation choice, not the production service's secret generation.
- The smoke seeds a project policy and four check rows, then replays timeout update, pause, resume and create actions, plus a negative unchanged-check assertion.
