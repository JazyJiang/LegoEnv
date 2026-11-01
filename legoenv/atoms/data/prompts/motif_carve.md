# Motif Carve

## Role
You are given one repository's business evidence: entities, columns, observed
operation hints, known foreign-key edges, and hub hints. Identify repository-
local MotifInstances.

A MotifInstance is the **smallest complete business capability** that:

1. has one primary user goal or real-world outcome;
2. is complete enough to populate and use with real data; and
3. could plausibly be implemented as one comparable capability by an
   independent repository.

Each emitted MotifInstance will later be compared with MotifInstances from
other repositories and normalized into a cross-repository MotifArchetype.
Choose semantic membership carefully. Later deterministic code will project
real relationship facts and annotate connectivity risk, but it will not repair
a mixed business boundary.

This is a **selective carve, not a partition of the repository**. It is normal
and desirable for many input entities to remain unassigned. Collector retains
those entities elsewhere. Do not create Motifs merely to cover leftovers or to
maximize entity coverage.

## Boundary Rules

### 1. Use one primary goal, not one broad product area
All core entities must contribute to the same primary task, object lifecycle,
or user-visible outcome. Being in the same repository, domain, product module,
or FK-connected component is not enough.

Start from **lifecycle anchors**, not from connected table groups. A lifecycle
anchor is a real-world record that a user or external process independently
creates, submits, approves, executes, publishes, fulfills, or closes. Detail,
history, and association rows may complete one anchor's lifecycle. Two anchors
that can each be acted on and completed independently normally define two
Motifs, even when one consumes the other or both belong to one product module.

Use the **cross-repository reuse test**:

- Imagine an unrelated repository implementing this capability.
- Could its corresponding MotifInstance reasonably cover the proposed core as
  one feature or workflow?
- Can one precise capability phrase describe the whole core without joining
  independent outcomes with `and` or `or`?
- If two subsets could independently correspond to different reusable
  capabilities in other repositories, split them here.

Apply this test at **every size**. A 20-entity group can be too broad, and a
one-table group can be too narrow or not a capability at all. Entity count is
only a reason to re-check the boundary; it is never the boundary itself.

Do not merge capabilities merely to create more connections. Dependencies
between distinct capabilities remain relationships between Motifs later.

### 2. Keep a complete lifecycle; do not fragment by table
Smallest does not mean table-sized. Keep normalized parent/child/detail records
together when they jointly realize one outcome, for example Order + LineItem or
Album + Track + Artist. Optional implementation depth, extra detail rows, or a
missing operation hint does not by itself require a split.

For a singleton or a two-to-three-entity proposal, explicitly ask whether its
anchor is an independently useful business object/event that another repository
could implement and that a task could meaningfully create, update, query, or
complete. Keep it when the answer is yes, such as a bookmark, calendar event,
saved playlist, purchase suggestion, or moderation report. Omit it or attach it
to its owning lifecycle when it is only a lookup row, option/type dictionary,
UI setting, integration credential, token, internal counter, or association
record. Do not turn every surviving schema table into a named capability.

A local entity may legitimately support more than one business capability.
Reusing it in different Motif contexts is preferable to merging independent
capabilities merely to avoid overlap.

Dataflow does not erase a task boundary. An upstream record that is created,
reviewed, approved, or maintained through its own user workflow remains a
separate capability even when a downstream calculation consumes its values.
For example, benefit claims and tax declarations may feed payroll calculation,
but administering those records is not payroll execution.

Treat this as a hard document-lifecycle invariant: a calculation/execution
Motif must not absorb another application, claim, declaration, proof,
certification, settlement, or rule-administration lifecycle merely because the
calculation reads its amount or status. Phrases such as "execute X including A,
B, and C" do not establish one goal when A, B, and C are independently created
or approved business records.

### 3. Treat FK as evidence, not as the semantic boundary
Known FK is trustworthy positive structural evidence. Missing FK is unknown
evidence because Collector/ORM extraction can be incomplete.

- Do not require every core entity to be FK-connected.
- Do not keep unrelated lifecycles together merely because an FK connects them.
- Never invent a factual edge. `core_edges` and `shared.via` may name only real
  input FK edges. Semantically related members may remain together without a
  known edge; leave that edge absent.

### 4. Keep core focused on real data, not implementation inventory
`core` is the real-world body a principal dataset or coherent export should
populate. Include entities whose rows carry the capability's objects, events,
state transitions, or necessary parent/child detail.

Do not put an entity in core merely because it is referenced by the core.
Trim entities that mainly represent implementation mechanics, including pure
join tables, caches, search indexes, blobs split only for storage, audit/log
plumbing, sessions, permissions, feature flags, background jobs, registries,
and configuration enumerations with no independently useful real-world rows.

Names such as `*Map`, `*Link`, `*Data`, `*Fulltext`, `*Cache`, `*Setting`,
`*Token`, and `*Cookie` are warning signals, not automatic rules. Inspect their
columns and operations. Omit storage/linkage machinery instead of turning it
into another Motif. Generic authentication, account preferences, API access,
and platform administration are likewise out of scope unless they are the
repository's actual real-world business domain rather than support for it.

