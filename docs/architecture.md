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
  |--> hourly market-hours price refresh endpoint
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

M2 intentionally does not perform FX conversion. Snapshot summary fields include priced holdings in the user's profile base currency, while holdings and allocation rows preserve instrument currencies.

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
│   ├── allocation.py
│   └── simulation.py
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

M3 added conversations and messages:

```text
conversations
- id
- user_id
- title
- created_at
- updated_at

messages
- id
- conversation_id  (FK → conversations.id, cascade delete)
- role             ("user" | "assistant")
- content
- created_at
```

Later milestones can add transactions, target allocations, CSV imports, and richer instrument exposure tables.

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
GET /api/v1/portfolio/breakdowns/{dimension}/{key}/composition
POST /api/v1/portfolio/simulate
POST /api/v1/assistant/messages
GET  /api/v1/assistant/conversations
GET  /api/v1/assistant/conversations/{conversation_id}
POST /api/v1/jobs/refresh-prices
```

M3 assistant endpoints:

- `POST /api/v1/assistant/messages` — send a user message, receive a grounded reply. Creates a new conversation when `conversation_id` is omitted. Returns `503` when `LLM_API_KEY` is not configured.
- `GET /api/v1/assistant/conversations` — list the authenticated user's conversations, newest first.
- `GET /api/v1/assistant/conversations/{conversation_id}` — return the conversation and its ordered messages. Returns `404` for another user's conversation.

The assistant tool-call loop exposes two tools to the model: `get_portfolio_breakdowns()` and `simulate_trades(legs)`. Both execute the same user-scoped domain functions used by the REST endpoints, so the model reasons over identical numbers. The loop is capped at 4 iterations.

Implemented M2 job endpoint behavior:

```text
Manual dashboard refresh:
POST /api/v1/jobs/refresh-prices
Authorization: Bearer <Supabase access token>

