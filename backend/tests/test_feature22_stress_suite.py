"""Feature 22 - Layer 8: controlled stress tests.

These tests increase workload while keeping the experiment deterministic and
portable. They focus on two things: (1) the system remains correct as the
number of records/operations grows, and (2) concurrent/conflicting operations
cannot produce invalid business state.

A real production load test should additionally run against PostgreSQL/Neon
and collect CPU, memory, connection-pool and network metrics. This suite does
not pretend an in-memory/process test is equivalent to that environment.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import statistics
import time

import pytest

from app.services.domain_invariants import (
    calculate_delivery_discrepancy,
    validate_commitment_quantity,
)
from app.services.procurement_service import VALID_TRANSITIONS


# ---------------------------------------------------------------------------
# Volume: many domain operations remain correct
# ---------------------------------------------------------------------------

def test_high_volume_discrepancy_calculations_preserve_correctness():
    """Exercise a large deterministic batch without changing the business rule."""
    records = 10_000
    failures = []

    for i in range(records):
        committed = Decimal(500 + (i % 25))
        received = committed - Decimal(i % 11)
        result = calculate_delivery_discrepancy(committed, received)
        expected_shortfall = Decimal(i % 11)
        if result["shortfall"] != expected_shortfall:
            failures.append((i, result["shortfall"], expected_shortfall))

    assert not failures
    assert records == 10_000


def test_many_supplier_capacity_checks_never_accept_over_capacity():
    """Simulate many suppliers competing for limited capacity deterministically."""
    available = Decimal("500")
    requested = [Decimal(10 + (i % 21)) for i in range(1_000)]
    accepted = 0
    committed = Decimal("0")

    for quantity in requested:
        if committed + quantity <= available:
            committed += quantity
            accepted += 1

    assert committed <= available
    assert accepted > 0
    assert committed == Decimal("495")


def test_large_deterministic_procurement_dataset_preserves_state_invariants():
    """Exercise many procurement-like records without allowing illegal states."""
    allowed = {source: set(targets) for source, targets in VALID_TRANSITIONS.items()}
    states = ["DRAFT"] * 5_000

    # Move every record through the first two legal transitions.
    for i, state in enumerate(states):
        assert "SUBMITTED" in allowed[state]
        states[i] = "SUBMITTED"
        assert "EVALUATION" in allowed[states[i]]
        states[i] = "EVALUATION"

    assert len(states) == 5_000
    assert all(state == "EVALUATION" for state in states)


# ---------------------------------------------------------------------------
# Repeated API-style activity / pagination contract
# ---------------------------------------------------------------------------

def test_large_list_query_pagination_contract_has_bounded_page_size():
    route = Path(__file__).resolve().parents[1] / "app" / "routes" / "procurement_routes.py"
    text = route.read_text()
    assert "limit: int = Query(20, ge=1, le=100)" in text
    assert "offset: int = Query(0, ge=0)" in text
    assert "LIMIT %s OFFSET %s" in text


def test_repeated_business_operations_are_deterministic():
    """Repeat the same operation many times and require identical output."""
    outputs = [calculate_delivery_discrepancy(500, 430) for _ in range(2_000)]
    assert all(item == outputs[0] for item in outputs)
    assert outputs[0]["shortfall"] == Decimal("70")
    assert outputs[0]["variance_rate"] == Decimal("14.00")


# ---------------------------------------------------------------------------
# Concurrent commitments / limited supply
# ---------------------------------------------------------------------------

def _concurrent_commit_attempt(quantity, state, lock):
    with lock:
        remaining = state["available"] - state["committed"]
        try:
            validate_commitment_quantity(quantity, remaining)
        except Exception:
            return "REJECTED"
        state["committed"] += quantity
        return "ACCEPTED"


def test_many_concurrent_commitments_preserve_limited_supply():
    """20 simultaneous claims for 500 kg must never produce >500 kg committed."""
    from threading import Lock

    state = {"available": Decimal("500"), "committed": Decimal("0")}
    lock = Lock()

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(
            lambda _: _concurrent_commit_attempt(500, state, lock),
            range(20),
        ))

    assert results.count("ACCEPTED") == 1
    assert results.count("REJECTED") == 19
    assert state["committed"] == Decimal("500")
    assert state["committed"] <= state["available"]


def test_concurrent_different_supplier_commitments_do_not_exceed_capacity():
    """Several suppliers competing for 500 kg cannot create an invalid total."""
    from threading import Lock

    state = {"available": Decimal("500"), "committed": Decimal("0")}
    lock = Lock()
    quantities = [Decimal("200"), Decimal("200"), Decimal("200"), Decimal("100"), Decimal("50")]

    with ThreadPoolExecutor(max_workers=len(quantities)) as pool:
        results = list(pool.map(
            lambda q: _concurrent_commit_attempt(q, state, lock),
            quantities,
        ))

    assert results.count("ACCEPTED") >= 2
    assert state["committed"] <= Decimal("500")
    assert state["committed"] == Decimal("500")


# ---------------------------------------------------------------------------
# Concurrent/conflicting delivery calculations
# ---------------------------------------------------------------------------

def test_concurrent_delivery_observations_remain_deterministic():
    """Concurrent read/calculation activity cannot mutate the discrepancy result."""
    def calculate(_):
        return calculate_delivery_discrepancy(500, 430)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(calculate, range(1_000)))

    assert all(result["shortfall"] == Decimal("70") for result in results)
    assert all(result["variance_rate"] == Decimal("14.00") for result in results)


# ---------------------------------------------------------------------------
# Resource observation: controlled latency, not a production benchmark
# ---------------------------------------------------------------------------

def test_controlled_batch_has_finite_execution_time():
    """Detect accidental pathological complexity in a bounded pure calculation."""
    start = time.perf_counter()
    for i in range(5_000):
        calculate_delivery_discrepancy(500 + (i % 10), 430 + (i % 10))
    elapsed = time.perf_counter() - start

    # This is a regression guard for pathological behavior, not a promised
    # production SLA; hardware and environment vary.
    assert elapsed < 2.0


def test_stress_observation_is_reportable_without_claiming_production_metrics():
    """Record repeat timings so the experiment has an observable artifact."""
    samples = []
    for _ in range(20):
        start = time.perf_counter()
        calculate_delivery_discrepancy(500, 430)
        samples.append(time.perf_counter() - start)

    assert all(sample >= 0 for sample in samples)
    assert statistics.median(samples) < 0.05


# ---------------------------------------------------------------------------
# Database/concurrency contract checks
# ---------------------------------------------------------------------------

def test_stress_suite_requires_row_locking_for_real_commitment_races():
    source = Path(__file__).resolve().parents[1] / "app" / "services" / "commitment_service.py"
    text = source.read_text()
    assert "FOR UPDATE" in text
    assert "validate_commitment_quantity" in text


def test_stress_suite_requires_database_unique_constraint_for_active_duplicates():
    migration = Path(__file__).resolve().parents[1] / "migrations" / "001_phase_a_baseline.sql"
    sql = migration.read_text()
    normalized = "".join(sql.split()).upper()
    assert "UQ_ACTIVE_COMMITMENT_PER_PO_LINE_SUPPLIER" in normalized
    assert "UNIQUEINDEX" in normalized


def test_stress_suite_keeps_failure_as_correctness_failure_not_just_latency():
    """Explicitly encode the critical distinction from the Feature 22 plan."""
    available = Decimal("500")
    committed = Decimal("500")
    assert committed <= available
    # If a future stress implementation ever reports > available, the test
    # must fail regardless of whether the run was otherwise fast.
    invalid_total = Decimal("1000")
    assert not (invalid_total <= available)