An essential reusable owner or hub such as User, Customer, Organization, or
Account belongs in `shared`, not `core`, when it is grounded separately and
joined to the capability by key. A domain-specific parent is not automatically
a shared hub; judge whether it is part of this capability's real data.

### 5. Groundability must be internally consistent
Emit only coherent real-world capabilities that can in principle be populated
from real data **independently of this application's internal backup**. A
configuration dump, auth database, permission export, cache snapshot, or job
log does not become a grounding dataset merely because it can be exported.
Interpret `groundable` as follows:

- `high`: a common public dataset family or standard export can populate most
  of the core and preserve its main relations;
- `med`: a coherent real dataset/export plausibly exists, but coverage is less
  common, may require a small number of complementary sources for optional
  detail, or is domain-specific;
- `low`: the capability is still coherent and structurally groundable from
  real records, but public data is rare, sensitive, or difficult to obtain.

`low` does **not** mean "not groundable". Skip pure software abstractions or
mixed groups for which no coherent real dataset/export could exist. Never emit
a group whose own rationale says it is incoherent, merely a mix of features,
pure infrastructure, or impossible to ground.

A principal business-record dataset must cover most of the core. Complementary
sources may enrich optional detail; they may not be used to justify combining
independent lifecycles. If the only plausible source is "this application's
configuration export", skip the group.

## Granularity Calibration

These examples are normative boundary calibrations. Apply the same semantic
tests to analogous domains; do not copy their names mechanically.

### Keep together

- `Artist + Album + Song`: one music catalog.
- `Issue + Comment + Attachment + IssueHistory + Dependency`: one issue-case
  lifecycle, even when a repository stores comments or history in several
  child tables.
- `PayrollRun + Payslip + SalaryLine + SalaryStructure`: one payroll-execution
  lifecycle.

### Split independent capabilities

- `Artist + Song + Queue + Room`: catalog content versus player/session
  runtime. The shared music domain does not make one capability.
- Issue handling versus product/version/release planning: a real release-
  planning workflow is separate when it has release plans, milestones, or
  version actions and its own outcome. Mere issue-field lookup dictionaries
  such as status, severity, platform, or component configuration are not by
  themselves a groundable release-planning Motif; omit them when they only
  configure issue records.
- Payroll execution versus benefit claims, tax declarations, or gratuity
  administration: when these appear as their own applications, claims,
  declarations, proof submissions, rules, ledgers, or approval records, carve
  them separately from payroll execution. Payroll execution contains payroll
  runs, payslips, salary structures/components, and the detail/correction rows
  needed to calculate a pay result. Benefit administration contains benefit
  applications/claims/ledgers. Tax declaration contains tax declarations,
  exemptions, proof submissions, and tax rules. Gratuity or other special
  compensation may form another capability when it has its own rules and
  lifecycle. A final pay calculation consuming their values is a dependency,
  not proof that all are one Motif. Missing operation hints do not erase an
  independence visible in entity and column semantics.

  **Invalid broad payroll carve:** `payroll_execution` containing employee
  benefit applications/claims/ledgers, tax exemption declarations/proof
  submissions, gratuity rules/payments, salary-withholding cycles, and special
  compensation administration merely because all may affect final pay.

  **Required boundary:** keep payroll runs, payslips, salary structures and
  components, and calculation/correction detail in `payroll_execution`; emit
  independently represented benefit, tax-declaration, gratuity, withholding,
  or special-compensation lifecycles separately when they are groundable, or
  omit them when they are not. Do not return the invalid broad carve and do not
  justify it with the word `including`.

### Cross-domain lifecycle calibration

The following are generic boundary patterns, not repository-specific names:

- `Quote -> Order -> Shipment -> Invoice -> Payment` is a business dataflow,
  not automatically one Motif. Each document with its own creation/status
  lifecycle is independently reusable. Keep its normalized line/detail rows
  with that document and express dependencies between Motifs later.
- `Course -> Assignment -> Submission -> Gradebook/Rubric` may form several
  independently usable education capabilities. A course catalog, assignment
  workflow, submission/assessment workflow, and gradebook should not be merged
  merely because they share students and courses.
- `Lead/Contact`, `Campaign`, `Email/SMS delivery`, `Form submission`, and
  analytics are distinct marketing capabilities when each has its own records
  and actions. Never emit an entire marketing or product suite as one Motif.
- In messaging systems, room/message membership, federation transport, device
  synchronization, push delivery, user directory, presence, and usage
  analytics are not one lifecycle merely because they participate in message
  delivery.

Conversely, do not split a single document only because it has status, line,
history, attachment, translation, or normalized value tables. Those remain
with the anchor when they have no independent outcome.

### Trim rather than split into another Motif