Scheduled refresh:
POST /api/v1/jobs/refresh-prices
X-Scheduler-Secret: <SCHEDULER_SECRET>
```

The scheduled path is called by GitHub Actions using repository secrets `PORTFOLIUS_API_URL` and `PORTFOLIUS_SCHEDULER_SECRET` for the deployed production backend. The workflow runs hourly on weekdays during the regular U.S. market session window and can also be dispatched manually. The backend still checks regular U.S. market hours and returns a zero-count result for scheduler calls outside that window; exchange holidays are not modeled in M2. Scheduler-triggered refreshes operate across all production users and request each distinct held instrument once. Local operators can run `python -m app.jobs.refresh_prices` when a command-line refresh is more convenient.

## Design Language and Terminal Mode (M3.x)

The CSS custom-property token system was expanded into a formal design language covering the full set of surfaces, foreground colors, radii, shadows, motion, and focus rings that all components reference. Key additions:

- **Paper and terminal surface palettes**: `--paper-50` through `--paper-300` for light surfaces; `--ink-950` through `--ink-200` for dark surfaces.
- **Semantic semantic color pairs**: `--gain-*` / `--loss-*` at 700/500/300/100 stops; `--info-*` and `--caution-*` stops.
- **Foreground tokens**: `--fg-paper` for light mode, `--fg-terminal` for terminal mode.
- **Accent ramp**: `--accent-900` through `--accent-50`.
- **Elevation**: `--shadow-0` through `--shadow-3` and `--shadow-inset`.
- **Motion**: `--ease-out`, `--ease-in`, `--ease-standard` curves with `--dur-fast` / `--dur-base` / `--dur-slow` durations.
- **Border radii**: `--radius-xs` through `--radius-full`.
- **Focus rings**: `--focus-ring` (paper mode) and `--focus-ring-terminal`.
- **Layout constants**: `--sidebar-w: 220px`, `--header-h: 56px`.

### Terminal mode

`AppShell` adds a `mode-terminal` class to `app-frame` when terminal mode is active. The mode is toggled by a sidebar button that persists the preference to `localStorage` under the key `portfolius:terminal-mode`. A `Sun` icon returns to paper mode; a `Monitor` icon enters terminal mode. All affected components respond to the parent `mode-terminal` class through CSS selectors rather than React context.

### Navigation updates

Nav icons were updated to `LayoutDashboard`, `Landmark`, and `UserRound`. The active nav link background changed from `--paper-50` with a rule border to a `--accent-100` fill with no visible border. Hover transitions use `--dur-fast` with `--ease-out`. Font size dropped from 14 px to 13 px.

### Dashboard KPI tiles

The primary KPI tile (priced value) gains a `kpi-tile--primary` modifier class that applies a stronger typographic weight and an accent-tinted background. In terminal mode the primary tile uses ink surfaces. The `num` utility class was removed from KPI `<strong>` elements; typography is driven by the tile class instead.

### Simulation panel mobile layout

The `simulation-dimension-control` modifier was added to the dimension `segmented-control` in `SimulationPanel`. On narrow viewports it becomes a horizontally scrolling row with hidden scrollbars, keeping the dimension selector usable without wrapping.

## Assistant Enhancements (M3.x)

### Price tool

A third tool, `get_instrument_prices`, was added to the assistant tool-call loop. It accepts up to eight ticker symbols and returns the latest available close price, exchange, currency, and date for each. The resolution strategy is:

1. Attempt a live fetch via `MarketDataClient` (backed by `YFinanceMarketDataClient`).
2. Fall back to the most recent stored close from the `prices` table for instruments already in the local database.
3. Symbols with neither a live price nor a local record are returned in a `missing` list.

The `MarketDataClient` is injected into `run_assistant_turn` and `execute_tool` as an optional parameter. The `post_assistant_message` endpoint wires in a `YFinanceMarketDataClient` instance through FastAPI dependency injection (`get_market_data_client`).

The system prompt was updated to instruct the model to use the price tool before naming specific buy ideas or comparing instruments, and to include a relevant price or number in conversational answers.

### Inline function-call markup stripping

Some LLM responses include raw `<function=…>…</function>` tags in the message content. These are now stripped in two places:

- **Backend** (`domain/assistant.py`): `final_reply_from_completion` removes inline markup from the reply before it is persisted and returned.
- **Frontend** (`ChatMessageList.tsx`): `displayContent` strips the pattern from rendered content. `inlineTools` extracts tool names from embedded markup so they contribute to the tool-badge display even when the backend stripping missed them.

### Tool badge for price checks

`ChatMessageList` maps `get_instrument_prices` in `used_tools` to the label `"checked prices"`, consistent with the existing `"checked allocation"` and `"ran a simulation"` labels.

### Conversation message deduplication fix

`conversationMessages` in `AssistantWidget` previously lost `used_tools` when optimistic messages were replaced by the saved conversation response. The merge now carries `used_tools` from the matching optimistic message onto the real message by key (`role + "\0" + content`), so tool badges survive the transition from optimistic to persisted state.

The loading spinner is now suppressed when optimistic messages are already in the thread, so the user sees the sent exchange immediately rather than a loading state while the conversation reloads.

### Mobile sheet layout

`AssistantWidget` gains the `assistant-mobile-sheet` class, enabling bottom-sheet positioning and full-screen expansion on narrow viewports via `@media` rules in the design-language CSS layer.

### Trend loader

`components/ui/TrendLoader.tsx` provides a branded loading indicator: an animated upward-trending SVG line with a leading dot, replacing the previous text-only "Loading…" empty-states. The path is normalised to `pathLength={100}` so the stroke draw and dot animation stay in sync regardless of rendered size. It respects `prefers-reduced-motion` (rendering a static tip dot instead of `animateMotion`) and exposes accessible status text via `role="status"` and an `srLabel`. It is used on the dashboard (snapshot and allocation loads) and across the auth, holdings, and profile gates.

### Production mode

The dashboard reads a `VITE_PROD_MODE` flag (truthy values: `1`, `true`, `yes`, `on`). When enabled, `DashboardPage` hides the "Backend status" strip and disables the `backend-health` query entirely, so production users never see the developer-facing health/endpoint diagnostics. The flag defaults to off, preserving the status strip in local development.

## Allocation Exploration (M4)

Allocation breakdowns support progressive disclosure: a user starts with a high-level dimension such as asset class, sector, region, country, currency, or instrument, then inspects what makes up a selected allocation row without leaving the dashboard. For example, if `ETF` is 62% of the portfolio, hovering or focusing that row shows the instrument composition inside that slice, such as `VOO` at 30%, `IXC` at 5%, and the remaining ETF holdings by their contribution.

The backend remains the source of truth for the math. Composition is a new, pure, in-memory transform over the existing M2 snapshot pipeline — `build_composition(snapshot, dimension, key, *, currency=None)` in `domain/allocation.py` — exposed through a dedicated, lazily-fetched endpoint so the existing `PortfolioBreakdowns` contract (which the simulation diff and the assistant `get_portfolio_breakdowns` tool both consume) stays untouched:

```text
GET /api/v1/portfolio/breakdowns/{dimension}/{key}/composition
```

- `dimension` is one of `asset_class`, `sector`, `country`, `region`, `currency`, `instrument`; an unknown dimension returns `404`. The optional `currency` query parameter disambiguates a label present in more than one currency, defaulting to the first matching currency.
- The route is authenticated and user-scoped exactly like the other portfolio routes: `401` without a token, `404` when the user has no profile, and `200` with an empty child list (not an error) for an unknown-but-valid key.
- `build_composition` reuses the M2 `label_for` mappers and `percent_of`, so composition labels and percentages match the breakdowns exactly, including `Unclassified` and the `(currency, label)` keying. It collapses repeated lots of one instrument into a single child row with `holding_count` accumulated.

The `CompositionResponse` payload carries the parent slice (`dimension`, `key`, `currency`, `market_value`, `percent_of_portfolio`), an `unpriced_holding_count`, and `children` rows. Each `CompositionRow` includes the child `instrument_id`, `symbol`, `name`, `currency`, `market_value`, `holding_count`, `percent_of_parent`, and `percent_of_portfolio`, with decimals serialized as strings like the other portfolio contracts. The two percentages are distinct on purpose: a tooltip needs to say both "VOO is 30% of the portfolio" and "VOO is 48% of the ETF slice." `percent_of_parent` is the child's value over the slice total; `percent_of_portfolio` is over the per-currency portfolio total. Missing-price holdings are excluded from the percentages and surfaced via `unpriced_holding_count`, just as the M2 breakdowns do.

The frontend renders the same allocation data through user-selectable chart types: bar, donut, or table. The selection is a presentation preference persisted client-side to `localStorage` under `portfolius:allocation-chart-type` (mirroring the terminal-mode pattern), defaulting to bar; it never changes the backend math or the table rows used for accessibility and precise reading. `bar` and `donut` render the chart alongside the dense table; `table` hides the chart and shows the table full-width. No line charts: a single current snapshot is not time-series data, so trend visualizations are deferred until a later milestone adds price or allocation history.

The drill-down is not hover-only. Each allocation table row is focusable (`role="button"`, `aria-expanded`) and opens the composition popover (`CompositionPopover`, which lazily fetches via TanStack Query) on hover, focus, and `Enter`/`Space`, closing on blur/`Escape`; chart segments open the same popover on click as an enhancement. Only one slice is open at a time. The popover shows the same data regardless of trigger and handles loading, empty, and error states, so screen-reader users reading the dense table get the identical composition — the table remains the canonical readable view.

## Portfolio Simulation (M3)

Portfolio simulation lets a user run *what-if scenarios* before committing to a trade. A scenario is a basket of hypothetical buy/sell legs (for example, sell 10 of AAPL, buy 5 of VXUS and 3 of BND). Portfolius then shows the resulting allocation **before, after, and delta** across every existing breakdown dimension, so the user can see how a prospective trade would shift their distribution. This is the bridge between understanding the current portfolio and deciding how to rebalance, and in M3 it becomes the substrate the AI assistant reasons over when suggesting trades.

### Stateless reuse of the snapshot pipeline

Simulation introduces no new portfolio math, and the simulated snapshot itself is non-mutating — `simulate_for_user` computes the "after" snapshot inside `db.no_autoflush` and issues a `db.rollback()` before returning, so hypothetical legs never persist as holdings. A scenario is otherwise a transform over the existing deterministic pipeline:

```text
real holdings + latest prices
        │
        ├─► build_portfolio_snapshot ─► build_allocation_breakdowns   = "before"
        │
   apply_trades(holdings, prices, legs)        (new pure function)
        │
        └─► build_portfolio_snapshot ─► build_allocation_breakdowns   = "after"
                                  │
                          diff_breakdowns(before, after)               = "delta"
