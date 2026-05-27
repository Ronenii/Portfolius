# Portfolius Web · UI Kit

An interactive recreation of the **Portfolius** web dashboard.

> ⚠️ The source repository has no implemented frontend yet — only a FastAPI backend skeleton and architecture docs. This kit is the **first proposed visual implementation** of the product, derived from the README, the architecture spec, and the planned routes. Treat it as a strong opening proposal rather than a documentation of existing code.

## What's in here

| File | What it is |
|---|---|
| `index.html` | Loads React + Babel and mounts the app. Demo of all screens, click-through. |
| `styles.css` | Kit-specific layout styles. Tokens come from `../../colors_and_type.css`. |
| `components.jsx` | Shared atoms — `Button`, `Card`, `Badge`, `Field`, `Sidebar`, `Header`, `KpiTile`, `Donut`, `Bars`, `AssistantPanel`. |
| `screens.jsx` | `DashboardScreen`, `HoldingsScreen`, `AssistantScreen`, `ProfileScreen`. |
| `app.jsx` | The `App` component — routing, mode toggle, mock state. |

## Screens

The kit demonstrates four screens, navigable from the sidebar:

1. **Dashboard** — KPI row, allocation donut, top holdings preview, "next contribution" callout.
2. **Holdings** — Filterable table of all positions with add/edit/delete affordances.
3. **Assistant** — Chat panel with a grounded-context strip and message bubbles.
4. **Profile** — A short setup form: goals, time horizon, frequency, base currency, markets of interest.

A header switch flips the app between **Paper** (default) and **Terminal** modes. Both modes share the same components — only surface tokens swap.

## What's faked

- No backend calls — everything is mock data in `app.jsx`.
- The assistant's responses are canned and grounded against the mock portfolio.
- Magic-link auth is skipped — the kit lands you straight on the dashboard.

## Extending

When the real frontend is implemented, this kit should be reconciled against it. Pull tokens from any future `tailwind.config.ts` or theme module. Replace mock data with the actual TanStack Query hooks. The component API was kept close to what shadcn/ui + Recharts would look like, but no shadcn-specific code is used.
