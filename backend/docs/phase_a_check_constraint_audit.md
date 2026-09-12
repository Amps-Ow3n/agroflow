# Phase A CHECK Constraint Audit

## Purpose

CHECK constraints protect domain invariants directly inside PostgreSQL.

The audit classifies fields into:

* positive
* non-negative
* percentage
* enum
* date relationship
* state
* text
* cross-field/domain relationship

The database constraint is the final structural backstop.

Application/Pydantic validation remains useful for early and user-friendly validation.

---

# 1. Positive quantities

These values represent quantities that must exist in a meaningful amount.

| Table                | Field             | Rule  |
| -------------------- | ----------------- | ----- |
| procurement_items    | quantity          | `> 0` |
| purchase_order_lines | quantity          | `> 0` |
| supplier_commitments | promised_qty      | `> 0` |
| delivery_lines       | expected_quantity | `> 0` |

PostgreSQL protection:

```sql
CHECK (quantity > 0)
```

or equivalent field-specific constraint.

---

# 2. Non-negative quantities and monetary values

These values may legitimately be zero but must not be negative.

| Table                        | Field                       | Rule           |
| ---------------------------- | --------------------------- | -------------- |
| purchase_order_lines         | unit_price                  | NULL or `>= 0` |
| purchase_order_lines         | line_total                  | NULL or `>= 0` |
| delivery_lines               | actual_quantity             | `>= 0`         |
| inspections                  | received_qty                | `>= 0`         |
| procurements                 | estimated_cost              | NULL or `>= 0` |
| supplier_performance_metrics | promised_quantity           | `>= 0`         |
| supplier_performance_metrics | accepted_quantity           | `>= 0`         |
| supplier_performance_metrics | observation_count           | `>= 0`         |
| supplier_performance_metrics | completed_procurement_count | `>= 0`         |
| supplier_performance_metrics | completed_commitment_count  | `>= 0`         |
| supplier_performance_metrics | timing_observation_count    | `>= 0`         |
| supplier_performance_metrics | quality_observation_count   | `>= 0`         |

---

# 3. Percentages

Percentage values must be:

`0 <= value <= 100`

Fields:

* fulfilment_rate
* quantity_variance_rate
* on_time_delivery_rate
* quality_acceptance_rate

This applies to:

* supplier_evaluations
* supplier_performance_metrics

NULL remains allowed where the system intentionally has insufficient evidence.

Therefore:

```sql
CHECK (
    fulfilment_rate IS NULL
    OR fulfilment_rate BETWEEN 0 AND 100
)
```

The same pattern applies to the other percentage fields.

---

# 4. Enum constraints

Enumerated domain values must be explicitly restricted.

## Organization

`organization_type`:

* SCHOOL
* SUPPLIER

`status`:

* PENDING
* ACTIVE
* SUSPENDED

`verification_status`:

* PENDING
* VERIFIED
* REJECTED

## Membership

`status`:

* PENDING
* ACTIVE
* SUSPENDED

## Responsibility

`organization_type`:

* SCHOOL
* SUPPLIER
* ANY
* NULL where intentionally permitted

## Supplier

`status`:

* ACTIVE
* SUSPENDED
* ARCHIVED

## Supplier registry child records

`status`:

* ACTIVE
* INACTIVE

## Procurement

Final lifecycle:

* DRAFT
* SUBMITTED
* EVALUATION
* SELECTED
* ORDERED
* COMMITTED
* DELIVERY
* INSPECTION
* ACCEPTED
* COMPLETED
* CANCELLED

The old:

* OPEN
* CLOSED

states must not remain in the final schema.

## Supplier evaluation

`evaluation_status`:

* ELIGIBLE
* INELIGIBLE

`capacity_status`:

* SUFFICIENT
* INSUFFICIENT
* UNKNOWN

`historical_evidence_status`:

* AVAILABLE
* NO_HISTORY
* INSUFFICIENT_EVIDENCE where supported by the final model

## Selection

`decision_type`:

* INITIAL_SELECTION
* RESELECTION

## Purchase order

Current historical values:

* DRAFT
* ISSUED
* CLOSED
* CANCELLED

Final accepted values must be confirmed against the approved PO lifecycle before baseline construction.

## Commitment

* SUBMITTED
* ACCEPTED
* REJECTED
* CANCELLED

## Delivery

* AWAITING_INSPECTION
* ACCEPTED
* REJECTED

## Inspection

`result`:

* ACCEPTED
* REJECTED

`quality_status`:

* GOOD
* FAILED

`delay_status`:

* ON_TIME
* DELAYED

## Corrective action

* OPEN
* COMPLETED
* CANCELLED

## Evidence

Document types must use the approved Phase A document vocabulary.

Visibility:

* INTERNAL
* SUPPLIER_VISIBLE

## Performance

* NO_HISTORY
* AVAILABLE

---

# 5. Date relationships

Dates must preserve chronological meaning.

## Procurement

If both are present:

`required_by_date >= procurement_date`

## Purchase order

If expected delivery date is present:

`expected_delivery_date >= order_date`

## Commitment

If a delivery window is used:

`delivery_end >= delivery_start`

## Corrective action

If `completed_at` exists, it must not precede `created_at`.

## Verification

If `reviewed_at` exists, it should correspond to a reviewed status.

Date relationships that require another row/entity must remain service-level rules unless PostgreSQL can enforce them safely without creating architectural coupling.

---

# 6. State constraints

State fields must contain only approved state values.

State validity is different from state transition validity.

Database CHECK:

```text
Does the state name exist?
```

Service/domain logic:

```text
Is this transition allowed?
```

For procurement:

```text
DRAFT
→ SUBMITTED
→ EVALUATION
→ SELECTED
→ ORDERED
→ COMMITTED
→ DELIVERY
→ INSPECTION
→ ACCEPTED
→ COMPLETED
```

Cancellation:

```text
DRAFT → CANCELLED
SUBMITTED → CANCELLED
```

The database must restrict invalid state names.

The service must enforce valid transitions.

---

# 7. Text constraints

Text fields requiring meaningful content should reject empty/whitespace-only values where the domain requires meaningful text.

Examples:

* procurement title
* item name
* unit
* contact name
* decision reason
* corrective action description
* evidence document name

Pattern:

```sql
CHECK (length(trim(field)) >= 1)
```

or a stronger minimum where the domain requires it.

Do not add arbitrary minimum lengths merely for the sake of adding constraints.

---

# 8. Conditional constraints

Some invariants depend on another field.

## Inspection rejection reason

If:

`result = REJECTED`

then:

`rejection_reason` must be present and meaningful.

If:

`result = ACCEPTED`

then:

`rejection_reason` must be NULL.

The current migration already implements this logic.

## Corrective action

A corrective action must represent a valid corrective-action state.

The rule that it can only be created after a rejected inspection is a service/domain rule and should not be reduced to a simple field CHECK.

---

# 9. Derived values

Do not store CHECK constraints for values that are not authoritative facts.

Feature 14 derives:

* shortfall
* variance
* lateness
* repetition

These are calculated from authoritative procurement facts.

They should not become stored domain facts merely to satisfy Feature 20.

---

# 10. Final rule

For every field ask:

1. What values are mathematically impossible?
2. What values are structurally invalid?
3. What values violate an enum?
4. What values violate a same-row relationship?
5. Is NULL meaningful?
6. Is this actually a cross-row business rule?

Then choose:

`CHECK`

or

`NOT NULL`

or

`service validation`

or

`transaction/concurrency control`.

CHECK audit status:

IN PROGRESS — final baseline reconstruction required.
