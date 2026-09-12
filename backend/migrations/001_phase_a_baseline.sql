-- ============================================================
-- AGROFLOW PHASE A
-- 001 — CLEAN DATABASE BASELINE
-- ============================================================
--
-- This is the canonical Phase-A database schema.
--
-- The database is currently disposable/development-only.
-- Therefore this migration intentionally does NOT migrate
-- obsolete agricultural/legacy AgroFlow tables.
--
-- Domain:
--
-- Organization
--      ↓
-- Membership
--      ↓
-- Responsibility
--
-- Supplier
--      ↓
-- Evaluation
--      ↓
-- Selection
--      ↓
-- Purchase Order
--      ↓
-- Commitment
--      ↓
-- Delivery
--      ↓
-- Inspection
--      ↓
-- Acceptance / Rejection
--      ↓
-- Corrective Action / Completion
--
-- Historical truth:
--
-- procurement_events
-- audit_events
-- evidence_documents
--
-- ============================================================

BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';


-- ============================================================
-- 1. USERS
-- ============================================================

CREATE TABLE users (

    id BIGSERIAL PRIMARY KEY,

    name TEXT NOT NULL,

    email TEXT NOT NULL UNIQUE,

    password TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'ACTIVE',

    is_system_admin BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT users_status_check
        CHECK (
            status IN (
                'PENDING',
                'ACTIVE',
                'SUSPENDED'
            )
        )
);


CREATE INDEX idx_users_system_admin
ON users(is_system_admin)
WHERE is_system_admin = TRUE;


-- ============================================================
-- 2. ORGANIZATIONS
-- ============================================================

CREATE TABLE organizations (

    id BIGSERIAL PRIMARY KEY,

    name TEXT NOT NULL,

    organization_type TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'PENDING',

    verification_status TEXT NOT NULL DEFAULT 'PENDING',

    registration_number TEXT,

    school_identifier TEXT,

    address TEXT,

    phone TEXT,

    email TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT organizations_type_check
        CHECK (
            organization_type IN (
                'SCHOOL',
                'SUPPLIER'
            )
        ),

    CONSTRAINT organizations_status_check
        CHECK (
            status IN (
                'PENDING',
                'ACTIVE',
                'SUSPENDED'
            )
        ),

    CONSTRAINT organizations_verification_check
        CHECK (
            verification_status IN (
                'PENDING',
                'VERIFIED',
                'REJECTED'
            )
        )
);

CREATE INDEX idx_organizations_type
ON organizations(organization_type);


CREATE INDEX idx_organizations_verification
ON organizations(verification_status);


-- ============================================================
-- 3. ORGANIZATION MEMBERSHIPS
-- ============================================================

CREATE TABLE organization_memberships (

    id BIGSERIAL PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    user_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL DEFAULT 'PENDING',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT memberships_status_check
        CHECK (
            status IN (
                'PENDING',
                'ACTIVE',
                'SUSPENDED',
                'REJECTED'
            )
        ),

    CONSTRAINT memberships_unique_user
        UNIQUE (
            organization_id,
            user_id
        )
);

CREATE INDEX idx_memberships_user
ON organization_memberships(user_id);


-- ============================================================
-- 4. RESPONSIBILITIES
-- ============================================================

CREATE TABLE responsibilities (

    id BIGSERIAL PRIMARY KEY,

    code TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    description TEXT,

    organization_type TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT responsibilities_org_type_check
        CHECK (
            organization_type IS NULL
            OR organization_type IN (
                'SCHOOL',
                'SUPPLIER',
                'ANY'
            )
        )
);


-- ============================================================
-- 5. MEMBERSHIP RESPONSIBILITIES
-- ============================================================

CREATE TABLE membership_responsibilities (

    membership_id BIGINT NOT NULL
        REFERENCES organization_memberships(id)
        ON DELETE CASCADE,

    responsibility_id BIGINT NOT NULL
        REFERENCES responsibilities(id)
        ON DELETE RESTRICT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        membership_id,
        responsibility_id
    )
);


-- ============================================================
-- 6. ORGANIZATION VERIFICATION RECORDS
-- ============================================================

