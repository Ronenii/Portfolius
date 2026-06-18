# UI Overhaul — Design Spec

**Date:** 2026-06-18
**Branch:** `ui/enhance-and-fix` (phased commits, single PR at the end)
**Scope:** Frontend only (`frontend/src`, primarily `index.css` + shared components)

## Goal

Polish the Portfolius frontend across four axes without breaking the documented
brand. The brand is a **stoic ledger crossed with a modern terminal** — calm,
muted, no celebration. Every change here works *within* that system, using its
tokens more confidently rather than introducing new visual language.

The four axes:

1. Full responsive polish for mobile and desktop web.
2. Full polish of terminal mode on every surface.
3. Loading state (inline mini-spinner) on buttons that trigger long async work.
4. General modernization — replace excessive gray with the correct ink/fg
   tokens, add the brand-permitted micro-motion, make the app feel alive while
   staying calm.

## Decisions (from brainstorming)

- **Aliveness = within brand.** No new colors, no gradients on primary surfaces,
  no bouncy motion. Use `--fg-paper`/`--fg-terminal` and `--ink-700` for primary
  body text instead of defaulting to `--ink-500`; use teal accents and the
  motion the design doc already permits (120/200/320ms fades+slides, count-up
  numerics).
- **Spinner = inline mini-spinner in the shared `Button` component** via a new
  `loading` prop. Disables the button and shows a spinning indicator while a
  long operation runs. Respects `prefers-reduced-motion`.
- **Terminal mode = keep the global user toggle.** "Optimize completely" means
  auditing every page/component so both paper and terminal modes are fully
  styled — no half-themed surfaces. No behavioral change to the toggle.
- **Responsive = full audit** at mobile (~375px), tablet (~768px), desktop.
  Verify by running the app and viewing renders, not by reading CSS alone.
- **Delivery = one branch, one commit per stage**, single PR at the end.

## Current state (what exists)

- `index.css` (~2750 lines) holds the entire design system: tokens, paper +
  `.mode-terminal` overrides, responsive breakpoints at 860px and 560px, and a
  `TrendLoader` (animated trend-line) for full-section loading.
- `components/ui/Button.tsx` — shared button, variants primary/secondary/ghost,
  optional leading icon. **No loading state.**
- `components/ui/TrendLoader.tsx` — used for page/section-level loading on
  Dashboard, Holdings, ProfileEdit, ProfileGate, CompositionPopover, AuthRoutes.
- `AppShell.tsx` — sidebar nav + global terminal toggle (localStorage), assistant
  widget mounted app-wide.
- Surfaces to cover: Dashboard, Holdings (+ form), Profile wizard, Profile edit,
  Login/auth (magic link), Simulation panel, Composition popover, Assistant
  widget, Instrument search, Allocation chart/donut.

## Where the work lives

### Gray text (modernization)

Secondary text across the app defaults to `--ink-500` (#6E6757) — labels,
captions, table `td` cells, field hints, subtitles, the `.lede`, KPI sub-labels.
Primary body text in places uses `--ink-700`. The "too much gray" complaint is a
**token-level** issue concentrated in `index.css`, not scattered inline styles.

Approach: promote primary content text to `--fg-paper`/`--fg-terminal`, keep
`--ink-500` only for genuinely tertiary metadata (eyebrows, timestamps), and let
teal carry the accent role it's designed for. Numeric/heading hierarchy stays.

### Async buttons (spinner)

Buttons that fire long operations and need the loading state:

- `SimulationPanel` — run simulation (longest; may also dim its result panel).
- `HoldingsPage` — add/save holding (form submit).
- `ProfileWizardPage` / `ProfileEditPage` — save profile.
- `AuthRoutes` — request magic link.
- `AssistantWidget` — send (already has a pending affordance; reconcile).

Only `Button.tsx` is used in ~8 places; some submits are raw `<button>` and will
be migrated to the shared component or given the same `loading` treatment.

### Terminal mode gaps

`.mode-terminal` overrides are extensive but were authored incrementally. The
audit confirms each surface above renders fully themed in terminal mode —
checking charts, popovers, the simulation result, instrument dropdown, empty
states, and focus rings specifically.

## Plan — four stages

### Stage 0 — Foundations (shared primitives)

- Add `loading` prop to `Button.tsx`: when true, disable + render a spinning
  indicator (new `.button__spinner`), keep label, set `aria-busy`. Add a small
  reusable `Spinner` (CSS keyframe `spin`, teal `currentColor`, reduced-motion
  fallback to a static/blink state consistent with `TrendLoader`).
- Add any missing motion tokens/utilities (count-up helper for numerics if
  cheap; otherwise defer).

### Stage 1 — Modernization / de-gray (mostly `index.css`)

- Re-grade text colors: primary copy to fg tokens, keep ink-500 for tertiary.
- Apply brand-permitted micro-motion: panel/card enter transitions, hover states
  that shift color (not opacity), count-up on KPI numerics if included.
- Tighten accent usage so teal reads as "alive" without new hues.
- Update the design doc only if any token meaning changes (expected: none).

### Stage 2 — Responsive audit & fixes

- Walk every surface at 375 / 768 / desktop. Fix overflow, cramped padding,
  touch targets (<44px), table reflow, sidebar/nav behavior, assistant sheet,
  simulation editor, forms.
- Verify by running the app and viewing renders at each breakpoint.

### Stage 3 — Terminal mode completeness

- Per-surface pass confirming both modes are fully themed; fill any gaps in
  `.mode-terminal` overrides (charts, popover, simulation result, dropdowns,
  focus rings, scrollbars, spinner color).

### Stage 4 — Spinners wired in

- Wire `Button loading` into each long-op call site, driven by existing
  pending/mutation state. Add panel-level dimming for the simulation if useful.

Stages 1–4 are independent enough to commit separately; Stage 0 lands first.

## Testing & verification

- Existing Vitest suites (auth, holdings, profile, portfolio, assistant, router,
  dashboard) must stay green; extend where a component contract changes
  (e.g. Button `loading`/`aria-busy`).
- Lint clean (ruff is backend; frontend uses its configured linter/build).
- Manual verification: run the app, view each surface in both modes at the three
  breakpoints, and exercise one long-op button to confirm the spinner.

## Non-goals

- No new color palette, gradients on primary surfaces, or spring/bounce motion.
- No re-architecture of the responsive system (no bottom-nav/drawer rebuild).
- No change to terminal-mode toggle behavior.
- No backend changes.
