# Portfolius Design System

> A long-term investor dashboard that shows you what you actually own — across markets, sectors, asset classes, and currencies — with an AI assistant grounded in your real numbers.

This design system encodes the visual and editorial identity of **Portfolius**, a pre-alpha personal-finance app for buy-and-hold ETF investors.

## Source materials

This system was derived from the public source repository. There is **no implemented frontend yet** — the codebase is a FastAPI backend skeleton plus architecture docs. Visual identity here was inferred from product copy, the intended tech stack (React + Vite + TypeScript + Tailwind + shadcn/ui + Recharts), and the brand name's Latin / classical-portfolio connotation.

- **GitHub:** https://github.com/Ronenii/Portfolius
- **Docs read:** `README.md`, `docs/architecture.md`, `docs/implementation/m0.md`
- **Tech stack signal:** React + Vite + TypeScript, Tailwind, shadcn/ui, Recharts, TanStack Query, FastAPI, Supabase, Groq LLM
- **Status quoted from repo:** "Hobby project · Pre-alpha"

If you have access to a later iteration of the repo, the frontend source under `frontend/src/` would be the source of truth — pull tokens from there and reconcile against this kit.

---

## Product context

Portfolius solves one repetitive task: rebalancing a long-term ETF portfolio without screenshotting your brokerage into ChatGPT every month.

The user enters their holdings once, declares their goals and preferred markets, and gets:

- **Multi-dimensional breakdowns** — the same portfolio sliced by geography, sector, asset class, or currency (not just by ticker).
- **An AI assistant pre-loaded with their context** — profile + holdings + goals — for grounded "what should I buy next?" analysis.

The audience is the **calm, deliberate investor**: someone who buys ETFs monthly, ignores the news cycle, and wants legible, honest information rather than gamified red-and-green confetti. The product is explicitly **not** a trading platform. The AI is explicitly **not** an advisor.

This shapes the entire design language: quiet, dense, ledger-like, slow. No hype green. No alarm red. No "buy now" copy.

## Products represented

The repo describes a single product surface today, with two clear contexts of use:

| Surface | Role | Visual mode |
|---|---|---|
| **Marketing / Profile / Assistant** | First-run, onboarding, AI chat | **Paper** — warm cream surfaces, serif display, generous whitespace |
| **Dashboard / Holdings** | Daily portfolio review | **Terminal** — deep ink background, teal highlights, monospace numerics |

Both modes share the same token system (teal accent, gain/loss semantics, type ramp) — they're two skins of one identity, not two products. The UI kit included here demonstrates both.

---

## Content fundamentals

The repository copy is **plain, declarative, lightly dry**. It tells you what something is and what it isn't, and respects the reader's time. The design system inherits that voice.

### Voice principles

- **Second person, never first.** "You enter your holdings", "your AI assistant", "you bought, when, and how much". Never "we" or "our". Portfolius is a tool, not a personality.
- **Declarative, present tense.** "Cuts out the screenshot loop." "Runs on a free tier." Not "will help you cut" or "is designed to run".
- **Short sentences. Em dashes earn their keep.** Long sentences split into two. Em dashes used for the one essential aside — like this — not for cleverness.
- **Concrete over abstract.** "Daily-close prices fetched automatically" instead of "real-time market data". Numbers (`$0/month`, `15 minutes`, `~30 seconds`) over adjectives ("affordable", "fast").
- **Honest disclaimers, in the same flat tone.** "It is **not financial advice**." Bolded for legal clarity, not theatrically.

### Casing

- **Sentence case everywhere.** "Profile setup", "Holdings tracking", "Multi-dimensional breakdowns". Not Title Case.
- **Product name capitalised mid-sentence**: "Portfolius cuts out the screenshot loop."
- **Feature names lowercase** when descriptive: "the assistant", "the dashboard", "the holdings page".

### Punctuation & rhythm

- **Em dash (—) for asides**, not parentheses where possible. From the repo: *"not just by ticker"*, *"no credit card required at any provider"*.
- **Colons for definitions**. *"Target cost: $0/month."*
- **Bold only for emphasis with weight**: dollar amounts, key constraints, legal copy. Never for "make this pop".
- **Bullet lists prefer noun-phrase parallel structure** ("Profile setup", "Holdings tracking", "Multi-dimensional breakdowns") — not full sentences.

### No-go