CREATE TABLE organization_verification_records (

    id BIGSERIAL PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(id)
        ON DELETE CASCADE,

    status TEXT NOT NULL,

    verification_type TEXT NOT NULL,

    submitted_by BIGINT
        REFERENCES users(id)
        ON DELETE SET NULL,

    reviewed_by BIGINT
        REFERENCES users(id)
        ON DELETE SET NULL,

    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    reviewed_at TIMESTAMP,

    reason TEXT,

    evidence_reference TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT verification_status_check
        CHECK (
            status IN (
                'PENDING',
                'VERIFIED',
                'REJECTED'
            )
        ),

    CONSTRAINT verification_type_check
        CHECK (
            verification_type IN (
                'SCHOOL',
                'SUPPLIER'
            )
        )
);

CREATE INDEX idx_verification_records_organization
ON organization_verification_records(organization_id);

CREATE INDEX idx_verification_records_status
ON organization_verification_records(status);

CREATE INDEX idx_organizations_verification_status
ON organizations(verification_status);

CREATE INDEX idx_organizations_type_status
ON organizations(
    organization_type,
    status
);
-- ============================================================
-- 7. SUPPLIERS
-- ============================================================

CREATE TABLE suppliers (

    id BIGSERIAL PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    status TEXT NOT NULL DEFAULT 'ACTIVE',

    supplier_code TEXT UNIQUE,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT suppliers_status_check
        CHECK (
            status IN (
                'ACTIVE',
                'SUSPENDED',
                'ARCHIVED'
            )
        ),

    CONSTRAINT suppliers_one_per_organization
        UNIQUE (organization_id)
);


CREATE INDEX idx_suppliers_status
ON suppliers(status);


-- ============================================================
-- 8. SUPPLIER CAPABILITIES
-- ============================================================

CREATE TABLE supplier_capabilities (

    id BIGSERIAL PRIMARY KEY,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    capability TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT supplier_capabilities_status_check
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE'
            )
        ),

    CONSTRAINT supplier_capabilities_unique
        UNIQUE (
            supplier_id,
            capability
        )
);


-- ============================================================
-- 9. SUPPLIER PRODUCTS
-- ============================================================

CREATE TABLE supplier_products (

    id BIGSERIAL PRIMARY KEY,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    product TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT supplier_products_status_check
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE'
            )
        ),

    CONSTRAINT supplier_products_unique
        UNIQUE (
            supplier_id,
            product
        )
);


CREATE INDEX idx_supplier_products_product
ON supplier_products(product);


-- ============================================================
-- 10. SUPPLIER CONTACTS
-- ============================================================

CREATE TABLE supplier_contacts (

    id BIGSERIAL PRIMARY KEY,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    contact_name TEXT NOT NULL,

    phone TEXT,

    email TEXT,

    role TEXT,

    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    status TEXT NOT NULL DEFAULT 'ACTIVE',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT supplier_contacts_status_check
        CHECK (
            status IN (
                'ACTIVE',
                'INACTIVE'
            )
        )
);


CREATE INDEX idx_supplier_contacts_supplier
ON supplier_contacts(supplier_id);


-- ============================================================
-- 11. PROCUREMENTS
-- ============================================================

CREATE TABLE procurements (

    id BIGSERIAL PRIMARY KEY,

    organization_id BIGINT NOT NULL
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    created_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    requesting_user_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    procurement_identifier VARCHAR(30) UNIQUE,

    title VARCHAR(200) NOT NULL,

    description TEXT,

    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',

    procurement_date DATE,

    required_by_date DATE,

    location VARCHAR(200),

    specifications TEXT,

    quality_requirements TEXT,

    estimated_cost NUMERIC(16,2),

    procurement_method VARCHAR(80),

    notes TEXT,

    requesting_department VARCHAR(200),

    submitted_at TIMESTAMP,

    cancelled_at TIMESTAMP,

    cancellation_reason TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT procurements_status_check
        CHECK (
            status IN (
                'DRAFT',
                'SUBMITTED',
                'EVALUATION',
                'SELECTED',
                'ORDERED',
                'COMMITTED',
                'DELIVERY',
                'INSPECTION',
                'ACCEPTED',
                'COMPLETED',
                'CANCELLED'
            )
        ),

    CONSTRAINT procurements_dates_check
        CHECK (
            required_by_date IS NULL
            OR procurement_date IS NULL
            OR required_by_date >= procurement_date
        ),

    CONSTRAINT procurements_cost_check
        CHECK (
            estimated_cost IS NULL
            OR estimated_cost >= 0
        )
);


