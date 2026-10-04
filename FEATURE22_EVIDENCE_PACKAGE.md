# AgroFlow Feature 22 — Phase 23 Final Evidence Package

## 1. Purpose

This package consolidates the evidence produced through Feature 22 Layers 1–8 into one traceable engineering record.

The package answers five questions:

1. **What did we test?** — domain rules, integrations, workflows, authorization, UI contracts, acceptance, adversarial behavior, and controlled stress behavior.
2. **Why did we test it?** — to turn requirements and business rules into observable evidence rather than relying on code inspection or happy-path demonstrations.
3. **What did we expect?** — the expected result is derived from the requirement/domain invariant/state/authorization rule under test.
4. **What actually happened?** — the executable backend suite currently reports **173 passed, 0 failed** in the supplied Layer 8 codebase. Frontend Jest/browser execution and live PostgreSQL/Neon execution were not performed in this isolated environment.
5. **What proves it / what remains uncertain?** — see the evidence matrix and limitations below.

## 2. Evidence chain

`Requirement → Domain Rule → Scenario → Input → Expected → Implementation → Test → Actual → Evidence → Conclusion → Limitation`

This is the central Feature 22 engineering habit. A test result is evidence about a defined question; it is not a blanket proof that the whole product is correct.

## 3. Layer summary

| Layer | Engineering question | Evidence | Current result | Boundary |
|---|---|---|---|---|
| 1 | Are core domain rules and calculations correct? | unit/domain tests | Included in 173-pass suite | In-process execution |
| 2 | Do route/service/schema/transaction paths work together? | integration suite + implementation record | Included in 173-pass suite | Deterministic DB adapter, not PostgreSQL |
| 3 | Do workflows and state transitions behave correctly? | workflow suite | Included in 173-pass suite | Application-level workflow execution |
| 4 | Are responsibilities and organization boundaries enforced? | authorization suite | Included in 173-pass suite | Live production auth/database still needs environment validation |
| 5 | Does the frontend represent and send the expected state? | React tests/source inspection | Source tests present; Jest not executed here | No installed frontend dependencies/browser |
| 6 | Can the system tell a complete procurement story? | acceptance suite | Included in 173-pass suite | Deterministic DB adapter; no live browser/DB |
| 7 | What happens when we deliberately attack the system? | adversarial suite | Included in 173-pass suite | Live DB/security perimeter still needs environment test |
| 8 | Does correctness survive higher controlled workload/concurrency? | stress suite | Included in 173-pass suite | Not production load testing; no live Neon |

## 4. Canonical evidence case

A central Feature 22 discrepancy case is:

- Committed/promised quantity: **500 kg**
- Actual received quantity: **430 kg**
- Shortfall: **70 kg**
- Variance: **14%**
- Interpretation: actual receipt is below the committed quantity and therefore requires an evidence-backed discrepancy explanation.

The package treats this as a domain calculation and evidence case, not merely a UI number.

## 5. Procurement evidence chain

The target business story is:

`Requirement → Supplier evaluation → Human selection → Purchase order → Commitment → Delivery → Inspection → Acceptance/rejection → Corrective action/new delivery → Outcome`

The evidence model distinguishes:

- planned quantity vs promised quantity vs actual quantity;
- supplier assertion vs school verification;
- commitment vs delivery vs inspection;
- evidence vs assertion;
- absence of historical observations vs demonstrated poor performance.

## 6. Security and authorization evidence

Feature 22 tests role permissions, active membership, organization state, organization isolation, resource ownership, supplier/school boundaries, evidence visibility, and direct-resource access attempts.

Layer 7 also hardened the central authorization boundary so organization-scoped authorization requires the organization to be **ACTIVE and VERIFIED**, in addition to the relevant membership/permission conditions.

The evidence suite therefore checks both ordinary authorization and adversarial attempts to bypass it.

## 7. Concurrency and database evidence

The application contains two important protections for active supplier commitments:

1. a row lock (`SELECT ... FOR UPDATE`) around the relevant purchase-order line during commitment/capacity evaluation;
2. PostgreSQL partial unique index `uq_active_commitment_per_po_line_supplier` for active (`SUBMITTED`/`ACCEPTED`) commitments.

Layer 8 exercised deterministic concurrency models and verified these production/schema contracts. It did **not** claim that an in-process thread model is equivalent to real PostgreSQL lock contention.

## 8. Stress evidence

Layer 8 exercised:

