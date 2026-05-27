---
name: portfolius-design
description: Use this skill to generate well-branded interfaces and assets for Portfolius — a long-term investor dashboard — either for production or throwaway prototypes/mocks. Contains essential design guidelines, colors, type, fonts, brand assets, and UI kit components for prototyping.
user-invocable: true
---

# Portfolius Design Skill

Portfolius is a long-term investor dashboard. The brand is **a stoic ledger crossed with a modern terminal**: warm cream paper surfaces for surfaces a user lingers on (profile, AI chat, marketing), and deep ink terminal surfaces for surfaces a user scans (dashboard, holdings table). One accent — **Teal** — money-coded without celebrating gains, so the brand reads calm even on red days.

## Start here

1. Read `README.md` — the full system: content fundamentals, visual foundations, iconography, file index.
2. Read `colors_and_type.css` — every token (`--accent-*`, `--paper-*`, `--ink-*`, `--gain-*`, `--loss-*`, type ramp, spacing, motion).
3. Open `preview/` cards — visual specimens for every concept (cards, buttons, tables, KPI tiles, donut, voice, accent options).
4. Open `ui_kits/web/index.html` — interactive Portfolius app with paper/terminal modes and live accent-palette switching.

## When creating visual artifacts (slides, mocks, prototypes)

- Copy assets out of `assets/` (wordmarks, glyphs) rather than rebuilding them.
- Link `colors_and_type.css` into your HTML; never hand-pick hex values.
- Use **Instrument Serif** for display, **Geist** for UI, **JetBrains Mono** for every numeric (money, percentage, ticker).
- Default to Paper mode. Use Terminal mode only for data-dense scanning surfaces.
- One chromatic accent: teal. Gain/loss semantics are muted sage and terracotta, both desaturated.
- No emoji. No gradients on primary surfaces. No bouncy animations.

## When working in production code

- Read `ui_kits/web/components.jsx` and `screens.jsx` for the component API shapes (Button, Field, Badge, CardPanel, KpiTile, Donut, Sidebar, Header).
- Tokens live in `colors_and_type.css`. Match them in your `tailwind.config.ts` or theme module.
- The kit is shadcn-compatible by intent (variant prop, primary/secondary/ghost) but doesn't depend on shadcn directly.

## If invoked without specific guidance

Ask the user what they want to build or design (a screen, a slide, a marketing page, a feature mock), ask 2–3 focused questions about audience and scope, then deliver as an HTML artifact or production-ready component.