CREATE INDEX idx_procurements_organization
ON procurements(organization_id);


CREATE INDEX idx_procurements_status
ON procurements(status);


CREATE INDEX idx_procurements_created_by
ON procurements(created_by);


CREATE INDEX idx_procurements_requesting_user
ON procurements(requesting_user_id);


CREATE INDEX idx_procurements_required_date
ON procurements(required_by_date);


-- ============================================================
-- 12. PROCUREMENT ITEMS
-- ============================================================

CREATE TABLE procurement_items (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE CASCADE,

    item_name VARCHAR(200) NOT NULL,

    description TEXT,

    quantity NUMERIC(16,2) NOT NULL,

    unit VARCHAR(50) NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT procurement_items_quantity_check
        CHECK (quantity > 0)
);


CREATE INDEX idx_procurement_items_procurement
ON procurement_items(procurement_id);


-- ============================================================
-- 13. SUPPLIER EVALUATIONS
-- ============================================================

CREATE TABLE supplier_evaluations (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE CASCADE,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,

    evaluation_status VARCHAR(30) NOT NULL,

    required_item_match BOOLEAN NOT NULL,

    mandatory_eligible BOOLEAN NOT NULL,

    verification_status VARCHAR(30) NOT NULL,

    capacity_status VARCHAR(30) NOT NULL,

    historical_evidence_status VARCHAR(30) NOT NULL,

    historical_delivery_count INTEGER NOT NULL DEFAULT 0,

    historical_commitment_count INTEGER NOT NULL DEFAULT 0,

    fulfilled_quantity NUMERIC(16,2) NOT NULL DEFAULT 0,

    promised_quantity NUMERIC(16,2) NOT NULL DEFAULT 0,

    fulfilment_rate NUMERIC(6,2),

    on_time_delivery_rate NUMERIC(6,2),

    quantity_variance_rate NUMERIC(6,2),

    quality_acceptance_rate NUMERIC(6,2),

    indicator_explanation TEXT NOT NULL,

    evaluated_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    evaluated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT supplier_evaluations_unique
        UNIQUE (
            procurement_id,
            supplier_id
        ),

    CONSTRAINT supplier_evaluation_status_check
        CHECK (
            evaluation_status IN (
                'ELIGIBLE',
                'INELIGIBLE'
            )
        ),

    CONSTRAINT supplier_evaluation_capacity_check
        CHECK (
            capacity_status IN (
                'SUFFICIENT',
                'INSUFFICIENT',
                'UNKNOWN'
            )
        ),

    CONSTRAINT supplier_evaluation_history_check
        CHECK (
            historical_evidence_status IN (
                'AVAILABLE',
                'NO_HISTORY'
            )
        ),

    CONSTRAINT supplier_evaluation_quantity_check
        CHECK (
            historical_delivery_count >= 0
            AND historical_commitment_count >= 0
            AND fulfilled_quantity >= 0
            AND promised_quantity >= 0
        ),

    CONSTRAINT supplier_evaluation_rates_check
        CHECK (
            (
                fulfilment_rate IS NULL
                OR fulfilment_rate BETWEEN 0 AND 100
            )
            AND
            (
                on_time_delivery_rate IS NULL
                OR on_time_delivery_rate BETWEEN 0 AND 100
            )
            AND
            (
                quantity_variance_rate IS NULL
                OR quantity_variance_rate BETWEEN 0 AND 100
            )
            AND
            (
                quality_acceptance_rate IS NULL
                OR quality_acceptance_rate BETWEEN 0 AND 100
            )
        )
);


CREATE INDEX idx_supplier_evaluations_procurement
ON supplier_evaluations(procurement_id);


CREATE INDEX idx_supplier_evaluations_supplier
ON supplier_evaluations(supplier_id);


-- ============================================================
-- 14. SUPPLIER SELECTION DECISIONS
-- ============================================================

CREATE TABLE supplier_selection_decisions (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE RESTRICT,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,

    decision_sequence INTEGER NOT NULL,

    decision_type TEXT NOT NULL,

    decision_reason TEXT NOT NULL,

    evaluation_snapshot JSONB NOT NULL,

    supersedes_decision_id BIGINT
        REFERENCES supplier_selection_decisions(id)
        ON DELETE RESTRICT,

    decided_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    decided_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT selection_sequence_positive
        CHECK (decision_sequence > 0),

    CONSTRAINT selection_decision_type_check
        CHECK (
            decision_type IN (
                'INITIAL_SELECTION',
                'RESELECTION'
            )
        ),

    CONSTRAINT selection_unique_sequence
        UNIQUE (
            procurement_id,
            decision_sequence
        )
);


