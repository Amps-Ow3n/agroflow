# AgroFlow Phase A — Identity Map

| Identifier | Meaning | Authoritative Table | Type |
|---|---|---|---|
| user_id | human account | users.id | User |
| organization_id | organization | organizations.id | Organization |
| membership_id | user ↔ organization relationship | organization_memberships.id | Membership |
| responsibility_id | defined responsibility | responsibilities.id | Responsibility |
| supplier_id | supplier business entity | suppliers.id | Supplier |
| procurement_id | procurement record | procurements.id | Procurement |
| procurement_item_id | procurement item | procurement_items.id | Procurement Item |
| purchase_order_id | purchase order | purchase_orders.id | Purchase Order |
| purchase_order_line_id | PO line | purchase_order_lines.id | PO Line |
| commitment_id | supplier commitment | supplier_commitments.id | Commitment |
| delivery_id | delivery event | deliveries.id | Delivery |
| delivery_line_id | delivery line | delivery_lines.id | Delivery Line |
| inspection_id | inspection | inspections.id | Inspection |
| corrective_action_id | corrective action | corrective_actions.id | Corrective Action |
| evidence_id | evidence | evidence_documents.id | Evidence |
| event_id | procurement event | procurement_events.id | Procurement Event |
| audit_event_id | audit event | audit_events.id | Audit Event |

## Organization Identity Rule

There is no separate Phase A School entity.

A school is represented by:

organizations.id
where:
organization_type = 'SCHOOL'

Therefore:

school_id must not be used as a substitute
for organization_id.

## Identity Semantics

user_id
    → users.id
    → human identity

organization_id
    → organizations.id
    → organizational ownership/scope

supplier_id
    → suppliers.id
    → supplier business identity

actor_id
    → users.id
    → human who performed an action

membership_id
    → organization_memberships.id
    → relationship between user and organization

school_id
    → NOT a Phase A authoritative identity
    → use organization_id where organization_type = SCHOOL

supplier_entity_id
    → NOT a Phase A authoritative identity
    → replace with supplier_id referencing suppliers.id