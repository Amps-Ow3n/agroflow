# Phase A Delete Policy Audit

## Purpose

Every foreign-key relationship in the Phase A schema must have an intentional deletion policy.

Allowed policies:

* CASCADE
* RESTRICT
* SET NULL

The policy must be based on domain meaning rather than convenience.

---

# 1. Identity and organization relationships

## organization_memberships → organizations

Relationship:

`organization_memberships.organization_id → organizations.id`

Recommended:

`CASCADE`

Reason:

A membership is subordinate to its organization.

However, the application should normally suspend organizations rather than physically delete them.

Final decision:

`CASCADE if physical deletion is retained; otherwise deletion may be operationally unavailable.`

---

## organization_memberships → users

Relationship:

`organization_memberships.user_id → users.id`

Recommended:

`RESTRICT`

Reason:

Membership identifies a historical relationship between a human account and an organization.

User accounts should normally be suspended rather than physically deleted.

Final decision:

`RESTRICT`

---

## membership_responsibilities → organization_memberships

Recommended:

`CASCADE`

Reason:

A responsibility assignment cannot meaningfully exist without its membership.

Final decision:

`CASCADE`

---

## membership_responsibilities → responsibilities

Recommended:

`RESTRICT`

Reason:

Responsibilities are centrally defined authorization concepts.

Deleting a responsibility could invalidate authorization history.

Final decision:

`RESTRICT`

---

## organization_verification_records → organizations

Recommended:

`CASCADE` only if an organization itself can be physically deleted.

Otherwise organizations should be suspended/archived.

Final decision:

`CASCADE` is structurally acceptable for subordinate verification records, but physical organization deletion should be tightly controlled.

---

## organization_verification_records.reviewed_by → users

Recommended:

`SET NULL` if user deletion is ever permitted.

Reason:

The verification record can retain its business meaning without an active user relationship.

However, user deletion should normally be avoided in the production system.

Final decision:

`SET NULL`

---

# 2. Supplier registry

## suppliers → organizations

Relationship:

`supplier.organization_id → organizations.id`

Recommended:

`RESTRICT`

Reason:

Supplier identity is part of organizational procurement history.

Deleting the organization must not silently destroy the supplier identity used by historical procurement records.

Final decision:

`RESTRICT`

---

## supplier_capabilities → suppliers

Recommended:

`CASCADE`

Reason:

A capability record has no independent existence outside its supplier registry record.

Final decision:

`CASCADE`

---

## supplier_products → suppliers

Recommended:

`CASCADE`

Reason:

Supplier product capability records are subordinate to the supplier.

Final decision:

`CASCADE`

---

## supplier_contacts → suppliers

Recommended:

`CASCADE`

Reason:

A supplier contact record is subordinate registry data.

Final decision:

`CASCADE`

---

# 3. Procurement

## procurement_items → procurements

Recommended:

`CASCADE` only if physical deletion of procurements is allowed.

Reason:

An item has no independent meaning outside its procurement.

However, completed procurement records should normally not be physically deleted.

Final decision:

`CASCADE` for true subordinate deletion semantics, combined with application policy preventing deletion of historical procurements.

---

## procurements → organizations

Recommended:

`RESTRICT`

Reason:

Procurement ownership is part of organizational history.

Deleting an organization must not casually destroy procurement history.

Final decision:

`RESTRICT`

---

## procurements → users

For:

* created_by
* requesting_user_id

Recommended:

`RESTRICT`

Reason:

The actor is part of procurement accountability.

Historical procurement must retain the human identity responsible for the action.

Final decision:

`RESTRICT`

---

# 4. Supplier evaluation

## supplier_evaluations → procurements

Recommended:

`CASCADE` only if a procurement itself is physically deleted.

Reason:

An evaluation has no independent meaning without its procurement.

Final decision:

`CASCADE` subject to procurement deletion policy.

---

## supplier_evaluations → suppliers

Recommended:

`RESTRICT`

Reason:

Evaluation history is evidence about a supplier.

Deleting the supplier would destroy historical evidence.

Final decision:

`RESTRICT`

---

## supplier_evaluations → users

For `evaluated_by`:

`RESTRICT`

Reason:

The evaluator is part of the evidence and accountability record.

Final decision:

`RESTRICT`

---

# 5. Supplier selection

## supplier_selection_decisions → procurements

Recommended:

`RESTRICT`

Reason:

Selection decisions are part of procurement history and human decision accountability.

If procurement physical deletion is ever allowed, deletion must be explicitly designed rather than silently cascading away decision history.

Final decision:

`RESTRICT`

---

## supplier_selection_decisions → suppliers

Recommended:

`RESTRICT`

Reason:

The selected supplier identity is historical evidence.

Final decision:

`RESTRICT`

---

## supplier_selection_decisions → users

For `decided_by`:

`RESTRICT`

Reason:

The human decision maker must remain accountable.

Final decision:

`RESTRICT`

---

## supplier_selection_decisions.supersedes_decision_id

Self-reference:

`decision → previous decision`

Recommended:

`RESTRICT`

Reason:

A later decision must not be allowed to destroy the earlier decision history.

Final decision:

`RESTRICT`

The historical migration already uses `ON DELETE RESTRICT` for this relationship.

---

# 6. Purchase orders

## purchase_orders → procurements

Recommended:

`RESTRICT`

Reason:

A purchase order is historical procurement evidence.

Deleting the procurement must not silently destroy the order record.

Final decision:

`RESTRICT`

---

## purchase_orders → suppliers

Recommended:

`RESTRICT`

Reason:

The supplier identity is part of the order's historical meaning.

Final decision:

`RESTRICT`

---