CREATE INDEX idx_selection_decisions_supplier
ON supplier_selection_decisions(supplier_id);


CREATE INDEX idx_selection_decisions_decided_by
ON supplier_selection_decisions(decided_by);


CREATE INDEX idx_selection_decisions_supersedes
ON supplier_selection_decisions(supersedes_decision_id);


-- ============================================================
-- 15. PURCHASE ORDER NUMBER SEQUENCE
-- ============================================================

CREATE SEQUENCE purchase_order_number_seq
START 1;


-- ============================================================
-- 16. PURCHASE ORDERS
-- ============================================================

CREATE TABLE purchase_orders (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE RESTRICT,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,

    order_number VARCHAR(50) NOT NULL UNIQUE,

    order_date DATE NOT NULL DEFAULT CURRENT_DATE,

    expected_delivery_date DATE,

    currency VARCHAR(10) NOT NULL DEFAULT 'UGX',

    notes TEXT,

    status VARCHAR(30) NOT NULL DEFAULT 'ISSUED',

    created_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT purchase_orders_status_check
        CHECK (
            status IN (
                'DRAFT',
                'ISSUED',
                'CLOSED',
                'CANCELLED'
            )
        ),

    CONSTRAINT purchase_orders_dates_check
        CHECK (
            expected_delivery_date IS NULL
            OR expected_delivery_date >= order_date
        ),

    CONSTRAINT purchase_orders_one_per_procurement
        UNIQUE (procurement_id)
);


CREATE INDEX idx_purchase_orders_supplier
ON purchase_orders(supplier_id);


-- ============================================================
-- 17. PURCHASE ORDER LINES
-- ============================================================

CREATE TABLE purchase_order_lines (

    id BIGSERIAL PRIMARY KEY,

    purchase_order_id BIGINT NOT NULL
        REFERENCES purchase_orders(id)
        ON DELETE CASCADE,

    procurement_item_id BIGINT NOT NULL
        REFERENCES procurement_items(id)
        ON DELETE RESTRICT,

    description TEXT,

    quantity NUMERIC(16,2) NOT NULL,

    unit VARCHAR(50) NOT NULL,

    unit_price NUMERIC(16,2),

    line_total NUMERIC(16,2),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT purchase_order_lines_quantity_check
        CHECK (quantity > 0),

    CONSTRAINT purchase_order_lines_price_check
        CHECK (
            unit_price IS NULL
            OR unit_price >= 0
        ),

    CONSTRAINT purchase_order_lines_total_check
        CHECK (
            line_total IS NULL
            OR line_total >= 0
        ),

    CONSTRAINT purchase_order_lines_unique_item
        UNIQUE (
            purchase_order_id,
            procurement_item_id
        )
);


CREATE INDEX idx_purchase_order_lines_item
ON purchase_order_lines(procurement_item_id);


-- ============================================================
-- 18. SUPPLIER COMMITMENTS
-- ============================================================

CREATE TABLE supplier_commitments (

    id BIGSERIAL PRIMARY KEY,

    purchase_order_id BIGINT NOT NULL
        REFERENCES purchase_orders(id)
        ON DELETE RESTRICT,

    purchase_order_line_id BIGINT NOT NULL
        REFERENCES purchase_order_lines(id)
        ON DELETE RESTRICT,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,

    promised_qty NUMERIC(16,2) NOT NULL,

    delivery_start DATE NOT NULL,

    delivery_end DATE NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'SUBMITTED',

    submitted_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    submitted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    accepted_by BIGINT
        REFERENCES users(id)
        ON DELETE RESTRICT,

    accepted_at TIMESTAMP,

    rejected_by BIGINT
        REFERENCES users(id)
        ON DELETE RESTRICT,

    rejected_at TIMESTAMP,

    rejection_reason TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT commitments_quantity_check
        CHECK (promised_qty > 0),

    CONSTRAINT commitments_delivery_window_check
        CHECK (delivery_end >= delivery_start),

    CONSTRAINT commitments_status_check
        CHECK (
            status IN (
                'SUBMITTED',
                'ACCEPTED',
                'REJECTED',
                'CANCELLED'
            )
        )
);


