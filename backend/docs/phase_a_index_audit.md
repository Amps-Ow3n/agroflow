# Phase A Index Audit

## Purpose

Indexes must be justified by actual query patterns.

The Phase A system will not use an "index everything" strategy.

Each index must serve at least one of:

* filtering;
* joining;
* sorting;
* uniqueness;
* partial active-record lookup.

Every proposed index must have a reason.

---

# 1. Identity

## users.email

Purpose:

* login lookup
* identity lookup
* uniqueness

Decision:

`UNIQUE`

This automatically provides the primary lookup structure.

No separate ordinary index is required.

---

## users.is_system_admin

Current migration:

Partial index:

`WHERE is_system_admin = TRUE`

Purpose:

System-admin lookup.

Decision:

`KEEP if system-admin lookup queries exist frequently enough.`

Because system admins are expected to be rare, the partial index is reasonable.

---

# 2. Organizations

## organizations.organization_type

Query pattern:

```sql
WHERE organization_type = ?
```

Purpose:

Filter schools vs suppliers.

Decision:

`INDEX`

---

## organizations.verification_status

Query pattern:

```sql
WHERE verification_status = ?
```

Purpose:

Find organizations awaiting/approved/rejected verification.

Decision:

`INDEX`

---

# 3. Organization memberships

## membership.user_id

Query pattern:

```sql
WHERE user_id = ?
```

Purpose:

Resolve a user's organizations.

Decision:

`INDEX`

---

## membership.organization_id

Query pattern:

```sql
WHERE organization_id = ?
```

Purpose:

Resolve members of an organization.

Decision:

`INDEX`

The unique `(organization_id, user_id)` constraint already creates an index beginning with `organization_id`, so a separate single-column organization index may be redundant.

Final decision:

`REVIEW AFTER UNIQUE INDEX ANALYSIS`

---

# 4. Verification records

## organization_verification_records.organization_id

Purpose:

Retrieve verification history for an organization.

Decision:

`INDEX`

---

# 5. Suppliers

## suppliers.organization_id

Purpose:

Resolve supplier business entity from supplier organization.

Also enforces:

`one supplier per supplier organization`

Decision:

`UNIQUE (organization_id)`

A separate ordinary index is therefore unnecessary.

---

## suppliers.status

Query:

```sql
WHERE status = 'ACTIVE'
```

Purpose:

Active supplier filtering.

Decision:

`INDEX` only if this is a common standalone query.

If most queries filter by organization/status together, prefer a composite index based on actual query workload.

---

# 6. Supplier registry children

## supplier_capabilities.supplier_id

Purpose:

Retrieve capabilities for a supplier.

Decision:

`INDEX`

---

## supplier_products.supplier_id

Purpose:

Retrieve products for a supplier.

Decision:

`INDEX`

---

## supplier_products.product

Purpose:

Find suppliers providing a product.

Decision:

`INDEX`

This is particularly relevant to supplier candidate discovery.

---

## supplier_contacts.supplier_id

Purpose:

Retrieve supplier contacts.

Decision:

`INDEX`

---

# 7. Procurements

## procurements.organization_id

Purpose:

Organization-scoped procurement queries.

Examples:

```sql
WHERE organization_id = ?
```

Decision:

`INDEX`

This is one of the most important Phase A indexes because organization isolation is a core query boundary.

---

## procurements.status

Purpose:

Operational dashboard filtering.

Examples:

```sql
WHERE status = 'EVALUATION'
```

Decision:

`INDEX`

---

## procurements.organization_id + status

Potential composite index:

```sql
INDEX (
    organization_id,
    status
)
```

Purpose:

School dashboard queries such as:

```sql
WHERE organization_id = ?
AND status = ?
```

Decision:

`PREFER COMPOSITE INDEX IF THIS IS A DOMINANT QUERY PATTERN`

Do not automatically retain both single-column indexes and the composite index.

---

## procurements.required_by_date

Purpose:

Upcoming procurement/delivery filtering.

Decision:

`INDEX` if used directly by dashboard/workflow queries.

---

## procurements.created_by

Purpose:

Find procurements created by a particular user.

Decision:

`INDEX` only if actual queries require it.

---

## procurements.requesting_user_id

Purpose:

Find procurements requested by a particular user.

Decision:

`INDEX` only if actual queries require it.

---

## procurements.procurement_identifier

Purpose:

Direct procurement lookup.

Decision:

`UNIQUE`

No separate ordinary index required.

---

# 8. Procurement items

## procurement_items.procurement_id

Purpose:

Retrieve all items for a procurement.

Decision:

`INDEX`

---

# 9. Supplier evaluations

## supplier_evaluations.procurement_id

Purpose:

Retrieve candidates/evaluations for procurement.

Decision:

`INDEX`

---

## supplier_evaluations.supplier_id

Purpose:

Retrieve evaluation history for supplier.

Decision:

`INDEX`

---

## UNIQUE(procurement_id, supplier_id)

Purpose:

One evaluation per supplier per procurement.

This unique index may also support queries beginning with:

`procurement_id`

Therefore a separate index on `procurement_id` may be redundant depending on PostgreSQL's chosen query patterns.

Final decision:

`REVIEW AFTER BASELINE QUERY ANALYSIS`

---

# 10. Supplier selection decisions

## procurement_id

Purpose:

Retrieve selection history.

Decision:

`INDEX`

---

## supplier_id

Purpose:

Find selection history involving a supplier.

Decision:

`INDEX` if required by supplier history/report queries.

---

## decided_by

Purpose:

Find decisions made by actor.

Decision:

`INDEX` if required by audit/accountability queries.

---

## supersedes_decision_id

Purpose:

Resolve reselection chain.

Decision:

`INDEX`

---

## UNIQUE(procurement_id, decision_sequence)

Purpose:

Prevent duplicate decision sequence numbers.

Also supports procurement-scoped sequence lookup.

---

# 11. Purchase orders

## purchase_orders.procurement_id

Purpose:

Retrieve PO for procurement.

Because current Phase A allows one PO per procurement:

`UNIQUE(procurement_id)`

already provides an index.

Therefore:

`NO ADDITIONAL ORDINARY INDEX REQUIRED`

---

## purchase_orders.supplier_id

Purpose:

Supplier-specific order history.

Decision:

`INDEX`

---

## purchase_order_lines.purchase_order_id

Purpose:

Retrieve PO lines.

Decision:

`INDEX`

---

## purchase_order_lines.procurement_item_id

Purpose:

Find order line for procurement item.

Decision:

`INDEX`

---

# 12. Supplier commitments

## purchase_order_id

Purpose:

Retrieve commitments belonging to PO.

Decision:

`INDEX`

---

## purchase_order_line_id

Purpose:

Retrieve commitments for specific PO line.

Decision:

`INDEX`

---

## supplier_id

Purpose:

Supplier commitment history.

Decision:

`INDEX`

---

## status

Purpose:

Find submitted/accepted/rejected commitments.

Decision:

`INDEX` only if status is commonly queried independently.

---

## active commitment partial UNIQUE index

Business rule:

one active commitment per:

`purchase_order_id + purchase_order_line_id + supplier_id`

Purpose:

* uniqueness;
* active commitment lookup;
* concurrency protection.

Decision:

`KEEP AS UNIQUE PARTIAL INDEX`

Final supplier identity must use:

`supplier_id`

not:

`supplier_entity_id`.

---

# 13. Deliveries

## deliveries.commitment_id

Purpose:

Retrieve delivery history for commitment.

Decision:

`INDEX`

---

## deliveries.parent_delivery_id

Purpose:

Retrieve corrective delivery chain.

Decision:

`INDEX`

---

## deliveries.delivery_status

Purpose:

Find:

* awaiting inspection;
* accepted;
* rejected.

Decision:

`INDEX` if operational dashboard queries commonly filter by status.

---

## deliveries.delivery_date

Purpose:

Date-range delivery queries.

Decision:

`INDEX` if historical reporting frequently filters by delivery date.

---

## deliveries.receiving_user_id

Purpose:

Find deliveries recorded by receiving officer.

Decision:

`INDEX` if audit/reporting queries require it.

---

## IMPORTANT

Do not create final indexes for:

`deliveries.procurement_id`

or:

`deliveries.supplier_id`

until the redundant fields themselves have been removed or justified.

The final model derives procurement and supplier through:

`delivery → commitment → purchase order → procurement/supplier`

---

# 14. Delivery lines

## delivery_lines.delivery_id

Purpose:

Retrieve lines belonging to delivery.

Decision:

`INDEX`

---

## delivery_lines.procurement_item_id

Purpose:

Trace delivered quantity to procurement requirement.

Decision:

`INDEX`

---

# 15. Inspections

## inspections.delivery_id

Purpose:

One inspection per delivery.

Decision:

`UNIQUE`

This also creates an index.

No separate ordinary index is required.

---

## inspections.inspected_by

Purpose:

Inspector history.

Decision:

`INDEX` if required.

---

## inspections.result

Purpose:

Find accepted/rejected deliveries.

Decision:

`INDEX` if used independently.

---

## inspections.inspected_at

Purpose:

Historical/time-based inspection queries.

Decision:

`INDEX` if date-range queries require it.

---

# 16. Corrective actions