- **No emoji.** Not in product copy, not in commit messages, not in cards. (Unicode glyphs for currency `$ € £ ¥` and arrows `↑ ↓` are fine — they are typographic, not decorative.)
- **No exclamation marks.** Ever.
- **No "rocket fuel / supercharge / unlock"** marketing verbs.
- **No "AI-powered"** as an adjective. The assistant is a chat panel that has portfolio context — describe what it does.
- **No emojis like 📈📉💰** as iconography. Use teal arrows and the gain/loss color tokens.

### Examples (lifted and re-styled from the repo)

> Long-term investor dashboard. Shows you what you own by market exposure, sector, and asset class.

> The AI assistant produces educational observations grounded in your stated portfolio — it cannot place trades, does not know your full financial situation, and should not be treated as a substitute for a licensed advisor.

> Daily-close prices fetched automatically.

> Target cost: $0/month.

---

## Visual foundations

### The core idea

**A stoic ledger crossed with a modern terminal.** Portfolius treats a portfolio the way a 19th-century investor treated their book of holdings: as a thing reviewed slowly, with a clean hand, in a warm room. The product feels like a leather-bound ledger that happens to render in WebGL — quiet, considered, with weight.

The two modes are siblings, not opposites:

- **Paper** for surfaces a user lingers on (profile setup, AI chat, marketing): warm cream backgrounds, serif headlines, thin teal rules.
- **Terminal** for surfaces a user scans (dashboard, holdings table, charts): deep ink background, monospace numerals, teal highlights against the dark.

### Color

Two surface palettes, one shared accent + semantic set. **Teal** is the only chromatic accent — money-coded without celebrating gains, so the brand reads calm even on red days. **Gain** is a muted sage (not Robinhood green) clearly distinct from the teal accent; **bear** is terracotta (not alarm red) — both desaturated to read calm at a glance.

| Role | Token | Hex | Use |
|---|---|---|---|
| Paper bg | `--paper-50` | `#FAF8F2` | Page background, paper mode |
| Paper raised | `--paper-100` | `#F4F1E8` | Cards, panels on paper |
| Paper sunk | `--paper-200` | `#ECE7D7` | Inset wells, hover on paper |
| Ink terminal bg | `--ink-950` | `#0E1217` | Page background, terminal mode |
| Ink raised | `--ink-900` | `#161B22` | Cards on terminal |
| Ink hairline | `--ink-800` | `#222831` | Dividers on terminal |
| Foreground primary | `--ink-100` | `#1A1815` (paper) / `#EFEADC` (terminal) | Body text |
| Foreground secondary | `--ink-500` | `#6E6757` | Captions, table headers |
| Foreground muted | `--ink-300` | `#A39B86` | Disabled, placeholder |
| Rule | `--rule` | `#DDD7C8` | 1px dividers on paper |
| Accent primary | `--accent-500` | `#1F6B6E` | Accent, links, focus ring |
| Accent dark | `--accent-700` | `#114448` | Hover, pressed |
| Accent light | `--accent-300` | `#71A8AB` | Subtle highlights, terminal accents |
| Accent wash | `--accent-100` | `#D3E6E7` | Selected row, highlight cells |
| Gain | `--gain-500` | `#4F7A4A` | Positive deltas, gains |
| Gain wash | `--gain-100` | `#DBE6D3` | Heatmap-low, hover on gain |
| Loss | `--loss-500` | `#A8442C` | Negative deltas, losses |
| Loss wash | `--loss-100` | `#F0D5C8` | Heatmap-low, hover on loss |

See `colors_and_type.css` for the full token list.

### Type

A three-family stack chosen for ledger feel + screen legibility:

- **Display: Instrument Serif** — high-contrast serif, single weight, used for the wordmark, headlines, and section openers. Italic available for emphasis. Sets the "classical portfolio" tone.
- **Sans: Geist** — neutral grotesk for all UI: buttons, body, labels. Variable weight 300–700.
- **Mono: JetBrains Mono** — tabular numerals for every money amount, every percentage, every ticker. Numerics never live in a proportional font — that's a hard rule.

Display sets **tight** (line-height 1.05, letter-spacing -0.01em), body sets **comfortable** (1.55, 0em), mono sets **even** (1.4, 0em).

### Spacing

A 4-px base scale: `4, 8, 12, 16, 20, 24, 32, 40, 56, 72, 96`. Tokens are named by step (`--space-1` = 4px through `--space-11` = 96px). Cards typically use `--space-5` (20px) padding; page rails use `--space-8` (40px) on desktop.

