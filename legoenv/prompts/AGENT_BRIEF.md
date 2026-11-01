# Instance diagnosis and repair

Read only the files in this case directory. `task.json` contains the request, verifier and reference solution (`witness`), `spec.json` contains its
world and tools, and `s0.json` through `s7.json` are eight failed teacher attempts.
The original witness is part of the permitted zero-pass pack; the reference
diagnoses and repairs are withheld.

Determine the primary cause from the goal, world, recorded tool results and all
eight trajectories. Write `diagnosis.json` with `tid`, `category`, `cause`,
and `action`. Choose exactly one category: `verifier_bug`,
`task_data_environment_tool`, `task_data_or_tool`, or
`teacher_execution_failure`. `action` is `repair` or `no_change`. A
teacher mistake is not evidence that the task needs weakening; use
`no_change` only when the package is sound and the failed attempts contain
concrete execution or reasoning mistakes.

The episode interface may express package tools as `api_search` and
`api_fetch` HTTP calls. Treat successful recorded API results as real reads
and mutations. For each strongest episode, map successful mutations and the
persisted final state to the task's requested actions before calling it an execution
failure; a final verifier false can be a predicate false negative even when
every requested mutation succeeded. Different teacher-facing and local-runtime
tool names are not, by themselves, an execution failure. Conversely, a reference solution that replays successfully proves reachability only: it may contain hidden constants
that the public goal and world never reveal. Do not use witness-only facts as
requirements or as proof that the package is fair.

Before choosing a category, compare at least one strongest failed episode with
the verifier clause by clause. Distinguish:

- a business-valid completion rejected by an underivable, contradictory, or
  misaddressed predicate: `verifier_bug`;
- a public source or entity promised by the goal but absent or inconsistent in
  the world/tool surface: `task_data_environment_tool`;
- an intrinsically ambiguous or impossible task/data/tool combination not
  localized to one environment artifact: `task_data_or_tool`;
- visible teacher mistakes despite a sound, fully discoverable package:
  `teacher_execution_failure`.

For `repair`, write `repaired_task.json` containing `goal_nl`, `env_id`,
`verifier`, and a corrected `witness` (a list of `{tool,args}` calls), and
optionally `repaired_spec.json` if the world or tool definition must change.
Preserve the business request. Change only the smallest broken part; retain
checks for requested actions and important exclusions. Never replace the
verifier with a constant or make it vacuously true. Do not copy a failed
teacher sequence as a witness without checking it.

Audit positive coverage as well as false negatives. Enumerate every branch of
the visible policy that selects an item and every action that branch requires.
A policy action remains required when it appears in a referenced public data
record rather than being repeated in the goal's prose. Build an action inventory
from the goal and every policy source, then require a positive verifier predicate
and a witness step for each action, including the requested owner, assignee,
lead, recipient, or parent relation. An unresolved placeholder such as `#{CH}` is
a public package defect; do not silently fill it from the original witness.
A negative predicate such as “no store credit” does not substitute for a
required alternate action such as creating a cash credit and replying. The
candidate verifier must require all requested positive work and preserve every
important exclusion.

For multi-branch policies, build a per-entity matrix before editing. For every
selected entity record: which branches select it, which status text each branch
requires, which status text is forbidden, which numeric field supplies each
amount, and which actions follow. A union of selected entities is not permission
to attach every branch's status or number to every member. Recompute public
formulas from their named operands exactly; do not add a customary zero clamp,
rounding rule, or display unit that the policy does not state.

For every selection and exclusion rule, identify each decision operand and its
public source. If the policy depends on applicant institution, conflict status,
principal investigator or another attribute that the task/world never exposes,
the intended target set is underivable even when the verifier and witness agree.
Do not infer the missing operand from the witness. Repeated episodes converging
on the same publicly supported alternative are evidence of this kind of data
gap; repair the smallest decision-relevant public field and keep the intended
actions and exclusions unchanged.

Audit every cross-system join. The entity identifier or mapping used to move
from one system's record to another must be present in the public task or world.
Similar-looking identifiers in different namespaces are not a mapping. If an
action depends on an unstated join, repair the smallest public data/mapping
artifact and update the verifier and witness consistently; do not preserve a
witness-only association.

Treat a revision as a semantic diff. Before emitting it, list every verifier
clause removed or weakened relative to the input candidate. Keep each sound
positive, negative, preservation, and exclusion clause. Adding a missing
positive action does not justify deleting a compatible negative constraint;
for example, a cash-credit branch may require both a cash-credit document and
zero store-credit documents. Remove or weaken a clause only when the public
goal/world evidence specifically shows that clause is broken, and explain that
evidence in `diagnosis.json`.

