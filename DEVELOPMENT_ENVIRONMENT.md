# AgroFlow Feature 22 — Reproducible Development Environment

## Backend

Recommended sequence from the repository root:

```text
cd backend
python -m venv .venv
```

Activate it on Windows PowerShell:

```text
.venv\Scripts\Activate.ps1
```

Install runtime + test dependencies:

```text
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Run the normal backend evidence suite:

```text
cd ..
python -m pytest -q backend/tests
```

A virtual environment is not FastAPI itself. It is an isolated Python environment in which FastAPI, Uvicorn, psycopg2-binary, PyJWT, Pydantic, pytest, and the other project dependencies are installed.

## Frontend

From the frontend directory:

```text
cd agroflow-mvp-frontend
npm install
npm test -- --watchAll=false
npm run build
```

`npm install` installs the versions recorded by `package.json`/`package-lock.json`. It is normally done after cloning the repository or when dependencies change; it is not necessary to repeat it for every code change if `node_modules` is already valid.

## Environment variables

Copy `.env.example` to a local `.env` and supply real values locally. **Never commit `.env` or paste database/JWT secrets into source control or a chat transcript.**

The important backend values are:

- `DATABASE_URL` — PostgreSQL/Neon connection string.
- `JWT_SECRET_KEY` — a private random secret of at least 32 characters.
- `CORS_ORIGINS` — trusted frontend origin(s).
- evidence/security settings documented in `.env.example`.

The supplied archive intentionally contains no production database credentials.

## Coverage

If `pytest-cov` is installed through `requirements-dev.txt`, use:

```text
python -m pytest --cov=backend/app --cov-report=term-missing -q backend/tests
```

Treat coverage as a diagnostic. High line coverage does not prove business correctness; inspect missing branches around invariants, authorization, transactions, failure paths, and state transitions.
