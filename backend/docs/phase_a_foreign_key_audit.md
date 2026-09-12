# Phase A Foreign-Key Audit

## Purpose

Every foreign key in the Phase A database must be justified by an explicit domain relationship.

A foreign key must not be accepted merely because the column names appear to match.

For each relationship we verify:

1. child table
2. child column
3. parent table
4. parent column
5. semantic meaning
6. data type compatibility
7. nullability
8. ON DELETE behavior
9. whether additional service-level validation is required

## Authoritative identity rules

* `users.id` = human user identity
* `organizations.id` = organization identity
* `suppliers.id` = supplier business identity
* `actor_id` = `users.id`
* `organization_id` = `organizations.id`
* `supplier_id` = `suppliers.id`
* `school_id` is not an authoritative Phase A identity
* `supplier_entity_id` is not an authoritative Phase A identity

# Phase A Foreign-Key Audit

## Purpose

Every foreign key must represent a deliberate domain relationship.

A foreign key must not be accepted merely because column names happen to match.

For every relationship we verify:

1. child table;
2. child column;
3. parent table;
4. parent column;
5. semantic meaning;
6. data type compatibility;
7. nullability;
8. ON DELETE behavior;
9. whether additional service-level validation is required.

---

# 1. Identity Relationships

| Child                             | Child column       | Parent                   | Parent column | Meaning                                         | Current decision                |
| --------------------------------- | ------------------ | ------------------------ | ------------- | ----------------------------------------------- | ------------------------------- |
| organization_memberships          | organization_id    | organizations            | id            | membership belongs to organization              | KEEP                            |
| organization_memberships          | user_id            | users                    | id            | membership belongs to user                      | KEEP                            |
| membership_responsibilities       | membership_id      | organization_memberships | id            | responsibility assignment belongs to membership | KEEP                            |
| membership_responsibilities       | responsibility_id  | responsibilities         | id            | assignment references responsibility definition | KEEP                            |
| organization_verification_records | organization_id    | organizations            | id            | verification record belongs to organization     | KEEP                            |
| organization_verification_records | reviewed_by        | users                    | id            | human reviewer                                  | KEEP, nullable                  |
| procurements                      | organization_id    | organizations            | id            | procurement belongs to school organization      | KEEP                            |
| procurements                      | created_by         | users                    | id            | human creator                                   | KEEP                            |
| procurements                      | requesting_user_id | users                    | id            | human requester                                 | KEEP if retained in final model |

## Identity invariant

Human identity:

`users.id`

Organization identity:

`organizations.id`

Supplier business identity:

`suppliers.id`

These identities must not be substituted for one another.

---

# 2. Supplier Relationships

| Child                 | Child column    | Parent        | Parent column | Meaning                                            | Current decision |
| --------------------- | --------------- | ------------- | ------------- | -------------------------------------------------- | ---------------- |
| suppliers             | organization_id | organizations | id            | supplier business belongs to supplier organization | KEEP             |
| supplier_capabilities | supplier_id     | suppliers     | id            | capability belongs to supplier                     | KEEP             |
| supplier_products     | supplier_id     | suppliers     | id            | product capability belongs to supplier             | KEEP             |
| supplier_contacts     | supplier_id     | suppliers     | id            | contact belongs to supplier                        | KEEP             |

## Legacy supplier identity

`supplier_entity_id` is NOT authoritative.

The final model shall use:

`supplier_id → suppliers.id`

Any existing `supplier_entity_id` relationship shall be replaced during schema reconstruction.

---

# 3. Procurement Relationships

| Child                        | Child column           | Parent                       | Parent column | Meaning                                     | Current decision |
| ---------------------------- | ---------------------- | ---------------------------- | ------------- | ------------------------------------------- | ---------------- |
| procurement_items            | procurement_id         | procurements                 | id            | item belongs to procurement                 | KEEP             |
| supplier_evaluations         | procurement_id         | procurements                 | id            | evaluation belongs to procurement           | KEEP             |
| supplier_evaluations         | supplier_id            | suppliers                    | id            | supplier being evaluated                    | KEEP             |
| supplier_evaluations         | evaluated_by           | users                        | id            | human/system actor recording evaluation     | KEEP             |
| supplier_selection_decisions | procurement_id         | procurements                 | id            | decision belongs to procurement             | KEEP             |
| supplier_selection_decisions | supplier_id            | suppliers                    | id            | selected supplier business entity           | KEEP             |
| supplier_selection_decisions | supersedes_decision_id | supplier_selection_decisions | id            | later decision supersedes previous decision | KEEP             |
| supplier_selection_decisions | decided_by             | users                        | id            | human decision maker                        | KEEP             |

