# AgroFlow — Build/Test/Deploy Workflow Review

## Your proposed sequence

> npm run build → npm install → git add/commit/push → GitHub → Vercel frontend + Render backend

That is close, but the important distinction is **local verification vs dependency installation vs deployment trigger**.

## Recommended workflow

### 1. Backend changes

```text
Activate backend/.venv
→ python -m pytest -q backend/tests
→ optionally run coverage
→ run Neon smoke test against dedicated staging DB
→ start FastAPI locally if API/browser testing is needed
```

You do not normally run `npm` for backend-only changes.

### 2. Frontend changes

```text
cd agroflow-mvp-frontend
→ npm install   (only when dependencies are missing/changed)
→ npm test -- --watchAll=false
→ npm run build
```

A successful build proves the frontend can compile. It does not prove the live API, database, authorization, or browser workflow.

### 3. Git

After tests/build are satisfactory:

```text
git status
git add .
git commit -m "Feature 22 evidence package"
git push
```

Do not commit `.env`, database passwords, JWT secrets, `node_modules`, Python virtual environments, build output that the deployment platform generates, or other secret/local artifacts.

### 4. Vercel

If the Vercel project is connected to the GitHub repository and configured for automatic deployments, pushing the relevant branch normally triggers a new frontend deployment automatically. You generally do **not** need a separate manual Vercel deployment.

Verify the deployment and inspect build logs/environment variables.

### 5. Render

If the Render service is connected to the GitHub repository with automatic deploys enabled, pushing the relevant branch normally triggers the backend deployment automatically. You generally do **not** need a separate manual Render deployment.

Verify the deployment, health/start command, environment variables, migration state, and logs.

## Important correction

Do not think of deployment as:

`git push = system proven`

Think:

`code → tests → build → deploy → deployed smoke test → deployed acceptance/security test → evidence`

The deployment platform can prove that a build was deployed; only runtime evidence can show that the deployed system behaves correctly.

## Environment variables are deployment configuration

Local `.env`, Vercel environment variables, and Render environment variables are separate configuration locations. A local `.env` does not automatically become a GitHub/Vercel/Render secret.

Keep secrets out of GitHub and out of ChatGPT.
