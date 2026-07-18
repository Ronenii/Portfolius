# Portfolius

> A long-term investor dashboard that shows you what you actually own by market exposure, sector, and asset class with an AI assistant help you rebalance against your goals.

**Status:** Hobby project · M4 complete

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

- **Profile setup**: display name, base currency, time horizon, investment frequency, risk tolerance, interest tags, sectors to avoid, and a free-text goals note.
- **Holdings tracking**: create, edit, list, and delete holdings with instrument search/autofill.
- **Authenticated API**: Supabase Auth sessions are verified by the backend and scoped by user ID.
- **Portfolio dashboard**: current values, cost basis, gain/loss, price coverage, and allocation breakdowns by instrument, asset class, sector, country, region, and currency.
- **Allocation exploration**: drill into any allocation slice to see the instrument composition inside it, with both "% of slice" and "% of portfolio"; switch each dimension between bar, donut, and table views. The drill-down is keyboard-accessible and the dense table stays the canonical readable view.
- **What-if simulation**: build a buy/sell basket and see before/after/delta across every breakdown dimension without committing any trades.
- **AI assistant**: floating chat grounded in your holdings, profile goals, and live simulation results. Uses Groq's `openai/gpt-oss-120b` reasoning model with tool-calling, and renders replies as Markdown (bold figures, lists, and compact before/after tables). Disabled gracefully when `LLM_API_KEY` is not set; when the free-tier per-minute token budget is exhausted mid-conversation it returns a clear "try again in a minute" message rather than failing.
- **Transactions ledger**: a full buy/sell history (date, quantity, price, fees) is the source of truth; holdings are derived by folding each instrument's transactions with weighted-average cost, and are read-only everywhere else — you edit a position by adding, editing, or deleting a transaction, not the holding.
- **Goal projection**: a dashboard chart projecting portfolio value forward (conservative/expected/optimistic bands plus a cost-basis line) against your goal target and contribution rate. The expected annual return is auto-computed from your current holdings' historical performance, not manually entered.
- **Installable PWA**: installable on desktop and mobile with a custom install prompt; the service worker precaches only the app shell and always fetches API/auth data fresh.
- **CSV import**: bulk-import a transaction history or a simple positions list from a CSV template, with a per-row preview and import report so one bad row doesn't block the rest.
- **Responsive**: works on desktop and phone.

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind, TanStack Query |
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic |
| Database + Auth | Supabase (Postgres + Google OAuth or magic-link auth) |
| Market data | Financial Modeling Prep for instrument search, yfinance for daily close prices |
| LLM | Groq (`openai/gpt-oss-120b` reasoning model), OpenAI-compatible, configurable |
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
│   └── refresh-prices.yml     # market-hours price refresh
├── AGENTS.md                  # build/test/conventions guidance for AI coding agents
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
cp .env.local.example .env.local # fill with dev Supabase values for debugging
alembic upgrade head
uvicorn app.main:app --reload # http://localhost:8000  /docs for swagger

# frontend (new terminal)
cd ../frontend
npm install
cp .env.example .env.local    # VITE_API_URL=http://localhost:8000, VITE_SUPABASE_*
npm run dev                   # http://localhost:5173
```

### Required environment variables

**Backend debug (`backend/.env.local`):**

```
DATABASE_URL=postgresql+psycopg://postgres:<dev-db-password>@<dev-db-host>:5432/postgres
SUPABASE_URL=https://<dev-project>.supabase.co
AUTH_AUDIENCE=authenticated
FRONTEND_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
FMP_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
SCHEDULER_SECRET=...
```

VS Code's `Backend: FastAPI` debug configuration reads `backend/.env.local`, so point it at the dev Supabase project rather than production.

For backend-only migration or repository work, you can still point `DATABASE_URL` at a local Postgres container instead. For full frontend/backend debugging, use the dev Supabase database so Auth and API tokens belong to the same Supabase project.

The backend verifies Supabase access tokens through the project's JWKS discovery endpoint:
`https://<project>.supabase.co/auth/v1/.well-known/jwks.json`. Do not use the legacy JWT secret for M1 backend auth.

M2 market data uses Financial Modeling Prep for instrument search and basic metadata autofill, Alpha Vantage for ETF exposure metadata when `ALPHA_VANTAGE_API_KEY` is set, and `yfinance` for latest daily close prices. `FMP_API_KEY` enables provider-backed search; without it, the backend returns an empty search result rather than breaking the holdings form. `SCHEDULER_SECRET` protects scheduler-triggered refreshes.

Existing ETF instrument metadata can be refreshed by the signed-in user as a one-time cleanup action. This scans ETF instruments in that user's holdings, refreshes provider metadata, and returns `requested`, `updated`, `skipped`, and `failed` counts.