- 10,000 discrepancy calculations;
- 1,000 supplier-capacity decisions;
- 5,000 procurement-like state records;
- bounded procurement pagination (`limit <= 100`);
- 2,000 repeated discrepancy operations;
- 20 competing commitment attempts against 500 kg;
- multiple-supplier commitment competition against 500 kg;
- 1,000 concurrent discrepancy observations;
- controlled timing regression checks.

The critical distinction is:

> **Performance degradation is an observation. Invalid business state is a correctness failure.**

## 9. Sample dataset

`evidence/feature22_sample_dataset.json` is a deterministic, human-readable dataset specification covering successful procurement, partial delivery, rejection/correction, supplier-history cases, authorization cases, over-commitment, boundary quantities, duplicate/conflict cases, and evidence/timeline facts.

It is deliberately a specification/fixture rather than an uncontrolled copy of production data.

## 10. API evidence

The package records the API-level contracts relevant to the tested workflows, including pagination bounds, procurement state transitions, commitment rules, delivery/inspection behavior, evidence upload, and authorization boundaries.

For frontend/API reasoning, the expected trace remains:

`UI → component → state → API client → HTTP → backend route → authorization → business logic → DB → response → frontend state → UI`

## 11. Timeline/evidence model

For an important procurement event, evidence should answer:

- **What happened?**
- **Who recorded/caused it?**
- **When did it happen?**
- **What evidence supports it?**
- **What decision or state change followed?**

Feature 21's audit/timeline mechanisms and Feature 22 acceptance/adversarial tests are treated as evidence of this design rather than as proof that every future production event will automatically be complete.

## 12. Coverage information

Coverage is useful only when interpreted against the test question. The current package therefore does not invent a percentage from an unavailable coverage run.

When the normal backend development environment is available, run the documented coverage command in `DEVELOPMENT_ENVIRONMENT.md`. Review uncovered branches against requirements, security boundaries, and failure modes rather than treating a high percentage as proof of correctness.

## 13. Known limitations / remaining uncertainty

### A. Real PostgreSQL/Neon behavior

This is the most important remaining runtime uncertainty.

The current evidence proves application-level rules and checks PostgreSQL-specific source/schema contracts, but it does not prove real Neon behavior under:

- actual PostgreSQL transactions;
- row-lock contention;
- transaction isolation;
- unique-index conflicts under simultaneous requests;
- real connection pooling;
- network latency/failures;
- deployed database permissions;
- real database constraints against the actual schema;
- real HTTP concurrency against the deployed backend.

A safe, credential-preserving Neon smoke/concurrency script has been added at `backend/tools/feature22_neon_smoke.py`. It reads `DATABASE_URL` from the user's local environment and never prints the password. It performs read-only schema/connection checks plus a temporary-table transaction/locking experiment. It is intentionally separate from the default test suite so no live database is touched accidentally.

A real staging acceptance run should additionally exercise the deployed FastAPI service against the Neon database with a controlled test dataset.

### B. Frontend runtime

The archive contains the React source and Feature 22 UI tests, but this isolated environment did not have frontend `node_modules` and could not install packages from the network. Therefore no claim is made that Jest, a real browser, or `npm run build` passed here.

### C. Production load

Layer 8 is controlled stress/regression testing, not a production load test. It does not provide real CPU, RAM, network, PostgreSQL throughput, connection-pool, or Render/Vercel latency measurements.

### D. Real evidence files/screenshots

The package defines what evidence should be captured, but screenshots from a real deployed browser session are not fabricated. They should be captured during the staging/production-like acceptance run where they materially clarify a workflow.

## 14. Phase 23 conclusion

**Phase 23 artifact work is complete in this codebase:** the layers have been consolidated into a coherent evidence package with a matrix, deterministic dataset, environment instructions, and a safe path for validating the remaining PostgreSQL/Neon uncertainty.

The correct engineering conclusion is not “everything is proven.” It is:

> The application-level Feature 22 suite provides broad executable evidence, while live PostgreSQL/Neon behavior, real browser execution, and deployed load behavior remain environment-dependent evidence that must be collected in the next validation environment.

That is a stronger engineering conclusion than hiding the remaining uncertainty.

## 13. Runtime validation handoff

The environment-dependent follow-up is documented in `PHASE23_RUNTIME_VALIDATION_RUNBOOK.md`. Its purpose is to collect real Neon, frontend/browser, Render, Vercel, and staging-load evidence without exposing secrets. `PHASE23_RUNTIME_EVIDENCE_STATUS.md` records what is verified versus what is intentionally not claimed.