The supplier-selection relationship is:

`procurement → supplier evaluation → human selection → supplier`

not:

`procurement → user`.

---

# 4. Purchase Order Relationships

| Child                | Child column        | Parent            | Parent column | Meaning                           | Final decision |
| -------------------- | ------------------- | ----------------- | ------------- | --------------------------------- | -------------- |
| purchase_orders      | procurement_id      | procurements      | id            | PO belongs to procurement         | KEEP           |
| purchase_orders      | supplier_id         | suppliers         | id            | PO is issued to supplier business | CHANGE         |
| purchase_orders      | created_by          | users             | id            | human creator                     | KEEP           |
| purchase_order_lines | purchase_order_id   | purchase_orders   | id            | line belongs to PO                | KEEP           |
| purchase_order_lines | procurement_item_id | procurement_items | id            | PO line fulfills procurement item | KEEP           |

## Critical correction

Current Feature 8 defines:

`purchase_orders.supplier_id → users.id`

This is incorrect for the final Phase A domain.

The final relationship is:

`purchase_orders.supplier_id → suppliers.id`

The current migration explicitly shows the old `users(id)` relationship.

---

# 5. Supplier Commitment Relationships

| Child                | Child column           | Parent               | Parent column | Meaning                       | Final decision              |
| -------------------- | ---------------------- | -------------------- | ------------- | ----------------------------- | --------------------------- |
| supplier_commitments | purchase_order_id      | purchase_orders      | id            | commitment belongs to PO      | KEEP                        |
| supplier_commitments | purchase_order_line_id | purchase_order_lines | id            | commitment relates to PO line | KEEP                        |
| supplier_commitments | supplier_id            | suppliers            | id            | supplier making commitment    | KEEP after identity cleanup |
| supplier_commitments | submitted_by           | users                | id            | human actor                   | KEEP                        |
| supplier_commitments | accepted_by            | users                | id            | human actor                   | KEEP                        |
| supplier_commitments | rejected_by            | users                | id            | human actor                   | KEEP                        |

## Legacy relationships

The following are not authoritative:

`supplier_entity_id`

`capacity_source_id → supply_sources.id`

The capacity source relationship requires separate review because `supply_sources` belongs to an older AgroFlow model.

The final commitment should not depend on an obsolete agricultural supply-source entity merely because the historical migration added that FK.

---

# 6. Delivery Relationships

| Child          | Child column        | Parent               | Parent column | Meaning                                    | Final decision |
| -------------- | ------------------- | -------------------- | ------------- | ------------------------------------------ | -------------- |
| deliveries     | commitment_id       | supplier_commitments | id            | delivery fulfills commitment               | KEEP           |
| deliveries     | receiving_user_id   | users                | id            | receiving actor                            | KEEP           |
| deliveries     | parent_delivery_id  | deliveries           | id            | corrective delivery chain                  | KEEP           |
| delivery_lines | delivery_id         | deliveries           | id            | line belongs to delivery                   | KEEP           |
| delivery_lines | procurement_item_id | procurement_items    | id            | delivered line relates to procurement item | KEEP           |

## Important redundancy

The historical Feature 10 schema contains:

`deliveries.procurement_id`

and:

`deliveries.supplier_id`

The supplier relationship was incorrectly defined as:

`deliveries.supplier_id → organizations.id`.

The delivery already has:

`delivery → commitment → purchase order → procurement`

and:

`delivery → commitment → supplier`

Therefore these duplicated direct relationships must not automatically be retained.

Final schema decision:

* `commitment_id` is authoritative.
* supplier is derived through commitment.
* procurement is derived through commitment → purchase order → procurement.

Redundant direct foreign keys should be removed unless a documented performance/domain reason proves they are necessary.

---

# 7. Inspection Relationships

