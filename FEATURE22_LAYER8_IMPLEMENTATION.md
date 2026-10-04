# Feature 22 — Layer 8: Stress Test Suite

## Purpose
Layer 8 increases controlled workload and concurrency to ask two separate questions:

1. Does AgroFlow remain correct as activity/record volume increases?
2. Can concurrent/conflicting operations produce invalid business state?

Performance degradation and correctness failure are recorded separately. A fast test that produces `committed > available` is a failure.

## Added
- `backend/tests/test_feature22_stress_suite.py`

The suite covers:
- 10,000 deterministic discrepancy calculations
- 1,000 supplier-capacity decisions against limited supply
- 5,000 procurement-like state records
- bounded procurement list pagination (`limit <= 100`)
- 2,000 repeated discrepancy operations
- 20 concurrent commitment attempts against 500 kg
- concurrent different-supplier commitments against limited supply
- 1,000 concurrent discrepancy observations
- controlled latency regression checks
- production commitment row-lock contract (`FOR UPDATE`)
- database unique active-commitment constraint contract
- explicit correctness-vs-latency distinction

## Fix during implementation
The first stress run found an incorrect expected value in the new test itself: the deterministic capacity loop commits 495 kg, not 499 kg. The test expectation was corrected. No production code change was necessary from the stress run.

## Verification
Command:

`PYTHONPATH=backend pytest -q backend/tests`

Result:

`173 passed in 0.65s`

## Important runtime boundary
These are controlled stress/regression tests, not a substitute for a production load test against the real PostgreSQL/Neon environment. In particular, CPU, memory, network, database connection-pool behavior, PostgreSQL lock contention, transaction isolation, and real HTTP throughput require a deployed/staging environment with observability.

The suite therefore verifies the application/schema concurrency contracts (`FOR UPDATE` and the active-commitment unique constraint) and exercises deterministic concurrent models without claiming those models are equivalent to real PostgreSQL load.
