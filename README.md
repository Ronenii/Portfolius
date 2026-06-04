# Portfolius

> A long-term investor dashboard that shows you what you actually own by market exposure, sector, and asset class with an AI assistant help you rebalance against your goals.

**Status:** Hobby project · M1 implemented, live provider verification pending

## Why this exists

Every time I wanted to rebalance my ETF portfolio, I was doing the same thing:

1. Screenshot my brokerage app.
2. Paste it into Claude or ChatGPT.
3. Ask: *"Break this down by geographic exposure and tell me what to buy next to hit my target allocation."*
4. Repeat next month.

This app cuts out the screenshot loop. You enter your holdings once, set your long-term goals and preferred markets, and get:

- A portfolio dashboard sliced by market exposure, sector, asset class, or currency — not just by ticker.
- An AI assistant that already has the context (your profile, your holdings, your goals) and can answer "what should I buy next?" without you re-explaining.

## Features

- **Profile setup**: display name, base currency, time horizon, and investment frequency.
- **Holdings tracking**: manually create, edit, list, and delete holdings.
- **Authenticated API**: Supabase Auth sessions are verified by the backend and scoped by user ID.
- **Planned breakdowns**: same portfolio, different lenses (region, sector, asset class, currency).
- **Planned AI assistant**: chat panel grounded in portfolio + profile context.
- **Responsive**: works on desktop and phone.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind, TanStack Query |
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic |
| Database + Auth | Supabase (Postgres + Google OAuth or magic-link auth) |
| Market data | Planned: yfinance and Financial Modeling Prep |
| LLM | Planned: Groq, configurable |
| Frontend hosting | Vercel |
| Backend hosting | Render (free web service) |
| Cron (price refresh) | GitHub Actions |

Everything runs on a free tier — no credit card required at any provider. Target cost: **$0/month**.

> **Note on Render's free tier:** the backend service sleeps after 15 minutes of inactivity, so the first request after idle takes ~30 seconds to wake up. Fine for personal use. If it bothers you, a free uptime monitor (e.g. UptimeRobot) pinging `/healthz` every 5–10 minutes keeps it warm.

## Repository layout

```
portfolius/
├── backend/                   # FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/            # HTTP routes
│   │   ├── domain/            # business logic (snapshots, aggregations)
│   │   ├── data/              # SQLAlchemy models + repos
│   │   ├── integrations/      # yfinance, fmp, groq clients
│   │   └── jobs/              # cron entrypoints
│   ├── alembic/               # migrations
│   ├── tests/
│   ├── pyproject.toml
│   ├── render.yaml            # Render service config
│   └── Dockerfile
├── frontend/                  # React + Vite SPA
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── lib/api.ts         # generated from backend OpenAPI
│   │   └── lib/charts/
│   ├── package.json
│   └── vite.config.ts
├── .github/workflows/
│   ├── ci.yml                 # lint + test on PR
│   └── refresh-prices.yml     # nightly cron
├── CLAUDE.md                  # instructions for Claude Code
└── README.md
```

## Getting started

### Prerequisites

- Python 3.11+
- Node 20+
- Docker (for local Postgres)
- A Supabase project (free tier)
- A Render account (free, no card required)

### Local setup

```bash
# clone
git clone <repo> portfolius && cd portfolius

# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # fill in SUPABASE_URL and FRONTEND_ORIGINS if needed
docker compose up -d db       # local postgres on :5432
alembic upgrade head
uvicorn app.main:app --reload # http://localhost:8000  /docs for swagger

# frontend (new terminal)
cd ../frontend
npm install
cp .env.example .env.local    # VITE_API_URL=http://localhost:8000, VITE_SUPABASE_*
npm run dev                   # http://localhost:5173
```

### Required environment variables

**Backend (`backend/.env`):**

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/portfolius
SUPABASE_URL=https://<project>.supabase.co
AUTH_AUDIENCE=authenticated
FRONTEND_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

The backend verifies Supabase access tokens through the project's JWKS discovery endpoint:
`https://<project>.supabase.co/auth/v1/.well-known/jwks.json`. Do not use the legacy JWT secret for M1 backend auth.

**Frontend (`frontend/.env.local`):**

```
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=...
```

## Common commands

### Backend

```bash
uvicorn app.main:app --reload          # dev server
pytest                                  # tests
ruff check . && ruff format .           # lint + format
mypy app                                # type-check
alembic revision --autogenerate -m "…"  # new migration
alembic upgrade head                    # apply migrations
python -m app.jobs.refresh_prices       # run cron job locally
```

### Frontend

```bash
npm run dev                             # vite dev server
npm run build                           # production build
npm run lint                            # eslint
```

## Deployment

Pushes to `main` deploy automatically:

- **Frontend:** Vercel GitHub integration auto-deploys.
- **Backend:** Render's GitHub integration auto-deploys on push. Service is defined in `backend/render.yaml` (Blueprint) — Render reads it on connect and provisions the web service.
- **Migrations:** run on backend boot via `alembic upgrade head` (set as the pre-deploy command in `render.yaml`).

Secrets are set in each platform's secret store. Nothing sensitive lives in the repo.

### Setting up Render (one-time)

1. Push the repo to GitHub.
2. In Render: **New → Blueprint**, point at the repo. It picks up `backend/render.yaml` and creates the web service.
3. Add environment variables (`DATABASE_URL`, `SUPABASE_URL`, `AUTH_AUDIENCE`, and `FRONTEND_ORIGINS`) in the service dashboard. Mark `DATABASE_URL` and provider URLs as secret where available.
4. Take the resulting `https://<service>.onrender.com` URL and set it as `VITE_API_URL` in Vercel.

For `FRONTEND_ORIGINS`, use a JSON list of allowed frontend origins, for example:

```text
["http://localhost:5173","https://<your-vercel-app>.vercel.app"]
```

### Setting up Supabase Auth

1. In Supabase, copy the project URL from **Project Settings -> API** and use it as `SUPABASE_URL` on Render and `VITE_SUPABASE_URL` on Vercel.
2. Copy the **anon public** key from **Project Settings -> API keys -> legacy anon, service_role API keys** and use it as `VITE_SUPABASE_ANON_KEY` on Vercel.
3. For Google OAuth, create a Google Cloud web OAuth client and add `https://<project>.supabase.co/auth/v1/callback` as an authorized redirect URI.
4. In Supabase **Authentication -> Providers -> Google**, enable Google and paste the Google client ID and secret.
5. For local magic links, include `http://localhost:5173` in Supabase **Authentication -> URL Configuration** as an allowed redirect URL.

## Roadmap

- [x] M0 — Walking skeleton (frontend + backend + DB deployed end-to-end)
- [ ] M1 — Profile wizard + manual holdings CRUD implemented; live Supabase/hosting verification pending
- [ ] M2 — Daily price refresh + multi-dimensional breakdowns
- [ ] M3 — LLM chat with portfolio context
- [ ] M4 — Transactions log, goal projection, PWA install, CSV import

## Disclaimer

This is a personal analysis tool. It is **not financial advice**. The AI assistant produces educational observations grounded in your stated portfolio — it cannot place trades, does not know your full financial situation, and should not be treated as a substitute for a licensed advisor.

## License

MIT.
