# AgroFlow Feature 22 — Phase 23 Runtime Validation Runbook

## Purpose

The cumulative Feature 22 application evidence is already recorded. The remaining evidence is **environment-dependent**:

1. real Neon PostgreSQL;
2. real React/Jest/browser execution;
3. deployed Render API;
4. deployed Vercel frontend;
5. production-like/staging load.

This runbook tells the engineer how to collect those pieces without giving secrets to ChatGPT.

## Security rule

Never paste the real `.env`, `DATABASE_URL`, JWT secret, API keys, or deployment secrets into ChatGPT or GitHub.

Keep secrets in:
- local `.env`;
- Render environment variables;
- Vercel environment variables.

If a secret is accidentally exposed, rotate it.

---

# A. Prepare the backend environment

From the repository root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cd ..
```

A virtual environment is **not FastAPI**. It is an isolated Python environment containing the project's Python packages.

Verify the cumulative suite:

```powershell
python -m pytest -q backend/tests
```

Expected current baseline:

```text
173 passed
```

If this fails after an environment change, stop and diagnose before deployment.

Optional coverage:

```powershell
python -m pytest --cov=backend/app --cov-report=term-missing -q backend/tests
```

Coverage is diagnostic; it does not replace business-rule or workflow evidence.

---

# B. Prepare the frontend environment

```powershell
cd agroflow-mvp-frontend
npm install
npm test -- --watchAll=false
npm run build
cd ..
```

`npm install` is normally needed after cloning or when dependencies change. It is not a required step after every source-code edit if `node_modules` is already valid.

A successful build proves the frontend compiles. It does not prove the deployed API, database, authorization, or browser workflow.

---

# C. Real Neon PostgreSQL validation

Use a **dedicated development/staging Neon database**, not production.

Keep the real `DATABASE_URL` only in your local `.env`.

From `backend` with the virtual environment active:

```powershell
python -m tools.feature22_neon_smoke
```

The smoke test checks:

- actual PostgreSQL/Neon connectivity;
- expected AgroFlow tables;
- the active commitment unique index;
- a real PostgreSQL lock/transaction primitive.

It is intentionally conservative and does not print the connection string or password.

### What this proves

It proves that the local application can reach the real PostgreSQL/Neon instance and that expected database structures/primitives are present.

### What it does not yet prove

It does not by itself prove the complete AgroFlow commitment race, delivery race, rollback, or authorization workflows against live Neon.

Those should be tested next against a **dedicated staging dataset**.

---

PHASE 23
│
├── 23.1 Deployment readiness
│
├── 23.2 Configure staging Neon
│
├── 23.3 Configure Render
│
├── 23.4 Configure Vercel
│
├── 23.5 Verify deployed system
│
├── 23.6 Create controlled test identities/data
│
├── 23.7 Execute core procurement experiment
│
├── 23.8 Execute security experiments
│
├── 23.9 Execute evidence/pagination experiments
│
├── 23.10 Record evidence
│
├── 23.11 Optional controlled load test
│
└── 23.12 Phase 23 conclusion