CREATE INDEX idx_commitments_purchase_order
ON supplier_commitments(purchase_order_id);


CREATE INDEX idx_commitments_purchase_order_line
ON supplier_commitments(purchase_order_line_id);


CREATE INDEX idx_commitments_supplier
ON supplier_commitments(supplier_id);


CREATE INDEX idx_commitments_status
ON supplier_commitments(status);


CREATE UNIQUE INDEX uq_active_commitment_per_po_line_supplier
ON supplier_commitments(
    purchase_order_line_id,
    supplier_id
)
WHERE status IN (
    'SUBMITTED',
    'ACCEPTED'
);


-- ============================================================
-- 19. DELIVERIES
-- ============================================================
--
-- IMPORTANT:
--
-- The delivery header describes the physical delivery event.
--
-- Actual quantities live in delivery_lines.
--
-- We deliberately do NOT duplicate quantity facts on the
-- delivery header.
-- ============================================================

CREATE TABLE deliveries (

    id BIGSERIAL PRIMARY KEY,

    commitment_id BIGINT NOT NULL
        REFERENCES supplier_commitments(id)
        ON DELETE RESTRICT,

    parent_delivery_id BIGINT
        REFERENCES deliveries(id)
        ON DELETE RESTRICT,

    delivery_sequence INTEGER NOT NULL,

    delivery_date DATE NOT NULL,

    condition VARCHAR(100) NOT NULL,

    notes TEXT,

    receiving_user_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    delivery_status VARCHAR(40) NOT NULL DEFAULT 'AWAITING_INSPECTION',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT deliveries_status_check
        CHECK (
            delivery_status IN (
                'AWAITING_INSPECTION',
                'ACCEPTED',
                'REJECTED'
            )
        ),

    CONSTRAINT deliveries_sequence_check
        CHECK (delivery_sequence > 0),

    CONSTRAINT deliveries_unique_sequence
        UNIQUE (
            commitment_id,
            delivery_sequence
        )
);


CREATE INDEX idx_deliveries_commitment
ON deliveries(commitment_id);


CREATE INDEX idx_deliveries_parent
ON deliveries(parent_delivery_id);


CREATE INDEX idx_deliveries_status
ON deliveries(delivery_status);


CREATE INDEX idx_deliveries_date
ON deliveries(delivery_date);


-- ============================================================
-- 20. DELIVERY LINES
-- ============================================================

CREATE TABLE delivery_lines (

    id BIGSERIAL PRIMARY KEY,

    delivery_id BIGINT NOT NULL
        REFERENCES deliveries(id)
        ON DELETE CASCADE,

    procurement_item_id BIGINT NOT NULL
        REFERENCES procurement_items(id)
        ON DELETE RESTRICT,

    actual_quantity NUMERIC(16,2) NOT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT delivery_lines_quantity_check
        CHECK (actual_quantity >= 0),

    CONSTRAINT delivery_lines_unique_item
        UNIQUE (
            delivery_id,
            procurement_item_id
        )
);


CREATE INDEX idx_delivery_lines_item
ON delivery_lines(procurement_item_id);


-- ============================================================
-- 21. INSPECTIONS
-- ============================================================

CREATE TABLE inspections (

    id BIGSERIAL PRIMARY KEY,

    delivery_id BIGINT NOT NULL
        REFERENCES deliveries(id)
        ON DELETE RESTRICT,

    result VARCHAR(20) NOT NULL,

    received_qty NUMERIC(16,2) NOT NULL,

    quality_status VARCHAR(30) NOT NULL,

    delay_status VARCHAR(30) NOT NULL,

    rejection_reason TEXT,

    notes TEXT,

    inspected_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    inspected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT inspections_result_check
        CHECK (
            result IN (
                'ACCEPTED',
                'REJECTED'
            )
        ),

    CONSTRAINT inspections_received_quantity_check
        CHECK (received_qty >= 0),

    CONSTRAINT inspections_quality_check
        CHECK (
            quality_status IN (
                'GOOD',
                'FAILED'
            )
        ),

    CONSTRAINT inspections_delay_check
        CHECK (
            delay_status IN (
                'ON_TIME',
                'DELAYED'
            )
        ),

    CONSTRAINT inspections_rejection_reason_check
        CHECK (
            (
                result = 'ACCEPTED'
                AND rejection_reason IS NULL
            )
            OR
            (
                result = 'REJECTED'
                AND rejection_reason IS NOT NULL
                AND length(trim(rejection_reason)) >= 2
            )
        ),

    CONSTRAINT inspections_one_per_delivery
        UNIQUE (delivery_id)
);


