# AgroFlow Phase A — Authoritative Domain Dependency Graph

## Identity

User
└── Organization Membership
    └── Organization

Organization
├── Memberships
├── Verification Records
├── Supplier
└── Procurements

## Supplier

Supplier
├── Supplier Products
├── Supplier Capabilities
├── Supplier Contacts
├── Supplier Evaluations
├── Supplier Selection Decisions
├── Purchase Orders
├── Supplier Commitments
└── Supplier Performance Metrics

## Procurement

Procurement
├── Procurement Items
├── Supplier Evaluations
├── Supplier Selection Decisions
├── Purchase Order
│   └── Purchase Order Lines
└── Supplier Commitments
    └── Deliveries
        ├── Delivery Lines
        ├── Inspections
        └── Corrective Actions

## Evidence and History

Procurement
├── Evidence
├── Procurement Events
└── Audit Events

## Derived Intelligence

Supplier
└── Supplier Performance Metrics

## Cardinalities

User
    1 ──── * OrganizationMembership

Organization
    1 ──── * OrganizationMembership

Organization
    1 ──── 0..1 Supplier

Organization
    1 ──── * Procurement

Supplier
    1 ──── * SupplierProduct

Supplier
    1 ──── * SupplierCapability

Supplier
    1 ──── * SupplierContact

Procurement
    1 ──── * ProcurementItem

Procurement
    1 ──── * SupplierEvaluation

Procurement
    1 ──── * SupplierSelectionDecision

Procurement
    1 ──── 0..1 PurchaseOrder

PurchaseOrder
    1 ──── * PurchaseOrderLine

PurchaseOrderLine
    1 ──── * SupplierCommitment

SupplierCommitment
    1 ──── * Delivery

Delivery
    1 ──── * DeliveryLine

Delivery
    1 ──── 0..1 Inspection

Inspection
    1 ──── 0..1 CorrectiveAction

Procurement
    1 ──── * Evidence

Procurement
    1 ──── * ProcurementEvent

Procurement
    1 ──── * AuditEvent

Supplier
    1 ──── 0..1 PerformanceMetric

## Authoritative Procurement Chain

Organization
    ↓
Procurement
    ↓
Purchase Order
    ↓
Purchase Order Line
    ↓
Supplier Commitment
    ↓
Delivery
    ↓
Inspection

## Derived Relationships

The following should normally be derived rather than independently stored:

Delivery → Supplier
Delivery → Procurement
Commitment → Organization
PO Line → Organization
Inspection → Supplier
Inspection → Procurement

## Dependency Rules

1. Membership depends on User and Organization.

2. Supplier depends on Organization.

3. Procurement depends on a SCHOOL Organization.

4. Procurement Items depend on Procurement.

5. Supplier Evaluation depends on Procurement and Supplier.

6. Supplier Selection Decision depends on Procurement and Supplier.

7. Purchase Order depends on Procurement and Supplier.

8. Purchase Order Line depends on Purchase Order and Procurement Item.

9. Supplier Commitment depends on Purchase Order,
   Purchase Order Line and Supplier.

10. Delivery depends on Supplier Commitment.

11. Delivery Line depends on Delivery and Procurement Item.

12. Inspection depends on Delivery.

13. Corrective Action depends on Inspection and replacement Delivery.

14. Evidence belongs to the Procurement aggregate
    and may reference the relevant Procurement Event.

15. Procurement Events belong to Procurement.

16. Audit Events belong to Procurement and identify the actor.

17. Performance Metrics depend on Supplier and historical procurement data.