### Radii

Conservative. **6px** is the default for buttons, inputs, and cards. **2px** for inline chips and badges. **999px** for filter pills. **0px** for table cells, dividers, and most marketing surfaces — the brand reads more confident with right angles than with friendly rounding.

### Borders, rules, dividers

- **Hairlines do the work that drop shadows do elsewhere.** A 1px `--rule` (paper) or `--ink-800` (terminal) divider replaces the shadow on most cards.
- Cards may have a single 1px border + zero shadow; or zero border + the subtle `--shadow-1` (see below). Never both — pick one.

### Shadow system

Used sparingly. Four steps; the brand's default state for most surfaces is **no shadow**.

- `--shadow-0` — none. Default.
- `--shadow-1` — `0 1px 2px rgba(20,18,12,0.06)` — quiet lift on paper.
- `--shadow-2` — `0 4px 16px -4px rgba(20,18,12,0.10), 0 1px 2px rgba(20,18,12,0.06)` — dropdowns, popovers.
- `--shadow-3` — `0 16px 40px -12px rgba(20,18,12,0.20), 0 2px 6px rgba(20,18,12,0.08)` — modals only.

Terminal mode uses **no shadow** — depth is signaled by `--ink-900` vs `--ink-950`, not lift.

### Transparency & blur

Used in exactly two places:

1. **Sticky table headers** — `backdrop-filter: blur(8px)` over `rgba(250,248,242,0.85)` (paper) or `rgba(14,18,23,0.85)` (terminal).
2. **Modal scrims** — `rgba(20,18,12,0.45)` flat, no blur.

Glassmorphism is not part of the brand.

### Backgrounds & textures

- **No gradients** for primary surfaces. Solid color only.
- **One permitted texture:** a very faint paper grain (`--texture-paper`, a 2% opacity noise SVG, optional) on hero / marketing surfaces. Off by default; opt in per surface.
- **No full-bleed photography by default.** If imagery is needed, it's a single muted document or chart graphic (b&w or duotone in teal) — never a stock photo of a person in a suit.
- **Charts** use the teal / gain / loss palette with `--ink-100` for axis text and `--rule` for gridlines. No rainbow palettes; categorical breakdowns use the teal scale + neutrals.

### Layout

- **12-column grid** on desktop, 28px gutters.
- **Page width caps at 1280px** for dashboards, 920px for reading surfaces (profile, marketing).
- **Sidebar nav is 220px**; collapses to 56px (icons only) at <1024px.
- **Header is 56px**, sticks on scroll with a 1px rule beneath it. No hero shadow.

### Animation

Quiet and consequential. Easings come from a single set; durations are short.

- `--ease-out`: `cubic-bezier(0.2, 0, 0, 1)` — most enters.
- `--ease-in`: `cubic-bezier(0.4, 0, 1, 1)` — exits.
- `--ease-standard`: `cubic-bezier(0.2, 0, 0.2, 1)` — UI transitions.
- Durations: **120ms** (hover/press), **200ms** (open/close), **320ms** (page-level). No 500ms+ flourishes.
- **No bounces, no springs, no parallax.** Things fade and slide a few pixels. The product is for slow investors; the motion respects that.
- Numeric values **count up / down** on update over 320ms with `--ease-standard`. This is the one "delight" the brand allows.

### Interaction states

- **Hover** (buttons, links): on paper, darken by ~6% or shift to `--accent-700`. On terminal, lighten ~6% or shift to `--accent-300`. Never opacity changes — opacity reads as "disabled".
- **Pressed**: solid fill darkens to `--accent-700`, plus 1px inset top shadow. No scale transforms.
- **Focus**: 2px `--accent-500` ring with a 2px transparent offset (Tailwind-style). Visible on keyboard only via `:focus-visible`.
- **Disabled**: 40% foreground opacity, no hover. (This is the one place opacity is used.)
- **Selected row** (tables): `--accent-100` fill, no border change.

### Cards

The default card:

```css
background: var(--paper-100);
border: 1px solid var(--rule);
border-radius: 6px;
padding: var(--space-5); /* 20px */
box-shadow: var(--shadow-0); /* none */
```

A **chart card** drops the border, uses `--shadow-1`, and adds a teal `border-top: 2px solid var(--accent-500)` only when the card represents the user's primary KPI (e.g. total portfolio value).

### Iconography