CREATE INDEX idx_inspections_inspected_by
ON inspections(inspected_by);


CREATE INDEX idx_inspections_result
ON inspections(result);


-- ============================================================
-- 22. CORRECTIVE ACTIONS
-- ============================================================

CREATE TABLE corrective_actions (

    id BIGSERIAL PRIMARY KEY,

    inspection_id BIGINT NOT NULL
        REFERENCES inspections(id)
        ON DELETE RESTRICT,

    description TEXT NOT NULL,

    status VARCHAR(30) NOT NULL DEFAULT 'OPEN',

    replacement_delivery_id BIGINT
        REFERENCES deliveries(id)
        ON DELETE RESTRICT,

    created_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMP,

    CONSTRAINT corrective_actions_status_check
        CHECK (
            status IN (
                'OPEN',
                'COMPLETED',
                'CANCELLED'
            )
        ),

    CONSTRAINT corrective_actions_description_check
        CHECK (
            length(trim(description)) >= 2
        ),

    CONSTRAINT corrective_actions_one_per_inspection
        UNIQUE (inspection_id)
);


CREATE INDEX idx_corrective_actions_status
ON corrective_actions(status);


CREATE INDEX idx_corrective_actions_replacement
ON corrective_actions(replacement_delivery_id);


-- ============================================================
-- 23. PROCUREMENT EVENTS
-- ============================================================

CREATE TABLE procurement_events (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE RESTRICT,

    event_type VARCHAR(60) NOT NULL,

    title VARCHAR(200) NOT NULL,

    description TEXT,

    actor_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    entity_type VARCHAR(80),

    entity_id BIGINT,

    occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    metadata JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT procurement_events_type_check
        CHECK (
            event_type IN (
                'REQUIREMENT_CREATED',
                'REQUIREMENT_UPDATED',
                'REQUIREMENT_SUBMITTED',
                'EVALUATION_STARTED',
                'SUPPLIER_SELECTED',
                'PURCHASE_ORDER_CREATED',
                'COMMITMENT_SUBMITTED',
                'COMMITMENT_ACCEPTED',
                'COMMITMENT_REJECTED',
                'DELIVERY_RECORDED',
                'INSPECTION_COMPLETED',
                'GOODS_ACCEPTED',
                'GOODS_REJECTED',
                'PROCUREMENT_COMPLETED',
                'PROCUREMENT_CANCELLED',
                'PROCUREMENT_STATUS_CHANGED',
                'EVIDENCE_ATTACHED'
            )
        )
);


CREATE INDEX idx_procurement_events_procurement_time
ON procurement_events(
    procurement_id,
    occurred_at,
    id
);


CREATE INDEX idx_procurement_events_actor
ON procurement_events(actor_id);


CREATE INDEX idx_procurement_events_entity
ON procurement_events(
    entity_type,
    entity_id
);


-- ============================================================
-- 24. AUDIT EVENTS
-- ============================================================

