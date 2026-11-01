# Motif Boundary Plan

## Role
Discover the independent business capabilities in one repository before any
Entity membership is assigned. Do not produce MotifInstances and do not try to
cover every Entity.

The next stage will independently verify your decisions and materialize Entity
membership. Your job is to separate retained business-capability boundaries
from excluded technical support before any full Entity grouping is attempted.

## Boundary Standard
A planned capability must have one real-world lifecycle anchor: a record a user
or external process independently creates, submits, approves, executes,
publishes, fulfills, or closes.

Independence means an independently meaningful **user or real-world outcome**,
not merely a software component that could be deployed as a standalone service.
Do not use "can be implemented independently" as sufficient reasoning when the
result is only authentication, configuration, storage plumbing, transport, or
another technical layer.

Apply a cross-repository reuse test: another repository's Motif should be able
to produce, consume, reference, or compose with this capability's business
records without importing the rest of this repository. This tests whether a
boundary is reusable; it does not turn a shared lookup/master record into a
business capability. A currency, UOM, status, category, account-tree node,
fiscal period, payment term, template, profile, or organizational grouping may
be referenced across repositories while still being support context.

- Two anchors that can be acted on and completed independently are two planned
  capabilities, even when they share a domain, FK edges, dataflow, or product.
- Planned capabilities need not partition anchor context. A parent business
  object may be named by more than one retained capability when another
  lifecycle is explicitly about it; shared context does not justify merging
  the lifecycles.
- Parent/line/detail, translation, attachment, status, and history records do
  not create separate capabilities when they only complete one anchor.
- Keep a structural container with the content/action that gives it meaning
  when neither is a complete user outcome alone. For example, a mailbox/thread/
  message hierarchy is one messaging capability; project/board/list/card is one
  board capability; album/track is one media catalog. Do not split one workflow
  into container, content, and processing layers merely because each has tables.
  In particular, session/topic/thread/message is one conversation capability,
  not separate conversation-container and conversation-content capabilities.
- Lookup dictionaries, settings, credentials, tokens, caches, indexes, joins,
  registries, and platform administration are not capability anchors.
- CRUD, validation, import, or delete methods on a table are not by themselves
  a lifecycle. Before retaining an anchor, require evidence of a business
  transaction, content/event lifecycle, independently completed user goal, or
  a stateful real-world record family. Do not emit one `*_management` capability
  for every maintainable master/configuration table.
- Generic user authentication, workspace membership, RBAC/permissions, API or
  OIDC credentials, provider/model catalogs, plugin/connector registries,
  notification plumbing, quota metering, and platform administration are
  support context rather than business Motifs unless one of them is the
  repository's primary real-world domain.
- Do not plan a broad `suite`, `platform`, or `full lifecycle` that combines
  conversation, task execution, content management, evaluation, verification,
  analytics, delivery, or administration. These are independent whenever
  another repository could implement one without the others.
- A coherent real-world dataset, a standard domain export, or genuine
  operational business records must be able to populate the capability. An
  application backup, configuration dump, credential export, tracing log,
  quota ledger, job queue, or device registry is not a grounding source merely
  because it contains rows.
- Selective omission is expected. Do not invent a capability for leftovers.

The planner does not assign all Entity membership. Do not place line items,
details, history, state, attachments, translations, or association rows into
`excluded_support` merely because they are not lifecycle anchors. The
materializer will decide whether those rows complete a retained capability.
`excluded_support` is only for entities that confidently represent a standalone
technical-support family.

Granularity calibration:

- Quote, order, shipment, invoice, and payment documents usually have distinct
  lifecycles. Keep each normalized document with its own lines/details rather
  than planning one broad commerce-fulfillment capability.
- Payroll execution does not absorb independently submitted benefit claims,
  tax declarations/proofs, gratuity administration, compensation awards, or
  withholding lifecycles merely because they affect final pay.
- Course catalog, assignment, submission/assessment, and gradebook are
  independently reusable education capabilities when their records exist.
- Issue handling should not absorb independently maintained release planning;
  issue-field lookup dictionaries are support rather than a third capability.

For every retained capability, classify its grounding basis as exactly one of:

- `common_public_dataset`: common public datasets cover the business records;
- `standard_domain_export`: an established domain format/export covers them;
- `real_operational_records`: organizations genuinely exchange or analyze
  these records independently of this application's implementation;
- `sensitive_real_records`: the records are genuine but uncommon or sensitive.

Do not retain a capability if its only plausible basis would be an internal
application export. Do not rename an internal table dump as an "operational
dataset". In particular, generic notification delivery, connector/provider
registration, quota accounting, tracing, background execution, device
registration, authentication, RBAC, and workspace administration are excluded
support unless they are the repository's primary real-world domain.

Use `repo_summary` as a weak inventory, Entity names and lifecycle/state fields
as semantic evidence, and `direct_operation_*` as strong but incomplete anchor
hints. `affected_operation_samples` and `relationship_context` are positive
clues for parent/detail ownership and cross-record workflows. They are not a
connectivity constraint: missing or sparse relationships never prove that two
records must be separated, and relationship density never proves that two
independent outcomes must be merged.

## Repository Evidence

```json
{{BOUNDARY_EVIDENCE}}
```

## Output Contract
Return one JSON object only. The two lists are mutually exclusive:

```json
{
  "retained_capabilities": [
    {
      "capability_id": "precise_snake_case_name",
      "goal": "one independently completable real-world outcome",
      "anchor_entities": ["one or more exact entities[].entity names"],
      "boundary_reason": "why another repository could contain a comparable business-record Motif without neighboring capabilities",
      "grounding": {
        "basis": "common_public_dataset | standard_domain_export | real_operational_records | sensitive_real_records",
        "family": "the concrete non-application-specific record family"
      }
    }
  ],
  "excluded_support": [
    {
      "entities": ["exact entities[].entity names that are clearly support"],
      "category": "authentication | platform_administration | configuration | integration_registry | observability | execution_plumbing | storage_or_join | other_support",
      "reason": "why these rows do not form an independently groundable business-record lifecycle"
    }
  ]
}
```

`anchor_entities` names must be exact supplied Entity names. They identify the
business documents/events that own a lifecycle, not all future core members.
`excluded_support` need not cover every unused Entity; it records only confident
support families. Return at most 16 excluded groups with at most 24 exact,
non-repeated representative Entities per group. Do not repeat an excluded
Entity across groups. Return no prose or markdown. Before answering:

1. check that no retained goal contains independently completable outcomes;
2. remove any retained item whose reason only proves that it could be a
   standalone technical service;
3. reject any grounding family that is merely this application's own export;
4. ensure no Entity appears in both retained anchors and excluded support;
5. prefer omission over manufacturing a weak capability for leftover tables.
6. reject a plan dominated by singleton CRUD or lookup/master-data capabilities;
   consolidate real parent/detail lifecycles and omit support records instead.
