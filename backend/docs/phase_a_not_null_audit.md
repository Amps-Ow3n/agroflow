# Phase A NOT NULL Audit

## Purpose

NULL is permitted only when the domain genuinely allows a value to be unknown, unavailable, optional, or not yet applicable.

A field must be NOT NULL when the absence of the value would destroy the meaning of the record.

---

# 1. Users

Required:

* id
* name/full_name
* email
* password_hash
* status
* is_system_admin
* created_at
* updated_at where used

Optional:

* fields genuinely not required for account identity

---

# 2. Organizations

Required:

* id
* name
* organization_type
* status
* verification_status
* created_at
* updated_at

Potentially optional:

* registration_number
* school_identifier
* address
* phone
* email

These may legitimately be unavailable depending on the registration workflow.

---

# 3. Memberships

Required:

* organization_id
* user_id
* status
* created_at
* updated_at

A membership without a user or organization has no meaning.

---

# 4. Responsibilities

Required:

* code
* name
* created_at

Optional:

* description
* organization_type where ANY/NULL is intentionally supported

---

# 5. Supplier

Required:

* organization_id
* status
* created_at
* updated_at

Supplier code:

Determine whether final Phase A requires it at creation.

If yes:

```text
NOT NULL + UNIQUE
```

If generated asynchronously or during registration:

temporary NULL may be legitimate.

---

# 6. Supplier capabilities/products

Required:

* supplier_id
* capability/product
* status
* created_at
* updated_at

An empty capability/product does not represent a valid registry record.

---

# 7. Supplier contacts

Required:

* supplier_id
* contact_name
* is_primary
* status
* created_at
* updated_at

Optional:

* phone
* email
* role

A supplier contact may legitimately lack one communication channel.

---

# 8. Procurement

Required:

* organization_id
* created_by
* title
* status
* created_at
* updated_at

Potentially required after requirement creation:

* procurement_identifier
* procurement_date
* required_by_date

The distinction matters.

A draft may legitimately not have every finalized procurement field yet.

Therefore the final NOT NULL decision must respect the lifecycle.

---

# 9. Procurement item

Required:

* procurement_id
* item_name
* quantity
* unit
* created_at
* updated_at

Optional:

* description

A procurement item without quantity or unit cannot represent the requirement.

---

# 10. Supplier evaluation

Required:

* procurement_id
* supplier_id
* evaluation_status
* required_item_match
* mandatory_eligible
* capacity_status
* historical_evidence_status
* historical counts
* fulfilled_quantity
* promised_quantity
* indicator_explanation
* evaluated_at
* evaluated_by

Historical percentage indicators may remain NULL.

Reason:

No historical evidence is not the same as 0% performance.

For example:

```text
on_time_delivery_rate = NULL
```

can mean:

```text
no usable timing evidence
```

while:

```text
on_time_delivery_rate = 0
```

means:

```text
0% of observed eligible timing outcomes were on time.
```

Those meanings must never be collapsed.

---

# 11. Supplier selection decision

Required:

* procurement_id
* supplier_id
* decision_sequence
* decision_type
* decision_reason
* evaluation_snapshot
* decided_by
* decided_at
* created_at

`supersedes_decision_id` may be NULL for the initial selection.

---

# 12. Purchase order

Required:

* procurement_id
* supplier_id
* order_number
* order_date
* currency
* status
* created_by
* created_at
* updated_at

`expected_delivery_date` may be NULL only if the final procurement process allows the PO to exist before an expected date is established.

---

# 13. Purchase order line

Required:

* purchase_order_id
* procurement_item_id
* quantity
* unit
* created_at

Optional:

* description
* unit_price if price is not yet recorded
* line_total if derived/calculated later

Do not make price NOT NULL merely because many POs eventually have a price.

Ask whether a valid PO can exist before price is recorded.

---

# 14. Supplier commitment

Required:

* purchase_order_id
* purchase_order_line_id
* supplier_id
* promised_qty
* status
* submitted_by
* submitted_at
* created_at/updated_at as used

Potentially optional:

* delivery_start
* delivery_end if the domain permits incomplete commitment scheduling
* accepted_by
* accepted_at
* rejected_by
* rejected_at
* rejection_reason

Those actor/time fields become meaningful only when the corresponding event has occurred.

---

# 15. Delivery

Required:

* commitment_id
* receiving_user_id
* delivery_date
* delivery_status
* delivery_sequence
* created_at
* updated_at

Optional:

* parent_delivery_id
* notes

Supplier and procurement should not be duplicated as mandatory fields if they are derivable through the commitment chain.

---

# 16. Delivery line

Required:

* delivery_id
* procurement_item_id
* expected_quantity
* actual_quantity
* created_at
* updated_at

`actual_quantity` must remain NOT NULL because zero is meaningful.

Zero means:

```text nothing was delivered for this line
```

NULL would mean:

```text actual quantity is unknown/not recorded
```

Those are different domain meanings.

---

# 17. Inspection

Required:

* delivery_id
* result
* received_qty
* quality_status
* delay_status
* inspected_by
* inspected_at
* created_at

Optional:

* rejection_reason
* notes

But `rejection_reason` becomes conditionally required when result = REJECTED.

That is handled by a conditional CHECK.

---

# 18. Corrective action

Required:

* inspection_id
* description
* status
* created_by
* created_at

Optional:

* replacement_delivery_id
* completed_at

`completed_at` should remain NULL until the corrective action is actually completed.

---

# 19. Evidence documents

Required:

* procurement_id
* document_type
* document_name
* original_filename
* mime_type
* file_size
* storage_reference
* visibility
* uploaded_by
* uploaded_at

Optional:

* event_id
* deleted_at
* deleted_by
* deletion_reason

The current Feature 12 structure intentionally makes event linkage optional.

---

# 20. Procurement events

Required:

* procurement_id
* event_type
* title
* actor_id
* occurred_at
* created_at

Optional:

* description
* entity_type
* entity_id
* metadata

---

# 21. Audit events

Required:

* procurement_id
* actor_id
* action
* entity_type
* created_at

Optional:

* entity_id
* previous_state
* new_state
* metadata

---

# 22. Supplier performance

Required:

* supplier_id
* observation_count
* completed_procurement_count
* completed_commitment_count
* promised_quantity
* accepted_quantity
* timing_observation_count
* quality_observation_count
* status
* calculation_version
* calculated_at

Performance rates may be NULL when evidence is insufficient.

The current Feature 15 schema correctly distinguishes counts from rates and allows rate NULLs.

---

# 23. NULL decision rule

For every field ask:

### Question 1

Can the record exist before this value is known?

If yes:

`NULL may be legitimate.`

### Question 2

Would NULL mean "unknown" while zero/false/empty means something else?

If yes:

`retain NULL semantics.`

### Question 3

Does the record become meaningless without this value?

If yes:

`NOT NULL.`

### Question 4

Is the field only required after a particular state/event?

If yes:

`NOT NULL may not be appropriate globally.`

Use a conditional CHECK or service validation instead.

---

# 24. Final principle

Do not use NOT NULL merely to make the database look strict.

Use it to preserve meaning.

`NULL` should be intentional.

NOT NULL audit status:

IN PROGRESS — final baseline reconstruction required.