```

- A new `domain/simulation.py` module holds `apply_trades(...)`, which returns a hypothetical `(holdings, prices)`, and `diff_breakdowns(...)`, which computes per-dimension deltas. Both are pure and unit-testable, consistent with the principle of keeping portfolio math deterministic before adding AI behavior.
- Buying an instrument that is not yet held resolves its metadata and latest price through injected clients rather than relying on the symbol already being in the local database. `simulate_for_user` accepts an optional `FmpInstrumentLookupClient` and `MarketDataClient` (wired via FastAPI dependency injection in `api/v1/portfolio.py` as `get_instrument_lookup_client` / `get_market_data_client`). `resolve_or_create_instrument` returns a local instrument when present, otherwise fetches an FMP profile and persists a new `instruments` row; `resolve_latest_price` fetches a live close via the `MarketDataClient` and upserts it into `prices`. These resolution/caching writes **are committed** — the rollback above only discards the hypothetical holdings, not the newly-cached instrument metadata and refreshed prices. Without sector, country, and region the holding cannot be allocated meaningfully, so simulation still depends on resolvable instrument metadata.
- Sells reduce an existing position and are validated against the held quantity. The product does not model shorting.
- Scenarios are computed on demand and not stored. Saving named scenarios is a possible later enhancement, deliberately deferred.

### API shape

```text
POST /api/v1/portfolio/simulate

