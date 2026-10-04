# Feature 22 — PostgreSQL/Neon Validation Plan

## Why this exists

The application-level Feature 22 suite cannot honestly prove behavior that only real PostgreSQL can provide. Neon is PostgreSQL, so the remaining database evidence must be collected against a controlled Neon database.

## Secrets: do not send them to ChatGPT

You do **not** need to give ChatGPT your `DATABASE_URL`, password, JWT secret, or `.env` contents.

Keep the real `.env` on your machine. The validation script reads `DATABASE_URL` locally and prints only sanitized database/server information. If a credential is ever exposed accidentally, rotate it immediately.

## Stage 1 — safe connection/schema smoke test

From `backend`:

```text
python -m tools.feature22_neon_smoke
```

This checks:

- real connection to PostgreSQL/Neon;
- expected core tables exist;
- the active-commitment unique index exists;
- PostgreSQL transaction/lock behavior is actually available.

It does not insert/update/delete AgroFlow production rows.

## Stage 2 — real schema migration verification

The Neon database should be a dedicated development/staging database, not the production database. Apply the repository migration using your normal migration procedure and then run the smoke test.

## Stage 3 — application integration against Neon

Set the local backend `.env` to the dedicated staging Neon connection and run the normal FastAPI application. Then execute controlled API workflows using test organizations/users and a deterministic dataset.

The important evidence is:

1. two concurrent commitment requests cannot over-commit the same capacity;
2. duplicate active commitments are rejected by the real database constraint;
3. invalid foreign keys/check constraints are rejected;
4. transaction rollback leaves no partial procurement/delivery write;
5. authorization is enforced against real persisted organizations/memberships/resources;
6. pagination returns bounded pages against real rows.

## Stage 4 — real deployed backend

Repeat the same deterministic acceptance/security/concurrency cases through the deployed Render API, not just direct Python service calls. Record request, expected result, actual result, timestamp, and evidence artifact.

## Stage 5 — production-like load

Only after correctness is established should a controlled staging load test be run. Measure:

- request latency (median/p95/p99);
- HTTP error rate;
- database connection behavior;
- lock waits/conflicts;
- CPU/RAM;
- slow queries;
- throughput;
- correctness under concurrency.

Do not use the production database for exploratory load testing.
