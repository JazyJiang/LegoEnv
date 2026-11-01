# SuiteCRM local onboarding

`make_base.py` copies the compiler release spec, changes `env_id` to `suitecrm_ab`, and adds a filter to the existing `module_getlist` search so its required `module` argument restricts `SugarBeanModule.module_name`. The release spec previously returned records from every module for every `module_getlist` call. No tool is added.

For the smoke world's persona, `smoke_seed` restores the first user's `user_hash` to the generated world password. The shared `World` helper substitutes the username first, and the release password `pw-ada` contains that username; otherwise the broad text replacement would turn it into `pw-<persona>` before the password replacement runs. This is a local seed correction, not a change to SuiteCRM authentication.

The strictly supported delivery surface is deliberately narrow: `alert_create` creates an internal CRM alert for the signed-in user, and `alert_markasread` changes an existing alert's read state. The smoke checks two target writes and one unaffected reminder.

The release `module_create` ignores `data_attributes` and creates a bare `SugarBeanModule` row; `module_update` likewise does not apply business attributes. Quote-conversion tools do not faithfully copy quote lines or account data. This registration does not advertise those tools as account, case, invoice, or contract creation. The generic `SugarBeanModule.item_summary` carrier is suitable only for a small internal triage register seeded by the builder.