Request:  { legs: [ { symbol | instrument_id, action: "buy" | "sell", quantity, price? } ] }
Response: { current: PortfolioBreakdowns,
            simulated: PortfolioBreakdowns,
            delta: [ { dimension, label, percent_before, percent_after, percent_change } ],
            warnings: [ ... ] }
```

The endpoint uses POST because the input is a structured basket. The simulated result is non-mutating with respect to the user's holdings, though resolving a not-yet-held instrument may cache its metadata and refresh its latest price as a side effect (see above). It is user-scoped exactly like the other portfolio endpoints, and `price?` defaults to the latest stored close, falling back to a live `MarketDataClient` fetch when none is stored. Warnings cover cases such as an unpriced new instrument or a sell that exceeds the held quantity.

### Assistant integration

The assistant invokes the same `simulate` pipeline to ground rebalancing suggestions in a concrete before/after delta rather than vague advice. As with all assistant context, it receives summarized simulated allocation, not raw holdings or secrets.

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
- M2: instrument search/autofill, price refresh, and allocation breakdowns. **Done.**
- M3: AI assistant grounded in portfolio context, and portfolio simulation (what-if buy/sell scenarios). **Done.**
- M3.x: design language, terminal mode, mobile layout, and assistant price tool. **Done.**
- M4: allocation exploration, including composition drill-downs and user-selectable chart types. **Done.**
- M5: transactions, projections, PWA install, and CSV import.
- M6: profile intelligence and personalization, including dark mode, suggested interest/avoid tags, and automatic typo cleanup for free-form profile keywords.

Future holding-entry improvements should make the add-holding flow ticker-first. A user should normally add a holding by entering a ticker and selecting the resolved instrument metadata. Manual instrument details should only be shown when the ticker lookup cannot find the instrument, so users are not asked to fill exchange, currency, asset class, sector, country, or region when the system can resolve them.

Future profile-keyword improvements can recommend tags from the user's goals and portfolio context, detect likely duplicates, and offer typo fixes before saving. These suggestions should remain user-confirmed rather than silently rewriting profile intent.

M0 should not include portfolio math, charting, market-data providers, or LLM integration. Those are intentionally deferred.
