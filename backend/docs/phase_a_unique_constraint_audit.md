# Phase A UNIQUE Constraint Audit

## Purpose

UNIQUE constraints prevent duplicate domain identities and duplicate business facts.

Each uniqueness rule is classified as:

1. identity uniqueness;
2. business uniqueness;
3. historical uniqueness;
4. concurrency/lifecycle uniqueness.

---

# 1. Identity uniqueness

## User email

Table:

`users`

Field:

`email`

Rule:

```text
one account identity per email
```

Final:

```sql
UNIQUE (email)
```

Email comparison/canonicalization must also be handled consistently by the application.

---

# 2. Supplier organization identity

Table:

`suppliers`

Field:

`organization_id`

Rule:

```text
one authoritative supplier entity per supplier organization
```

Final:

```sql
UNIQUE (organization_id)
```

The current Feature 3 migration already defines this uniqueness.

---

# 3. Supplier code

Table:

`supplier_code`

Rule:

supplier code must identify at most one supplier.

Final:

```sql
UNIQUE (supplier_code)
```

NULL behavior must be intentional.

---

# 4. Supplier capabilities

Table:

`supplier_capabilities`

Business identity:

```text
supplier_id + capability
```

Final:

```sql
UNIQUE (supplier_id, capability)
```

---

# 5. Supplier products

Table:

`supplier_products`

Business identity:

```text
supplier_id + product
```

Final:

```sql
UNIQUE (supplier_id, product)
```

---

# 6. Organization membership

Table:

`organization_memberships`

Business identity:

```text
organization_id + user_id
```

Final:

```sql
UNIQUE (organization_id, user_id)
```

The current migration already defines this composite uniqueness.

---

# 7. Membership responsibility

Table:

`membership_responsibilities`

Identity:

```text
membership_id + responsibility_id
```

The composite primary key already provides uniqueness.

No additional duplicate UNIQUE constraint is necessary.

---

# 8. Procurement identifier

Table:

`procurements`

Business identity:

`procurement_identifier`

Final:

```sql
UNIQUE (procurement_identifier)
```

The identifier should be generated deterministically for new procurements.

The historical migration used a unique index only where the identifier was non-null.

For the final baseline, determine whether the identifier is mandatory.

If mandatory:

```text
NOT NULL + UNIQUE
```

is preferable to a nullable unique identifier.

---

# 9. Purchase order number

Table:

`purchase_orders`

Identity:

`order_number`

Final:

```sql
UNIQUE (order_number)
```

The current migration already defines this.

---

# 10. One purchase order per procurement

Current Phase A model:

```text
one procurement
    ↓
one purchase order
```

Therefore:

```sql
UNIQUE (procurement_id)
```

This is a business/lifecycle uniqueness rule.

The current migration already defines it.

If the domain later supports multiple POs per procurement, this constraint must change deliberately.

---

# 11. Purchase order line uniqueness

Within one PO:

```text
purchase_order_id + procurement_item_id
```

must identify one PO line.

Final:

```sql
UNIQUE (
    purchase_order_id,
    procurement_item_id
)
```

The current migration already defines this.

---

# 12. Supplier evaluation uniqueness

Within one procurement:

```text
procurement_id + supplier_id
```

identifies one evaluation snapshot.

Final:

```sql
UNIQUE (
    procurement_id,
    supplier_id
)
```

This is already present in the historical Feature 6/7 schema.

---

# 13. Supplier selection decision uniqueness

Selection history is append-only.

Each decision has:

```text
procurement_id + decision_sequence
```

Final:

```sql
UNIQUE (
    procurement_id,
    decision_sequence
)
```

This permits:

```text
1 INITIAL_SELECTION
2 RESELECTION
3 RESELECTION
```

without overwriting history.

---

# 14. Inspection uniqueness

Each delivery has at most one inspection.

Final:

```sql
UNIQUE (delivery_id)
```

This is a lifecycle uniqueness rule.

The current migration already creates this unique index.

---

# 15. Active commitment uniqueness

Within a purchase order line and supplier, only one active commitment may exist.

Business key:

```text
purchase_order_id
+
purchase_order_line_id
+
supplier_id
```

Active statuses:

```text
SUBMITTED
ACCEPTED
```

Final concept:

```sql
CREATE UNIQUE INDEX ...
ON supplier_commitments (
    purchase_order_id,
    purchase_order_line_id,
    supplier_id
)
WHERE status IN ('SUBMITTED', 'ACCEPTED');
```

The historical migration used the same concept but referenced `supplier_entity_id`; the final schema must use `supplier_id`.

---

# 16. Delivery sequence uniqueness

Within one commitment:

```text
commitment_id + delivery_sequence
```

must be unique.

Final:

```sql
UNIQUE (
    commitment_id,
    delivery_sequence
)
```

This is both:

* historical/lifecycle uniqueness;
* concurrency protection.

The service must still lock the commitment when generating the next sequence.

The UNIQUE constraint is the database backstop.

---

# 17. Evidence storage reference

Table:

`evidence_documents`

Field:

`storage_reference`

Rule:

one physical storage object must not accidentally represent multiple database evidence records.

Final:

```sql
UNIQUE (storage_reference)
```

The current Feature 12 schema already defines this.

---

# 18. Corrective action uniqueness

One inspection may have one corrective-action record.

Final:

```sql
UNIQUE (inspection_id)
```

This prevents multiple independent corrective actions from being created for the same rejected inspection unless the domain is deliberately changed.

---

# 19. Performance metric uniqueness

Current model stores one current derived metric snapshot per supplier.

Final:

```sql
UNIQUE (supplier_id)
```

This is appropriate only if the table represents the current metric snapshot.

If later historical metric snapshots are required, the key must evolve to include a calculation period/version.

---

# 20. Do not confuse indexes with business uniqueness

This:

```sql
CREATE INDEX ON procurements(organization_id);
```

does NOT mean:

```text organization_id is unique
```

It merely improves lookup.

This:

```sql
UNIQUE (organization_id)
```

means:

```text duplicate organization_id values are forbidden
```

---

# 21. Concurrency principle

UNIQUE constraints are database-level race protection.

Example:

Two requests simultaneously attempt:

```text
delivery_sequence = 3
```

Application-only checking can fail:

```text
Request A checks → 3 doesn't exist
Request B checks → 3 doesn't exist
A inserts 3
B inserts 3
```

A UNIQUE constraint prevents the final duplicate.

The service should additionally use locking or retry logic where required.

---

# 22. Final rule

For every candidate uniqueness rule ask:

1. Is this an identity?
2. Is this a business key?
3. Is this historical sequence identity?
4. Is this lifecycle uniqueness?
5. Is it only a query-performance index?
6. Can multiple valid records legitimately share the value?

UNIQUE audit status:

IN PROGRESS — final baseline reconstruction required.