CREATE TABLE audit_events (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE RESTRICT,

    actor_id BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    action VARCHAR(100) NOT NULL,

    entity_type VARCHAR(80) NOT NULL,

    entity_id BIGINT,

    previous_state JSONB,

    new_state JSONB,

    metadata JSONB,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX idx_audit_events_procurement_created
ON audit_events(
    procurement_id,
    created_at,
    id
);


CREATE INDEX idx_audit_events_actor
ON audit_events(actor_id);


CREATE INDEX idx_audit_events_entity
ON audit_events(
    entity_type,
    entity_id
);


-- ============================================================
-- 25. EVIDENCE DOCUMENTS
-- ============================================================

CREATE TABLE evidence_documents (

    id BIGSERIAL PRIMARY KEY,

    procurement_id BIGINT NOT NULL
        REFERENCES procurements(id)
        ON DELETE RESTRICT,

    event_id BIGINT
        REFERENCES procurement_events(id)
        ON DELETE RESTRICT,

    document_type VARCHAR(50) NOT NULL,

    document_name VARCHAR(255) NOT NULL,

    original_filename VARCHAR(255) NOT NULL,

    mime_type VARCHAR(100) NOT NULL,

    file_size BIGINT NOT NULL,

    storage_reference TEXT NOT NULL UNIQUE,

    visibility VARCHAR(30) NOT NULL DEFAULT 'INTERNAL',

    uploaded_by BIGINT NOT NULL
        REFERENCES users(id)
        ON DELETE RESTRICT,

    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    deleted_at TIMESTAMP,

    deleted_by BIGINT
        REFERENCES users(id)
        ON DELETE RESTRICT,

    deletion_reason TEXT,

    CONSTRAINT evidence_document_type_check
        CHECK (
            document_type IN (
                'RFQ',
                'QUOTATION',
                'SUPPLIER_RESPONSE',
                'EVALUATION',
                'PURCHASE_ORDER',
                'COMMITMENT',
                'DELIVERY_NOTE',
                'GRN',
                'INSPECTION_RECORD',
                'INVOICE',
                'APPROVAL'
            )
        ),

    CONSTRAINT evidence_visibility_check
        CHECK (
            visibility IN (
                'INTERNAL',
                'SUPPLIER_VISIBLE'
            )
        ),

    CONSTRAINT evidence_file_size_check
        CHECK (file_size > 0)
);


CREATE INDEX idx_evidence_documents_procurement
ON evidence_documents(procurement_id);


CREATE INDEX idx_evidence_documents_event
ON evidence_documents(event_id);


CREATE INDEX idx_evidence_documents_uploaded_by
ON evidence_documents(uploaded_by);


CREATE INDEX idx_evidence_documents_active
ON evidence_documents(procurement_id)
WHERE deleted_at IS NULL;


-- ============================================================
-- 26. SUPPLIER PERFORMANCE
-- ============================================================

CREATE TABLE supplier_performance_metrics (

    id BIGSERIAL PRIMARY KEY,

    supplier_id BIGINT NOT NULL
        REFERENCES suppliers(id)
        ON DELETE RESTRICT,

    observation_count INTEGER NOT NULL DEFAULT 0,

    completed_procurement_count INTEGER NOT NULL DEFAULT 0,

    completed_commitment_count INTEGER NOT NULL DEFAULT 0,

    promised_quantity NUMERIC(16,2) NOT NULL DEFAULT 0,

    accepted_quantity NUMERIC(16,2) NOT NULL DEFAULT 0,

    fulfilment_rate NUMERIC(6,2),

    quantity_variance_rate NUMERIC(6,2),

    on_time_delivery_rate NUMERIC(6,2),

    quality_acceptance_rate NUMERIC(6,2),

    timing_observation_count INTEGER NOT NULL DEFAULT 0,

    quality_observation_count INTEGER NOT NULL DEFAULT 0,

    status VARCHAR(30) NOT NULL DEFAULT 'NO_HISTORY',

    calculation_version INTEGER NOT NULL DEFAULT 1,

    calculated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT supplier_performance_unique
        UNIQUE (supplier_id),

    CONSTRAINT supplier_performance_status_check
        CHECK (
            status IN (
                'NO_HISTORY',
                'AVAILABLE'
            )
        ),

    CONSTRAINT supplier_performance_counts_check
        CHECK (
            observation_count >= 0
            AND completed_procurement_count >= 0
            AND completed_commitment_count >= 0
            AND timing_observation_count >= 0
            AND quality_observation_count >= 0
        ),

    CONSTRAINT supplier_performance_quantities_check
        CHECK (
            promised_quantity >= 0
            AND accepted_quantity >= 0
        ),

    CONSTRAINT supplier_performance_rates_check
        CHECK (
            (
                fulfilment_rate IS NULL
                OR fulfilment_rate BETWEEN 0 AND 100
            )
            AND
            (
                quantity_variance_rate IS NULL
                OR quantity_variance_rate BETWEEN 0 AND 100
            )
            AND
            (
                on_time_delivery_rate IS NULL
                OR on_time_delivery_rate BETWEEN 0 AND 100
            )
            AND
            (
                quality_acceptance_rate IS NULL
                OR quality_acceptance_rate BETWEEN 0 AND 100
            )
        )
);


CREATE INDEX idx_supplier_performance_status
ON supplier_performance_metrics(status);


-- ============================================================
-- 27. RESPONSIBILITY SEED DATA
-- ============================================================

INSERT INTO responsibilities
(
    code,
    name,
    description,
    organization_type
)
VALUES
(
    'ORGANIZATION_ADMIN',
    'Organization Administrator',
    'Manages the organization account and its users.',
    'ANY'
),
(
    'PROCUREMENT_OFFICER',
    'Procurement Officer',
    'Creates and manages procurement activities.',
    'SCHOOL'
),
(
    'PROCUREMENT_REVIEWER',
    'Procurement Reviewer',
    'Reviews procurement and supplier evaluation information.',
    'SCHOOL'
),
(
    'RECEIVING_OFFICER',
    'Receiving Officer',
    'Records receiving and inspection information.',
    'SCHOOL'
),
(
    'SUPPLIER_USER',
    'Supplier User',
    'Operates supplier-side procurement activities.',
    'SUPPLIER'
),
(
    'SUPPLIER_ADMIN',
    'Supplier Administrator',
    'Manages supplier organization activities.',
    'SUPPLIER'
);


-- ============================================================
-- 28. IMMUTABLE PROCUREMENT EVENTS
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_procurement_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    RAISE EXCEPTION
        'Procurement timeline events are immutable.';

END;
$$;


CREATE TRIGGER trg_procurement_events_immutable
BEFORE UPDATE OR DELETE
ON procurement_events
FOR EACH ROW
EXECUTE FUNCTION prevent_procurement_event_mutation();


-- ============================================================
-- 29. IMMUTABLE AUDIT EVENTS
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_audit_event_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    RAISE EXCEPTION
        'Audit events are immutable.';

END;
$$;


CREATE TRIGGER trg_audit_events_immutable
BEFORE UPDATE OR DELETE
ON audit_events
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_event_mutation();


-- ============================================================
-- 30. CROSS-ENTITY ORGANIZATION INTEGRITY
-- ============================================================

CREATE OR REPLACE FUNCTION enforce_supplier_organization_type()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM organizations
        WHERE id = NEW.organization_id
          AND organization_type = 'SUPPLIER'
    ) THEN
        RAISE EXCEPTION 'Supplier must belong to a SUPPLIER organization.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_supplier_organization_type