## purchase_orders → users

For `created_by`:

`RESTRICT`

Reason:

The creator is an accountability record.

Final decision:

`RESTRICT`

---

## purchase_order_lines → purchase_orders

Recommended:

`CASCADE` only if PO deletion is genuinely permitted.

Reason:

A PO line has no independent meaning without its PO.

Final decision:

`CASCADE` structurally, with application-level prohibition on deleting issued/historical POs.

---

## purchase_order_lines → procurement_items

Recommended:

`RESTRICT`

Reason:

The line must remain tied to the original procurement requirement.

Final decision:

`RESTRICT`

---

# 7. Supplier commitments

## supplier_commitments → purchase_orders

Recommended:

`RESTRICT`

Reason:

Commitment is historical evidence of what the supplier promised.

Final decision:

`RESTRICT`

---

## supplier_commitments → purchase_order_lines

Recommended:

`RESTRICT`

Reason:

The commitment must remain tied to the ordered line.

Final decision:

`RESTRICT`

---

## supplier_commitments → suppliers

Recommended:

`RESTRICT`

Reason:

Commitment identifies the supplier making the promise.

Final decision:

`RESTRICT`

---

## supplier_commitments → users

For:

* submitted_by
* accepted_by
* rejected_by

Recommended:

`RESTRICT` for historical actors.

Final decision:

`RESTRICT`

---

# 8. Deliveries

## deliveries → supplier_commitments

Recommended:

`RESTRICT`

Reason:

A delivery is a physical event fulfilling a commitment.

Deleting the commitment must not destroy delivery evidence.

Final decision:

`RESTRICT`

---

## deliveries → users

For `receiving_user_id`:

`RESTRICT`

Reason:

The receiving actor is part of verification/accountability.

Final decision:

`RESTRICT`

---

## deliveries.parent_delivery_id → deliveries.id

Recommended:

`RESTRICT`

Reason:

Corrective delivery chains are historical evidence.

Deleting the parent must not silently destroy the relationship.

Final decision:

`RESTRICT`

---

## delivery_lines → deliveries

Recommended:

`CASCADE`

Reason:

Delivery lines have no independent existence without the delivery event.

Final decision:

`CASCADE`

---

## delivery_lines → procurement_items

Recommended:

`RESTRICT`

Reason:

Delivery evidence must remain tied to the original procurement requirement.

Final decision:

`RESTRICT`

---

# 9. Inspections

## inspections → deliveries

Recommended:

`RESTRICT`

Reason:

An inspection is verification evidence about a delivery.

Deleting the delivery must not destroy inspection history.

Final decision:

`RESTRICT`

---

## inspections → users

For `inspected_by`:

`RESTRICT`

Reason:

Inspector identity is accountability information.

Final decision:

`RESTRICT`

---

# 10. Corrective actions

## corrective_actions → inspections

Recommended:

`RESTRICT`

Reason:

Corrective action exists because of a particular inspection result.

Final decision:

`RESTRICT`

---

## corrective_actions → deliveries

For `replacement_delivery_id`:

`RESTRICT`

Reason:

The replacement delivery is historical evidence of corrective action.

Final decision:

`RESTRICT`

---

## corrective_actions → users

For `created_by`:

`RESTRICT`

Reason:

The actor is accountability evidence.

Final decision:

`RESTRICT`

---

# 11. Evidence

## evidence_documents → procurements

Recommended:

`RESTRICT`

Reason:

Evidence supporting a procurement must not disappear because the procurement is deleted.

Final decision:

`RESTRICT`

---

## evidence_documents → procurement_events

Recommended:

`RESTRICT`

Reason:

Evidence is linked to a historical event.

Final decision:

`RESTRICT`

---

## evidence_documents → users

For:

* uploaded_by
* deleted_by

Recommended:

`RESTRICT` for historical accountability, unless the final identity-retention policy deliberately permits SET NULL.

Final decision:

`RESTRICT` for historical actor preservation.

---

# 12. Procurement events

## procurement_events → procurements

Recommended:

`RESTRICT`

Reason:

Timeline events are historical facts.

Final decision:

`RESTRICT`

---

## procurement_events → users

For `actor_id`:

`RESTRICT`

Reason:

Actor identity is part of the historical fact.

Final decision:

`RESTRICT`

---

# 13. Audit events

## audit_events → procurements

Recommended:

`RESTRICT`

Reason:

Audit history must not disappear through procurement deletion.

Final decision:

`RESTRICT`

---

## audit_events → users

For `actor_id`:

`RESTRICT`

Reason:

Audit accountability depends on retaining the actor identity.

Final decision:

`RESTRICT`

---

# 14. Supplier performance

## supplier_performance_metrics → suppliers

Recommended:

`RESTRICT`

Reason:

Performance metrics are derived historical evidence about a supplier.

Final decision:

`RESTRICT`

---

# 15. General deletion policy

Phase A should prefer:

`SUSPEND / ARCHIVE`

over:

`PHYSICAL DELETE`

for entities that participate in historical procurement.

This preserves:

* accountability;
* auditability;
* supplier history;
* procurement history;
* evidence;
* performance calculations.

CASCADE should therefore be reserved mainly for subordinate records that have no independent business meaning.

RESTRICT should be the default for historical relationships.

SET NULL should be used only where the child remains meaningful without the parent identity.

---

# Final decision hierarchy

1. Historical/accountability relationship → `RESTRICT`
2. Pure subordinate child → `CASCADE`
3. Optional actor/reference where child survives independently → `SET NULL`
4. When uncertain → do not guess; resolve the domain meaning first.

Delete-policy audit status:

READY FOR BASELINE RECONSTRUCTION.