See [ICONOGRAPHY](#iconography) below.

---

## Iconography

### Strategy

The repo ships **no custom icon assets** — there is no frontend code yet. The intended stack is shadcn/ui, which pairs by default with **lucide-react**. This kit adopts **Lucide** as the primary icon set because (a) it is the shadcn default the repo would have used, and (b) its 1.5px-stroke, geometric-but-warm style matches the calm ledger feel.

Icons in this kit are loaded via the Lucide CDN as inline SVG:

```html
<i data-lucide="trending-up"></i>
<script src="https://unpkg.com/lucide@latest"></script>
<script>lucide.createIcons();</script>
```

### Rules

- **Stroke weight: 1.5px.** Default Lucide. Never bold or filled.
- **Size scale: 14, 16, 20, 24 px.** Default body icon: 16px. Inline-with-text icons: 14px. Section headers: 20px. Empty-state hero icons: 24px.
- **Color: `currentColor`.** Icons inherit text color so they recolor with teal / gain / loss semantics naturally.
- **No emoji.** Anywhere.
- **No unicode-glyph icons** except currency symbols (`$ € £ ¥ ₪`) and the arrows `↑ ↓ →` when used in inline tabular numerics (e.g. `↑ 2.4%`). For UI affordances (caret, chevron, close) use Lucide.

### The Portfolius wordmark

A simple type-set wordmark in **Instrument Serif**, lowercase, with a teal dot at the end — `portfolius.` — read as a period that holds the brand color. Two lockups:

- **Wordmark + dot** — `portfolius.` for headers, marketing.
- **Glyph only** — a serif `p` + trailing teal dot, set in a 32×32 surface for favicons, app icons, terminal compact mode.

See `assets/portfolius-wordmark.svg` and `assets/portfolius-glyph.svg`.

### Specific icon vocabulary

The product uses a tight set. Keep new screens within this vocabulary unless absolutely necessary:

| Concept | Lucide name |
|---|---|
| Portfolio / dashboard | `layout-dashboard` |
| Holdings | `landmark` |
| Profile | `user-round` |
| AI assistant | `sparkles` |
| Settings | `settings-2` |
| Add holding | `plus` |
| Edit | `pencil` |
| Delete | `trash-2` |
| Filter | `sliders-horizontal` |
| Search | `search` |
| Calendar / date | `calendar-days` |
| Sort | `arrow-up-down` |
| Gain / up | `trending-up` |
| Loss / down | `trending-down` |
| Region / geography | `globe` |
| Sector | `pie-chart` |
| Asset class | `layers` |
| Currency | `coins` |
| External link | `arrow-up-right` |
| Info | `info` |
| Help | `help-circle` |

---

## Index

Files in this design system:

| Path | What's in it |
|---|---|
| `README.md` | This document — product context, content + visual foundations, iconography |
| `SKILL.md` | Agent-compatible skill manifest for invoking this system in Claude Code |
| `colors_and_type.css` | All CSS custom properties — colors, type, spacing, radii, shadows, motion |
| `assets/` | Wordmark, glyph, brand marks (SVG) |
| `preview/` | Per-token preview cards rendered in the Design System tab |
| `ui_kits/web/` | Interactive HTML + JSX recreation of the Portfolius web app |
| `ui_kits/web/README.md` | What's in the UI kit, how to extend it |

The UI kit ships with **6 alternative accent palettes** (Teal, Forest, Brass, Sky, Ink, Claret, Slate) selectable via Tweaks — the chosen direction is Teal, but the others remain available for future iteration.

### Caveats — read these

- **The repo has no frontend code.** Every visual decision here is an inference from product copy, stack signals, and the brand name. Treat this as a strong opening proposal, not a documentation of existing code.
- **Fonts are loaded from Google Fonts** (Instrument Serif, Geist, JetBrains Mono), not the repo. If the team picks different fonts when they actually build the frontend, swap the `@font-face` block in `colors_and_type.css`. No local `fonts/` folder is shipped — Google Fonts handles delivery.
- **Icons substitute Lucide** because that's the shadcn/ui default. If the team ships with a different set (Heroicons, Phosphor, custom), swap the icon strategy section.
- **Accent palette is iterable.** Teal is the chosen direction; the UI kit's Tweaks panel ships with five alternatives so future explorations don't require a code change.
- **Want to extend this?** Explore the source repository: https://github.com/Ronenii/Portfolius — when the frontend exists, reconcile this kit against it.
