# MINING BRIEF: mine real-world business-automation scenarios into skeleton_spec v2

You are mining ONE domain: `{DOMAIN}`. Goal: `{N}` distinct, realistic scenarios in which an operations person applies a written
business rule to a set of records and produces per-record actions plus a summary, written as `skeleton_spec v2` JSON files
that the LegoEnv builder can turn into training environments. Sources are the public internet; never an agent benchmark, its tasks or its wording.

## Read first
- `{WORKFLOW}/CONTRACT.md` (what a skeleton is), `{CONTRACT}/skeleton_schema.json`, `{CONTRACT}/vocab.json` (the ONLY allowed values for
  apps / kinds / check_kinds / archetypes / carriers / domains; `app_role` tells you which real SaaS each onboarded environment stands in for),
  and up to 3 files from `{WORKFLOW}/examples/` if that directory exists.

## Where to look (mix them; <= 3 scenarios from any single page)
- Public automation template galleries: n8n.io/workflows, zapier.com/templates and zapier.com/apps/<app>/integrations, make.com/en/templates,
  Microsoft Power Automate template gallery, IFTTT, Pipedream, Workato recipes.
- Vendor help centers that show automation recipes: HubSpot workflows, Salesforce Flow / assignment rules, Zendesk triggers, Freshdesk,
  Pipedrive, Monday/Asana rules, QuickBooks/Xero rules, Greenhouse/Lever, Gusto/BambooHR.
- Process / SOP libraries: process.st, Tallyfy, SweetProcess, Notion template gallery (ops/finance/HR), public university and city
  procedures (procurement thresholds, expense policies, leave policies, vendor onboarding, incident escalation).
- Public company policies: expense reimbursement, purchase approval, discount approval, credit hold, SLA/escalation, refund policy,
  data-retention/compliance checks, onboarding/offboarding checklists.

## What one scenario must contain
1. A business rule that selects some records and excludes look-alikes (that is the rule atom): threshold / exclusion / deadline / tiering /
   approval chain / budget / reconciliation / compliance flag. Write `rule_shape` ABSTRACTLY: which kind of column or condition selects
   records and what happens to them, no company/product/person/place names, no literal thresholds or dates. `has_exception` = the rule has
   an override clause (hold, opt-out, already handled, VIP, manager override...).
2. Where the rule text will live in the world: `carrier` (policy worksheet / policy e-mail / notes field on a record / wiki doc / card description / pinned chat message).
   Pick one the chosen apps can host (`vocab.carriers`).
3. The deliverables (deliverable atoms): 1-3 actions on 1-3 apps. **Apps come from two pools**: (a) the onboarded apps in `vocab.apps`; then `kind` MUST be listed for that app in `vocab.kind_tools`; (b) ANY other spec in `{CONTRACT}/spec_tools.json` (compiled open-source apps that are not onboarded yet; pick business-relevant ones from `{SCREEN}`, relevance >= 2, e.g. an HR suite for HR, an invoicing or ledger app for finance, a helpdesk for support, a document-assembly app for legal); then the atom must also carry `"tools": [<write tool names from that spec>]` that realize the kind, and a rule whose carrier lives on that app must carry `"carrier_field": "Entity.field"` (a real entity and text column from spec_tools.json). Prefer pool (b) whenever the scenario's real system is not among the onboarded stand-ins: those choices tell us which specs to onboard next. Use the release slug as the app name.
   Map the source's SaaS to our stand-in through `app_role` (Gmail->stalwart, Sheets/Excel/Airtable->budibase or directus, Slack/Teams->zulip,
   Salesforce/Pipedrive->espocrm, HubSpot->espocrm_hs, Google Calendar->gladys, Zoom->openmeetings, Calendly->easyappointments, DocuSign->opensign,
   Asana/Trello/Monday->vikunja, Jira->mantisbt, Notion/Confluence->outline, Mailchimp->listmonk, Twitter/LinkedIn posts->mastodon/misskey,
   Drive->cloudreve, Zendesk/Intercom/SMS->chatwoot, ChatGPT->librechat). Apps that only hold the policy text still count as apps.
   `pos` = how many records typically get the action (2-12 for per-record fan-out, 1 for a summary), `neg` = distractors + invariants (1-10).
   `check_kinds` from `vocab.check_kinds`: to what precision the action is checked (address + body terms, exact cell value, event time...).
4. `chain`: 3-4 abstract steps (read carrier -> scan records -> per-record actions -> summary), `n_intents` = number of deliverable atoms,
   `n_distractors_min` 2-4, `predicate_budget` = max(8, sum(pos+neg)), `domain` = `{DOMAIN}`, `source` = "web:<url>",
   `skeleton_id` = `mine_{DOMAIN}_NNN` (NNN = 001...). Optional `dataset_hint`: leave empty (the builder picks real data).

## Diversity requirements for the batch
All 8 archetypes appear; at least 3 carriers; at least 10 distinct app combinations; at least 6 distinct kinds; no two scenarios with the
same (apps, kinds, archetypes, rule_shape gist). Prefer scenarios where the rule has 2-4 clauses and natural look-alikes exist.

## Deliver
- `{OUT}/mine_{DOMAIN}_NNN.json` one file per scenario.
- `{OUT}/SOURCES.tsv`: `skeleton_id<TAB>url<TAB>one line: what the source describes`.
- Run `python3 {CONTRACT}/validate_skeleton.py {OUT} --strict` and fix every FAIL before finishing; the last line must read `{N}/{N} valid`.
- Final message (<= 12 lines): counts per archetype / carrier / app combo, how many sources, anything you could not express with the vocabulary
  (name the kind or carrier you wished existed; that is useful to us).