Text checks should enforce semantic atoms rather than accidental surface form.
Unless the public task requires exact formatting, do not require one word
order, punctuation mark, Unicode dash, or a label in one specific field. For
example, require both “v3” and “addendum” separately instead of the contiguous
literal “v3 addendum”; accept stable opportunity-name components across dash
styles; and ground an email by its exact recipient plus the required
appointment/date content without demanding that its body repeat a company name
already present in the subject or recipient. Keep content checks strong enough
to prove the requested action occurred.

When repairing an underivable exact timestamp, keep every public scheduling
constraint and translate its wording exactly. `before X` requires a strict
`lt X`; `after X` requires `gt X`; `by X` or `no later than X` permits
`lte X`; and `on or after X` permits `gte X`. A newly created event must
not be before the task's stated current date. Preserve any public duration,
participant, calendar, title, or status constraints. If no upper deadline is
stated, do not invent one. Apply the same rule to other hidden constants:
remove only the underivable constraint and retain the public semantic
boundary.

When the goal requires one summary naming every acted-on item, require all
items and every requested paired attribute (for example its budget-line code)
in the same message predicate, bind any requested aggregate count to that same
message, and enforce the relevant-message cardinality when the goal says one.
A top-level OR over item names proves only one item was mentioned; one complete
message predicate alone also does not rule out extra partial summaries. Preserve
the correct route and sender along with the complete same-message content. Bind
a required value to the artifact named by the goal: a ground required on a DMS
evidence note is not covered by checking that word on an accounting invoice
note.

Honor the identifier form requested by the goal. If an e-mail must name a
proposal, require a stable public proposal-title atom in the submitted e-mail;
the numeric issue ID alone is insufficient. Negative communication constraints
must cover any recipient unless the goal or policy limits the forbidden action
to a named recipient.

When the goal says to leave every other item untouched, protect each public
state surface that the requested workflow could mutate. Preserving only a
related card is insufficient if the source row's status, numeric result or note
can still change while passing. Use same-record predicates for the original
fields of every excluded item, and preserve its related card, message and other
workflow artifacts when those are also in scope. If the task requires a person
or relation without prescribing a storage field, accept that semantic atom in
the natural fields of the same artifact (for example a Goal's name or
description); do not require one field solely because the witness used it.

Do not stop after repairing the first false-negative or hidden literal. Re-audit
the entire goal, every visible policy rule, every positive branch, every
exclusion and every mutable source record against the revised verifier and
witness. The revision is not ready merely because the supplied witness passes.

Before emitting a repair, construct and run or reason through all four of these
adversarial counterexamples. Each must make the revised verifier false:

1. Split required atoms across two records, such as the right category on one
   bill and the right note text on another, or three required phrases across
   several comments. Required atoms for one action belong in one selected
   artifact predicate and must be bound to the exact public entity relation.
2. Duplicate a required output or add a partial second summary. If the goal says
   one, enforce exact cardinality over every relevant artifact, including a
   message that mentions any selected item rather than only a message that
   contains all selected items.
3. Mutate an excluded item using generic text, a different destination, a wrong
   bucket/status, deletion, or a duplicate replacement. Text-specific absence
   is insufficient for an item the goal says to leave unchanged; preserve its
   exact current record and relevant relations.
4. Mutate a stable field of a selected source record while separately creating
   the requested output. Preserve all non-target source fields and current-world
   relations. Account for artifacts already present in the seed: moving an
   existing card is different from creating another card, and a seed row that
   already satisfies one atom must not hide a missing requested mutation.

If a visible task and a referenced public policy contradict each other, or a
required recipient/relation is absent from the public world, repair the smallest
public instruction or data mapping as well as the verifier and witness. Do not
silently retain a private witness choice. If that public defect cannot be made
coherent within the allowed files, record it as unresolved instead of weakening
the requested workflow.

You may inspect the local runtime in `runtime/` and use
`python3 check_candidate.py .` to replay your proposed witness, require a
false initial verifier and a true final verifier, and inspect errors. This is
an offline smoke test. It does not establish business equivalence, strict
acceptance, or teacher success. Run it after each change. Record any unresolved
issue in `diagnosis.json` rather than inventing a successful repair. Read
large episode files selectively; avoid dumping all eight into one model
context.

The files in this directory are the entire allowed input. Do not search the parent project, shared disk, reference fixes,
audit labels, `repair.json`, or other cases. Do not alter `task.json`, `spec.json`, or
the eight teacher episodes.