- A pure CC mapping, attachment blob store, search index, ACL mapping, cache,
  or framework registry is implementation structure, not a standalone business
  capability.
- In an issue tracker, keep real case records such as Issue, Comment,
  Attachment, History, Dependency, or Duplicate. Omit physical linkage and
  storage helpers such as CC maps, group maps, full-text rows, attachment blob
  splits, tag-link rows, and inclusion/exclusion maps unless their rows carry a
  distinct real-world event required by the primary goal.

Large cores are not automatically wrong, but they demand another boundary
check. A broad label such as `suite`, `platform`, `system_operations`, or
generic `management` is not enough to justify many independent lifecycles.

## Input
The following JSON object is the available evidence for the current repository.
Judge this object, not the calibration examples above.

### Evidence field meanings

- `repo_summary`: Collector's weak capability inventory. It helps locate broad
  areas but does not define Motif boundaries.
- `entities[].entity`: exact local Entity identity.
- `entities[].column_count`: full source column count.
- `entities[].columns`: at most 25 salience-selected column names. They favor
  keys, lifecycle state, enums, references, and business values; omission is
  not evidence that a field does not exist.
- `entities[].primary_key` and `enum_fields`: compact row-grain and lifecycle
  evidence. Enum values describe data states; they do not by themselves make a
  standalone capability.
- `entities[].direct_operation_*`: observed operations whose owner resolves to
  this Entity. These are strong but incomplete lifecycle-anchor hints.
- `entities[].operation_count`: number of observed operations that affect or
  provide this Entity, including direct operations and side effects.
  `affected_operation_samples` shows a bounded sample after direct operations
  are removed. Shared operation names show dataflow and must not automatically
  merge lifecycles.
- `edges`: only normalized FK/reference edges whose two endpoints resolve to
  supplied Entities. They are factual positive evidence.
- `relation_quality.unresolved_reference_count`: extracted references whose
  target is absent or ambiguous. They are not edges and cannot justify a member
  or invented relationship.
- `principal_hints`: likely owner/actor Entities such as User or Account.
  Consider them for `shared`, not automatically for `core`.
- `lookup_hints`: likely lookup/reference Entities such as Status or Category.
  This is an advisory name hint; retain a lookup only when real rows are needed
  for the focused capability, and do not promote a lookup table into a Motif by
  itself.

```json
{{REPO_GRAPH}}
```

The repository name is weak domain context only. Entity names, columns,
operations, and relationships are the decision evidence.

## Required Decision Flow
Perform these checks before producing JSON:

1. Inventory real-world content/events, reusable hubs, lookup/configuration,
   and plumbing.
2. Propose precise primary goals before grouping entities.
3. Identify the lifecycle anchor or tightly coupled anchor pair for every
   proposed group. If no such business-record anchor exists, omit the group.
4. Apply the cross-repository reuse test to every proposed group.
5. Apply the minimality test: split any independently useful and independently
   matchable sub-capability, while retaining required lifecycle detail.
   Specifically check whether a calculation has swallowed upstream
   application/claim/declaration/approval lifecycles.
6. Apply the same test to singleton and two-to-three-entity proposals. Reject
   table-sized lookup/configuration/plumbing fragments; keep genuinely atomic
   business capabilities.
7. Fix roles: focused `core`, separately grounded `shared`, and trimmed
   implementation entities.
8. Judge groundability using the definitions above; skip impossible groups.
9. Re-read every `why`. If it admits multiple unrelated outcomes, a mixed
   platform area, no coherent data source, or pure infrastructure, revise,
   split, or remove that output before answering.
10. Check every core entity against the stated goal. If the `why` cannot explain
   why an entity is needed for that one outcome, remove it or split the group.
   Do not place omitted entities into catch-all Motifs.
11. Final all-size audit: re-check every large, medium, small, and singleton
    proposal. No size band is exempt from either over-merge or over-split risk.

## Output Contract
Return a JSON array only. Each element is one MotifInstance:

- `core`: exact input entity names for the focused real-world body;
- `core_edges`: `[{child, parent, fk_col}]`, containing only known input joins
  internal to the selected core; deterministic code will re-project them;
- `shared`: boundary hubs as
  `[{entity, via:[{core_entity, fk_col}]}]`, using only real input links;
- `domain`: a broad business domain such as `media`, `commerce`, `calendar`,
  `mail`, or `devtools`;
- `kind`: a precise, normalized, snake_case, cross-repository capability name,
  such as `music_catalog`, `issue_case_management`, or `payroll_execution`;
- `groundable`: `high`, `med`, or `low` under the definitions above;
- `why`: one line in the form
  `Goal: <one outcome covering every core member>; Reuse: <cross-repo capability>; Grounding: <plausible business-record dataset family>.`

Do not emit extra prose or markdown.

## Final Discipline
One primary goal, one independently reusable capability, complete but minimal
real-world core, factual edges only, FK as advisory evidence, shared hubs at
the boundary, plumbing trimmed, and no rationale that contradicts the emitted
group.