| Child       | Child column | Parent     | Parent column | Meaning                      | Final decision |
| ----------- | ------------ | ---------- | ------------- | ---------------------------- | -------------- |
| inspections | delivery_id  | deliveries | id            | inspection verifies delivery | KEEP           |
| inspections | inspected_by | users      | id            | human inspector              | KEEP           |

Inspection is school-side verification.

The supplier does not become the inspection authority merely because the supplier owns the commitment.

---

# 8. Corrective Action Relationships

| Child              | Child column            | Parent      | Parent column | Meaning                                        | Final decision |
| ------------------ | ----------------------- | ----------- | ------------- | ---------------------------------------------- | -------------- |
| corrective_actions | inspection_id           | inspections | id            | corrective action follows inspection           | KEEP           |
| corrective_actions | replacement_delivery_id | deliveries  | id            | corrective action creates replacement delivery | KEEP           |
| corrective_actions | created_by              | users       | id            | human actor                                    | KEEP           |

The historical migration correctly uses `RESTRICT` for these relationships.

---

# 9. Evidence Relationships

| Child              | Child column   | Parent             | Parent column | Meaning                                  | Final decision |
| ------------------ | -------------- | ------------------ | ------------- | ---------------------------------------- | -------------- |
| evidence_documents | procurement_id | procurements       | id            | evidence belongs to procurement          | KEEP           |
| evidence_documents | event_id       | procurement_events | id            | evidence supports procurement event      | KEEP           |
| evidence_documents | uploaded_by    | users              | id            | human uploader                           | KEEP           |
| evidence_documents | deleted_by     | users              | id            | human performing administrative deletion | KEEP, nullable |

The older `procurement_documents` and `delivery_documents` structures are not authoritative.

`evidence_documents` is the final evidence structure.

---

# 10. Timeline Relationships

| Child              | Child column   | Parent             | Parent column | Meaning                       | Final decision |
| ------------------ | -------------- | ------------------ | ------------- | ----------------------------- | -------------- |
| procurement_events | procurement_id | procurements       | id            | event belongs to procurement  | KEEP           |
| procurement_events | actor_id       | users              | id            | actor causing/recording event | KEEP           |
| audit_events       | procurement_id | procurements       | id            | audit belongs to procurement  | KEEP           |
| audit_events       | actor_id       | users              | id            | human actor                   | KEEP           |
| evidence_documents | event_id       | procurement_events | id            | evidence supports event       | KEEP           |

Feature 13 explicitly defines these procurement and actor relationships with `ON DELETE RESTRICT`.

---

# 11. Supplier Performance

| Child                        | Child column | Parent    | Parent column | Meaning                            | Final decision |
| ---------------------------- | ------------ | --------- | ------------- | ---------------------------------- | -------------- |
| supplier_performance_metrics | supplier_id  | suppliers | id            | derived metrics belong to supplier | KEEP           |

The historical Feature 15 migration already uses:

`supplier_performance_metrics.supplier_id → suppliers.id`

with `ON DELETE RESTRICT`.

---

# 12. Foreign Keys Requiring Special Review

The following relationships must NOT simply be copied into the clean baseline:

1. `purchase_orders.supplier_id → users.id`
2. `supplier_commitments.supplier_entity_id → suppliers.id`
3. `supplier_commitments.capacity_source_id → supply_sources.id`
4. `deliveries.supplier_id → organizations.id`
5. direct `deliveries.procurement_id`
6. legacy `procurement_status_history`
7. legacy document tables
8. any FK belonging exclusively to the retired agricultural/legacy model.

---

# 13. ON DELETE Principle

Phase A is an auditable procurement system.

Historical procurement facts must not disappear through casual parent deletion.

Default principle:

* identity/reference records used by historical procurement: generally `RESTRICT`;
* membership assignment records may use `CASCADE`;
* child capability/product records may use `CASCADE` where they are subordinate registry records;
* optional administrative reviewer/deleter references may use `SET NULL`;
* historical procurement events/audit events use `RESTRICT`;
* corrective-action history uses `RESTRICT`.

Every `CASCADE` must therefore have an explicit justification.

---

# 14. Final FK Standard

A relationship is accepted only when:

`semantic relationship is correct`

AND

`parent identity is correct`

AND

`data types are compatible`

AND

`delete behavior is correct`

AND

`any cross-entity business rule is handled by the service layer`.

FK audit status:

IN PROGRESS — baseline reconstruction required.
