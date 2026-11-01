# App integrations

This page covers the app adapters available to skeletons and the check that replays
the per-app examples.

| Item | Count | Location |
|---|---|---|
| Apps in the generation vocabulary (32 baseline + target apps) | 212 | `skeleton/vocab.json`, `apps/base_specs/` |
| Per-app adapter modules (including 13 earlier registrations) | 193 | `apps/adapters/<app>/` |
| Target apps with an onboarded adapter and a reference example | 180 | `app_examples/` (not in this repository) |

New apps are compiled into server atoms by the [server-atom compiler](compiler.md).

## Capability cards

Each adapter has `register.py` and `capability_card.json`, indexed in `apps/APPS.md`.
A card defines the supported kind spellings, the real tools behind each kind, the
login arguments and the policy carriers. `login: null` means no login call;
`carriers: {}` means the app cannot hold a policy document, and a combination of
apps needs at least one real carrier. Adapters run the declared operations in the
local runtime and do not deploy the upstream server; each card lists its
`known_limitations` (for example, Reactive Resume does not implement the full
pipeline timeline).

## Reference examples

Each example (`app_examples/<app>/` with `task.json`, `spec.json`, `skeleton.json`)
passes strict admission and reference replay from inline state;
`app_examples/packs.tsv` lists all 180. 31 were built by isolated DeepSeek/Claude
Code builder sessions and PrestaShop and FileGator were written by hand from their
web skeletons and real source CSV; the other 147 come from the original builds.
Building new worlds needs the source datasets.

```bash
python tools/check_app_increment.py --root /path/to/tree --out /path/to/new-dir --workers 4
```

`--root` must also contain `app_examples/` and `APP_QUALIFICATION.json`. The check
runs the 193 onboard checks, strict validation of the 180 skeletons and the 180
reference replays, and fails if any input file changes. It makes no model requests.
`--replay-one <app>` replays one example.