```text
POST $PORTFOLIUS_API_URL/api/v1/jobs/refresh-etf-metadata
Authorization: Bearer <supabase-access-token>
```

M2 does not do FX conversion. Portfolio-wide summary totals include priced holdings in the profile base currency, while holdings and allocation rows retain their instrument currency.

**M3 assistant and simulation:**

```
LLM_API_KEY=<your-groq-api-key>      # get one at console.groq.com — free tier
LLM_BASE_URL=https://api.groq.com/openai/v1  # default; override to use a different OpenAI-compatible provider
LLM_MODEL=openai/gpt-oss-120b        # default; override as needed
LLM_MAX_TOKENS=3072                  # default
LLM_REASONING_EFFORT=low             # gpt-oss reasoning effort: low | medium | high (unset to omit for non-reasoning models)
```

`LLM_REASONING_EFFORT` is only valid for reasoning models such as `openai/gpt-oss-120b`, where Groq accepts exactly `low`, `medium`, or `high`. If you point `LLM_MODEL` at a non-reasoning model (e.g. `llama-3.3-70b-versatile`), leave `LLM_REASONING_EFFORT` unset, or the request is rejected with HTTP 400.

Without `LLM_API_KEY` the assistant endpoints return `503 "Assistant is not configured"`. The simulation endpoint (`POST /api/v1/portfolio/simulate`) works without an LLM key. The simulated snapshot is non-mutating — hypothetical buy/sell legs are never persisted as holdings — but simulating a buy of an instrument you don't yet hold will resolve and cache its metadata (via FMP) and refresh its latest price (via yfinance) as a side effect. The assistant's `simulate_trades` tool runs through the same pipeline with the same clients, so its before/after numbers match the Simulation tab exactly.

**Frontend (`frontend/.env.local`):**

```
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=...
VITE_PROD_MODE=false   # set truthy (1/true/yes/on) to hide the dashboard backend-status strip in production
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
python -m app.jobs.refresh_prices
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

### Scheduled price refresh

M2 refreshes daily close prices through `.github/workflows/refresh-prices.yml`. The workflow runs hourly on weekdays during the regular U.S. market session window and targets the deployed production backend.

```text
POST $PORTFOLIUS_API_URL/api/v1/jobs/refresh-prices
X-Scheduler-Secret: $PORTFOLIUS_SCHEDULER_SECRET
```

The backend also checks regular U.S. market hours before accepting scheduler-triggered refreshes, so manual dashboard refreshes can still run while scheduled refreshes skip closed-market windows. Exchange holidays are not modeled in M2. Scheduler-triggered refreshes operate across all production users and request each distinct held instrument once.

Required GitHub repository secrets:

```text
PORTFOLIUS_API_URL=https://<backend-service>
PORTFOLIUS_SCHEDULER_SECRET=<same value as backend SCHEDULER_SECRET>
```

### Setting up Render (one-time)

1. Push the repo to GitHub.
2. In Render: **New → Blueprint**, point at the repo. It picks up `backend/render.yaml` and creates the web service.
3. Add environment variables (`DATABASE_URL`, `SUPABASE_URL`, `AUTH_AUDIENCE`, `FRONTEND_ORIGINS`, `FMP_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `SCHEDULER_SECRET`, and `LLM_API_KEY`) in the service dashboard. Mark `DATABASE_URL`, provider keys, and scheduler secrets as secret where available. `LLM_MODEL` is pre-set in `render.yaml`; override it in the dashboard if you want a different model. **Keep `LLM_MODEL` and `LLM_REASONING_EFFORT` consistent**: a reasoning model (`openai/gpt-oss-120b`) needs `LLM_REASONING_EFFORT` set to `low`/`medium`/`high`, while a non-reasoning model (`llama-3.3-70b-versatile`) requires it unset — a mismatch causes every assistant request to fail with HTTP 400.
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
- [x] M1 — Profile wizard + manual holdings CRUD
- [x] M2 — Asset autocomplete + daily price refresh + multi-dimensional breakdowns
- [x] M3 — AI assistant grounded in portfolio context + portfolio simulation (what-if buy/sell)
- [x] M4 — Allocation exploration (composition drill-downs + selectable chart types)
- [ ] M5 — Transactions log, goal projection, PWA install, CSV import
- [ ] M6 — Profile intelligence, dark mode, suggested interest/avoid tags, and automatic typo cleanup

## Disclaimer

This is a personal analysis tool. It is **not financial advice**. The AI assistant produces educational observations grounded in your stated portfolio — it cannot place trades, does not know your full financial situation, and should not be treated as a substitute for a licensed advisor.

## License

MIT.
