# Portfolius Architecture

Portfolius is a personal long-term investor dashboard. The product should help a user understand what they own across regions, sectors, asset classes, and currencies, then ask an AI assistant grounded in that portfolio context for educational rebalancing analysis.

This document describes the intended architecture. It is deliberately implementation-oriented, but not a permission slip to build everything at once. Each milestone should land in small, reviewable slices.

## Architecture Principles

- Keep portfolio math deterministic and testable before adding AI behavior.
- Treat market data and LLMs as replaceable integrations behind local interfaces.
- Keep user-owned financial data scoped by authenticated user ID at every boundary.
- Prefer boring deployment: Vercel for the frontend, Render for the backend, Supabase Postgres for data.
- Make M0 prove the path from browser to API to database to deployment, with minimal product surface.

## System Context

```text
User
  |
  v
React SPA on Vercel
  |
  | HTTPS + Supabase JWT
  v
FastAPI service on Render
  |
  | SQLAlchemy / Alembic
  v
Supabase Postgres

FastAPI service
  |--> yfinance for prices
  |--> Financial Modeling Prep for instrument metadata
  |--> Groq-compatible LLM API for assistant responses

GitHub Actions
  |--> CI
  |--> scheduled price refresh endpoint or job command
```

## Runtime Components

### Frontend

The frontend is a React + Vite + TypeScript single-page app. It owns presentation, client-side routing, auth session handling, and API calls. It should not own portfolio calculations beyond lightweight display formatting.

Expected responsibilities:

- Supabase authentication — magic-link email and Google OAuth (social login). Additional providers (GitHub, Apple) can be enabled in the Supabase dashboard without backend changes.
- Dashboard pages and setup flows.
- TanStack Query cache and request state.
- Chart rendering through Recharts.
- Generated or typed API client for the backend.

### Backend

The backend is a FastAPI service. It owns authorization checks, persistence, portfolio calculations, market-data refreshes, and LLM context construction.

Expected responsibilities:

- Verify Supabase JWTs.
- Enforce user scoping.
- Provide REST endpoints under `/api/v1`.
- Persist and query data through SQLAlchemy repositories.
- Run deterministic domain services for snapshots and allocation breakdowns.
- Wrap third-party providers in integration modules.

### Database

The database is Supabase Postgres. The application should use Alembic-managed schema migrations from the backend. Supabase Auth is used for identity; application tables reference Supabase user IDs rather than storing passwords.

### Integrations

Integrations must sit behind local client modules so they can be mocked in tests and swapped later.

- `yfinance`: daily close prices.
- Financial Modeling Prep: instrument profile, sector, country, and asset metadata.
- Groq-compatible LLM API: assistant responses grounded in portfolio context.

## Backend Module Layout

```text
backend/app/
├── main.py
├── api/v1/
│   ├── health.py
│   ├── profile.py
│   ├── holdings.py
│   ├── portfolio.py
│   └── assistant.py
├── core/
│   ├── config.py
│   ├── auth.py
│   └── logging.py
├── data/
│   ├── database.py
│   ├── models.py
│   └── repositories/
├── domain/
│   ├── portfolio_math.py
│   ├── snapshots.py
│   └── allocation.py
├── integrations/
│   ├── market_data.py
│   ├── fmp.py
│   ├── yfinance_client.py
│   └── llm.py
└── jobs/
    └── refresh_prices.py
```

## Frontend Module Layout

```text
frontend/src/
├── app/
│   ├── router.tsx
│   └── query-client.ts
├── pages/
│   ├── DashboardPage.tsx
│   ├── ProfilePage.tsx
│   ├── HoldingsPage.tsx
│   └── AssistantPage.tsx
├── components/
│   ├── layout/
│   ├── charts/
│   └── ui/
├── features/
│   ├── auth/
│   ├── profile/
│   ├── holdings/
│   ├── portfolio/
│   └── assistant/
└── lib/
    ├── api.ts
    ├── supabase.ts
    └── format.ts
```

## Initial Data Model

The model should start small and grow only when a milestone needs it.

```text
profiles
- id
- user_id
- display_name
- base_currency
- time_horizon
- investment_frequency
- created_at
- updated_at

instruments
- id
- symbol
- name
- exchange
- currency
- asset_class
- sector
- country
- region
- metadata_updated_at

holdings
- id
- user_id
- instrument_id
- quantity
- average_cost
- created_at
- updated_at

prices
- id
- instrument_id
- price_date
- close_price
- currency
- source
- created_at
```

Later milestones can add transactions, target allocations, assistant conversations, CSV imports, and richer instrument exposure tables.

## API Shape

M0 should expose only health and a minimal authenticated database probe. Later milestones can expand the API.

```text
GET /healthz
GET /api/v1/me
GET /api/v1/db-ping
```

Planned product endpoints:

```text
GET/PUT /api/v1/profile
GET /api/v1/instruments/search
GET/POST /api/v1/holdings
GET/PUT/DELETE /api/v1/holdings/{holding_id}
GET /api/v1/portfolio/snapshot
GET /api/v1/portfolio/breakdowns
POST /api/v1/assistant/messages
POST /api/v1/jobs/refresh-prices
```

## Authentication Strategy

Authentication is handled entirely by Supabase Auth. The frontend never handles passwords or stores credentials.

Supported sign-in methods (M1):

- **Google OAuth** (primary): `supabase.auth.signInWithOAuth({ provider: 'google' })`. Requires a Google Cloud OAuth client ID and secret configured in the Supabase dashboard.
- **Magic-link email** (fallback): `supabase.auth.signInWithOtp({ email })`. No third-party OAuth setup required.

Both methods produce a Supabase JWT. The backend verifies that JWT on every protected request using Supabase's JWKS discovery endpoint at `https://<project>.supabase.co/auth/v1/.well-known/jwks.json`, with `AUTH_AUDIENCE=authenticated`. The backend does not differentiate between auth providers.

To enable Google OAuth:
1. Create an OAuth client in Google Cloud Console (Credentials → OAuth 2.0 Client ID, type: Web).
2. Add the Supabase callback URL as an authorised redirect URI: `https://<project>.supabase.co/auth/v1/callback`.
3. In the Supabase dashboard: Authentication → Providers → Google → enable, paste Client ID and Secret.

## Security Boundaries

- Frontend authenticates with Supabase and sends the access token to the backend.
- Backend verifies the JWT on protected routes.
- Every user-owned query filters by `user_id`.
- Service secrets live only in platform secret stores and local `.env` files.
- The assistant must receive summarized portfolio context, not raw secrets or unrelated user metadata.

## Testing Strategy

- Backend unit tests cover domain portfolio math without network or database calls.
- Backend API tests cover auth behavior, user scoping, and core response contracts.
- Integration clients are mocked unless a test is explicitly marked as live.
- Frontend tests focus on high-risk UI flows and API state handling.
- CI runs formatting, linting, type checks, and tests before deploy.

## Deployment Strategy

- Frontend deploys to Vercel from `main`.
- Backend deploys to Render from `main`.
- Database schema changes are applied through Alembic migrations.
- GitHub Actions runs CI on pull requests.
- A scheduled GitHub Actions workflow later triggers price refreshes.

## Milestone Boundaries

- M0: walking skeleton from deployed frontend to deployed backend to database.
- M1: authentication (Google OAuth + magic-link), profile wizard, and manual holdings CRUD.
- M2: instrument search/autofill, price refresh, and allocation breakdowns.
- M3: AI assistant grounded in portfolio context.
- M4: transactions, projections, PWA install, and CSV import.

M0 should not include portfolio math, charting, market-data providers, or LLM integration. Those are intentionally deferred.
