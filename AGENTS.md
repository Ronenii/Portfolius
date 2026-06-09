# AGENTS.md

Guidance for AI coding agents working in this repo. For the full product story, deployment, and provider setup, see [README.md](README.md). This file is the short version: how to build, test, and not break things.

## What this is

Portfolius is a long-term investor dashboard: enter holdings once, see allocation sliced by market/sector/asset class/currency, and ask an AI assistant grounded in your portfolio what to rebalance. Hobby project, runs entirely on free tiers.

## Layout

```
backend/    FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic
  app/
    main.py          app entrypoint
    api/v1/          HTTP routes (holdings, instruments, portfolio, profile, assistant, jobs, health)
    domain/          business logic (snapshots, aggregations, simulation)
    data/            SQLAlchemy models + repositories
    schemas/         Pydantic request/response models
    integrations/    yfinance, FMP, Groq/LLM clients
    jobs/            cron entrypoints (price refresh)
    core/            config, auth, shared plumbing
  alembic/           migrations
  tests/             pytest
frontend/   React + Vite + TypeScript SPA
  src/
    pages/           route-level views
    features/        feature modules
    components/      shared UI
    lib/             api client, charts, helpers
    test/            vitest
.github/workflows/   ci.yml (lint+test), refresh-prices.yml (scheduled price refresh)
.codex/skills/       Portfolius design system (brand, colors, type, UI kit)
```

## Commands

Run these from the package directory (`backend/` or `frontend/`), not the repo root.

**Backend** (activate the venv first: `source .venv/bin/activate`)

```bash
uvicorn app.main:app --reload          # dev server → http://localhost:8000  (/docs for Swagger)
pytest                                  # run tests
ruff check . && ruff format .           # lint + format
alembic revision --autogenerate -m "…"  # create a migration
alembic upgrade head                    # apply migrations
python -m app.jobs.refresh_prices       # manual price refresh
```

**Frontend**

```bash
npm run dev                             # vite dev server → http://localhost:5173
npm run build                           # tsc -b && vite build
npm run lint                            # eslint
npm run test                            # vitest run
```

Before opening a PR, make sure the backend passes `ruff check .` + `pytest` and the frontend passes `npm run lint` + `npm run build` — these gate CI.

## Conventions

- **Backend lint/format is ruff** (line length 88, rules `E,F,I,UP,B`). There is no mypy dependency despite older notes — don't add type-check steps that aren't wired up. Match existing module style.
- **Keep routes thin.** HTTP handlers in `api/v1/` should delegate to `domain/` (logic) and `data/` (persistence). Pydantic models live in `schemas/`.
- **Schema changes go through Alembic.** Never hand-edit the DB; add a migration. Migrations apply on backend boot in production (`alembic upgrade head`).
- **Frontend API types** live in `src/lib` and mirror the backend OpenAPI contract — keep them in sync when you touch backend response shapes.
- **Design system:** for any UI/visual work, use the `.codex/skills/portfolius-design` skill (Paper/Terminal modes, Teal accent, Instrument Serif / Geist / JetBrains Mono). Don't hand-pick hex values.

## Gotchas

- **Auth:** Supabase access tokens are verified via the project JWKS endpoint (`/auth/v1/.well-known/jwks.json`), not the legacy JWT secret. Frontend and backend must point at the same Supabase project for tokens to validate.
- **LLM is optional.** Without `LLM_API_KEY`, assistant endpoints return `503 "Assistant is not configured"`. The simulation endpoint (`POST /api/v1/portfolio/simulate`) is a pure, non-mutating calculation and works without an LLM key.
- **Market data:** FMP for instrument search (empty results, not an error, when `FMP_API_KEY` is unset); yfinance for daily close prices. No FX conversion — summary totals are in the profile base currency, while holding/allocation rows keep their instrument currency.
- **Scheduled refresh** only runs during regular U.S. market hours and requires the `X-Scheduler-Secret` header matching `SCHEDULER_SECRET`. Exchange holidays are not modeled.
- **Env files:** backend reads `backend/.env.local` (point at the dev Supabase project for full-stack debugging); frontend reads `frontend/.env.local`. Secrets live in each platform's store, never in the repo.

## Boundaries

- Don't commit secrets, `.env*` files, or real API keys.
- This is **not financial advice** — the assistant produces educational observations only and cannot place trades. Keep that framing in any assistant-facing copy.
- Pushes to `main` auto-deploy (Vercel + Render). Treat `main` as production.
