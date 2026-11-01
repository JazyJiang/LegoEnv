# Local workspace adapters

Import `packlib` and then `newspecs.register` to register the Vikunja, MantisBT, Outline, Listmonk, Cloudreve, Directus and Mastodon adapters. These adapters run declared relational state and tools in the local runtime; they do not deploy complete upstream servers.

The registration module supplies `add_users`, `tasks_board`, `tracker_project`, `wiki_collection`, `mail_lists`, `drive_tree`, `table`, and social-account helpers. Supply attributed dataset rows with explicit `src=` bindings, merge the world, and check observation coverage before emitting a task. `W.seed` replaces the entire named entity table, so retain the signed-in persona row when replacing an account entity.

New publication namespaces use the prefix declared in the current register. Read the actual tools and entities rather than inferring upstream functionality from a business-role alias. World policies are local task inputs and must be readable through the supported tools. The original strict admission and deterministic reference replay remain required. Historical external test reports and task translators are outside this installation-code subset; they are retained in the private source audit and are not inputs to this builder.