## corrective_actions.inspection_id

Purpose:

One corrective action per inspection.

Decision:

`UNIQUE`

---

## corrective_actions.status

Purpose:

Operational corrective-action queue.

Decision:

`INDEX`

---

## corrective_actions.replacement_delivery_id

Purpose:

Resolve replacement delivery.

Decision:

`INDEX` if lookup is used.

---

# 17. Evidence documents

## evidence_documents.procurement_id

Purpose:

Retrieve all evidence for procurement.

Decision:

`INDEX`

---

## evidence_documents.event_id

Purpose:

Retrieve evidence attached to event.

Decision:

`INDEX`

---

## evidence_documents.uploaded_by

Purpose:

Uploader history.

Decision:

`INDEX` if required.

---

## evidence_documents.visibility

Purpose:

Filter visibility.

Decision:

`REVIEW`

A low-cardinality field such as visibility may not benefit from a standalone index at small pilot scale.

---

## evidence_documents.procurement_id WHERE deleted_at IS NULL

Purpose:

Retrieve active evidence for procurement.

Decision:

`PARTIAL INDEX`

This is useful because soft-deleted evidence should normally be excluded from operational queries.

---

## evidence_documents.storage_reference

Purpose:

Physical storage identity.

Decision:

`UNIQUE`

---

# 18. Procurement events

## procurement_events.procurement_id + occurred_at + id

Purpose:

Primary procurement timeline query:

```sql
WHERE procurement_id = ?
ORDER BY occurred_at, id
```

Decision:

`COMPOSITE INDEX`

This is a strong example of designing an index from an actual access pattern rather than from individual columns.

---

## procurement_events.actor_id

Purpose:

Actor history.

Decision:

`INDEX` if audit queries require it.

---

## procurement_events.entity_type + entity_id

Purpose:

Resolve events for a particular entity.

Decision:

`COMPOSITE INDEX`

---

## procurement_events.event_type

Purpose:

Filter timeline events by type.

Decision:

`INDEX` only if commonly queried independently.

---

# 19. Audit events

## audit_events.procurement_id + created_at + id

Purpose:

Retrieve chronological audit history.

Decision:

`COMPOSITE INDEX`

---

## audit_events.actor_id

Purpose:

Actor accountability lookup.

Decision:

`INDEX`

---

## audit_events.entity_type + entity_id

Purpose:

Entity-specific audit lookup.

Decision:

`COMPOSITE INDEX`

---

## audit_events.action

Purpose:

Filter audit actions.

Decision:

`INDEX` only if actual query workload requires it.

---

# 20. Supplier performance

## supplier_performance_metrics.supplier_id

Purpose:

Retrieve current supplier metrics.

Because supplier_id is unique:

`UNIQUE(supplier_id)`

already provides the required lookup index.

Therefore:

`NO SEPARATE ORDINARY INDEX REQUIRED`

---

## supplier_performance_metrics.status

Purpose:

Find suppliers with/without historical evidence.

Decision:

`REVIEW`

At small pilot scale this may not justify an index.

---

# 21. Indexes that must NOT automatically survive

The following historical indexes are tied to obsolete/redundant structures:

* indexes on `supply_sources`;
* indexes on `supplier_entity_id`;
* indexes on legacy `procurement_documents`;
* indexes on legacy `delivery_documents`;
* indexes on redundant delivery `supplier_id`;
* indexes on redundant delivery `procurement_id`;
* indexes supporting retired agricultural procurement chains.

These must be reconsidered during baseline reconstruction.

---

# 22. Index redundancy rule

Before adding an index, ask:

1. Does a PRIMARY KEY already provide this index?
2. Does a UNIQUE constraint already provide this index?
3. Does a composite index already begin with this column?
4. Is the query selective enough?
5. Is the query actually executed frequently?
6. Does the index support filtering, joining, sorting, uniqueness, or a useful partial condition?
7. What write cost does the index introduce?

Never create an index simply because a column is a foreign key.

---

# 23. Composite-index principle

For a query:

```sql
WHERE organization_id = ?
AND status = ?
ORDER BY created_at DESC
```

a potentially useful index is:

```sql
(
    organization_id,
    status,
    created_at DESC
)
```

rather than three unrelated indexes.

But this must be verified against actual queries and `EXPLAIN ANALYZE`.

---

# 24. Final index rule

The final Phase A index set shall be derived from:

`domain constraints`

*

`actual query patterns`

*

`organization isolation`

*

`dashboard/report access patterns`

*

`timeline/audit access patterns`

*

`measured query performance`

not from:

`index every column`.

Index audit status:

READY FOR BASELINE RECONSTRUCTION AND QUERY-PLAN VERIFICATION.