BEFORE INSERT OR UPDATE OF organization_id ON suppliers
FOR EACH ROW
EXECUTE FUNCTION enforce_supplier_organization_type();

CREATE OR REPLACE FUNCTION enforce_procurement_organization_type()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM organizations
        WHERE id = NEW.organization_id
          AND organization_type = 'SCHOOL'
    ) THEN
        RAISE EXCEPTION 'Procurement must belong to a SCHOOL organization.';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_procurement_organization_type
BEFORE INSERT OR UPDATE OF organization_id ON procurements
FOR EACH ROW
EXECUTE FUNCTION enforce_procurement_organization_type();


-- ============================================================
-- 31. AUTOMATIC UPDATED_AT
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    NEW.updated_at = CURRENT_TIMESTAMP;

    RETURN NEW;

END;
$$;


CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE
ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_organizations_updated_at
BEFORE UPDATE
ON organizations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_memberships_updated_at
BEFORE UPDATE
ON organization_memberships
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_suppliers_updated_at
BEFORE UPDATE
ON suppliers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_supplier_capabilities_updated_at
BEFORE UPDATE
ON supplier_capabilities
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_supplier_products_updated_at
BEFORE UPDATE
ON supplier_products
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_supplier_contacts_updated_at
BEFORE UPDATE
ON supplier_contacts
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_procurements_updated_at
BEFORE UPDATE
ON procurements
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_procurement_items_updated_at
BEFORE UPDATE
ON procurement_items
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_supplier_evaluations_updated_at
BEFORE UPDATE
ON supplier_evaluations
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_purchase_orders_updated_at
BEFORE UPDATE
ON purchase_orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_supplier_commitments_updated_at
BEFORE UPDATE
ON supplier_commitments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_deliveries_updated_at
BEFORE UPDATE
ON deliveries
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


CREATE TRIGGER trg_delivery_lines_updated_at
BEFORE UPDATE
ON delivery_lines
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();


COMMIT;