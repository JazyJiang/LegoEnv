# Motif Plan Materialization

## Role
Materialize final repository-local MotifInstances from a separately generated
capability boundary plan and the full repository evidence.

The boundary decision contains retained capability hypotheses and confidently
excluded support. It prevents broad one-shot grouping, but it is not permission
to emit one Motif for every retained hypothesis.

## Materialization Rules

1. Independently verify every retained hypothesis against the full evidence.
   The plan is a semantic proposal, not a required one-output-per-candidate
   partition. You may reject a retained hypothesis that has no genuine
   business-record lifecycle or whose grounding is really an internal
   application export. Do not output an empty placeholder for a rejected item.
2. You may merge planned candidates only when the planner fragmented one
   complete container/content or parent/detail lifecycle, such as session/topic/
   thread/message, album/track, or order/order-line. You may split one planned
   candidate when it mixes independently actionable documents or outcomes,
   such as quote/order/shipment/invoice/payment or payroll/benefit-claim/tax-
   declaration/gratuity. Never merge merely because candidates share a suite,
   domain, FK edge, or dataflow. Dependencies remain later relationships.
3. Omit a retained candidate when its records are generic authentication,
   workspace/RBAC administration, credentials, provider configuration, plugin
   or connector registry, quota metering, observability/tracing, background-job
   plumbing, device registry, cache, index, join, or settings rather than a
   groundable real-world business outcome.
4. `excluded_support` says that a family should not become its own Motif. It is
   not an absolute ban on Entity membership. Restore an excluded Entity when
   its supplied fields show that it is real line/detail/history/state data
   needed to complete a retained anchor, but never restore it merely to increase
   coverage.
5. Keep the normalized parent/line/detail, translation, attachment, state, and
   history rows needed to complete one planned anchor. A detail table is not a
   second Motif.
6. Do not force unplanned leftovers into a catch-all Motif. Selective omission
   is expected.
7. `core` contains the real-world data body for one capability. A principal
   such as User, Account, or Organization belongs in `shared` when a factual
   edge exists; generic principals do not become core merely because many rows
   reference them.
8. `lookup_hints` and name patterns such as `*Map`, `*Link`, `*Cache`,
   `*Setting`, `*Token`, `*Index`, and `*Log` are advisory warnings. Inspect
   columns and operations; trim implementation rows, but retain a real event or
   lifecycle detail when it is necessary for the planned outcome.
9. A coherent real-world dataset/export must populate most core rows. Internal
   configuration or backup data alone is insufficient.
10. Inspect every size. Do not over-merge a large candidate or turn every small
    schema into a capability. In a large repository, lookup/master/configuration
    tables with create/update operations are still not automatically independent
    Motifs. A result dominated by singleton table-management capabilities is a
    failed materialization and must be consolidated into its owning lifecycle or
    omitted.
11. Core memberships are not a partition. The same local Entity may appear in
    multiple MotifInstances when it provides genuine business context to each.
    For example, Product may occur in both a product catalog and product-review
    Motif, and Course may occur in both course and assignment Motifs. Reuse is
    preferable to merging independent lifecycles merely to avoid duplication.
    Do not copy generic hubs or unrelated rows into every Motif.
12. For each retained capability, inspect real edges from its records to the
    anchor of another retained capability. If a Review, Invoice, Shipment,
    Assignment, Submission, Booking, or analogous lifecycle cannot be
    interpreted without its Product, Order, Course, Project, or other domain
    parent, include that parent as contextual core even when it already occurs
    elsewhere. This is overlapping context, not a broad merged lifecycle.
    Principals such as User/Customer remain shared when factual links exist.

`direct_operation_*` identifies likely anchors but is incomplete.
`affected_operation_samples` may be another anchor's side effect. `edges` are
factual positive evidence and will be deterministically projected after your
semantic membership decision; missing edges do not require splitting.

## Capability Boundary Decision

```json
{{BOUNDARY_DECISION}}
```

## Repository Evidence

```json
{{REPO_GRAPH}}
```

## Output Contract
Return a JSON array only. Each element contains:

- `core`: exact `entities[].entity` names;
- `core_edges`: only factual input edges, or `[]` for deterministic projection;
- `shared`: exact principal Entity candidates with factual `via`, or `[]`;
- `domain`: broad business domain;
- `kind`: a precise snake_case capability name. It may preserve, split, or
  consolidate planned ids under the verification rules above;
- `groundable`: `high`, `med`, or `low`;
- `why`: exactly
  `Goal: <one outcome>; Reuse: <one capability>; Grounding: <real dataset family>.`

Return no prose or markdown. It is valid to output fewer or more Motifs than
retained hypotheses. Before answering, check that every output is justified by
the evidence and boundary tests, support candidates are omitted, normalized
details remain with their anchor, and no catch-all group was created. If a
repository has several dependent retained capabilities but no Entity appears in
more than one core, re-check that you did not accidentally force a partition.
