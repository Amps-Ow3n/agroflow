# Phase A Bootstrap Replacement

## Purpose

The current AgroFlow repository does not contain the previously referenced `init__db.py` or `init__db.py` database bootstrap.

The current database foundation is represented by a collection of historical SQL migrations under:

`backend/migrations/`

These migrations document the evolution of AgroFlow through Features 1–15.

Feature 20 replaces this historical migration accumulation with a clean authoritative Phase A database baseline.

## Current Problem

The existing migration history contains:

* incremental ALTER TABLE operations;
* temporary compatibility fields;
* legacy identity relationships;
* obsolete tables;
* duplicate table definitions;
* historical backfills;
* relationships that were corrected in later features;
* schema assumptions from earlier AgroFlow versions.

Examples include:

* `purchase_orders.supplier_id` referencing `users.id`;
* `supplier_commitments.supplier_entity_id` existing alongside older supplier identity;
* `deliveries.supplier_id` referencing `organizations.id`;
* duplicate document structures;
* legacy procurement status/history structures;
* legacy agricultural structures.

## Target

The authoritative Phase A database shall be represented by a clean baseline schema:

`backend/schema/phase_a_baseline.sql`

The baseline shall be derived from the final Phase A domain model rather than mechanically concatenating historical migrations.

## Authoritative identity rules

* `users.id` = human identity.
* `organizations.id` = organization identity.
* `suppliers.id` = supplier business identity.
* `actor_id` and actor-related fields reference `users.id`.
* `organization_id` references `organizations.id`.
* `supplier_id` references `suppliers.id`.
* `school_id` is not an authoritative Phase A identity.
* `supplier_entity_id` is not an authoritative Phase A identity.

## Migration strategy

Because the development database has been emptied and contains no production users or production procurement history, the Phase A schema may be rebuilt cleanly.

The historical migrations shall be treated as design history and reference material.

They shall not automatically become the production schema-building mechanism.

## Important rule

No historical migration shall be deleted or rewritten until its useful domain decisions have been incorporated into the final Phase A baseline.

After the baseline has been verified, obsolete migrations may be retired from the active migration path.

## Current status

Phase 20.4 analysis: IN PROGRESS.

Phase 20.4 implementation begins after the Phase 20.5–20.8 schema audits establish the final database contract.
