# UI Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish Portfolius across responsive layout, terminal mode completeness, button loading states, and body-text de-graying — all within the existing brand.

**Architecture:** All changes are CSS-first (`frontend/src/index.css`) plus targeted TSX edits; no new libraries. The shared `Button` component gets a `loading` prop that propagates to every async call site via a single interface change.

**Tech Stack:** React 18 + Vite + TypeScript, plain CSS custom properties, Vitest + @testing-library/react

---

## Already done (do not re-implement)

- Composition breakdown stacks to 1 column at ≤560px (`index.css`)
- Terminal mode `color-scheme: dark` on `<html>` via `app-root--terminal` class (`AppShell.tsx`, `index.css`)
- Polished webkit scrollbars for `.mode-terminal` in `index.css`
- `AuthLoading` and `ProfileLoading` use `.loading-screen` (fills content-rail, centered)

---

## File map

| File | What changes |
|---|---|
| `frontend/src/components/ui/Button.tsx` | Add `loading` prop; show spinner, set `aria-busy`, force disabled |
| `frontend/src/components/ui/Button.test.tsx` | New — unit tests for `loading` prop |
| `frontend/src/index.css` | Spinner keyframe + `.button__spinner`; terminal `.simulation-warnings` fix; table cell text promotion; any remaining responsive fixes |
| `frontend/src/pages/DashboardPage.tsx` | Migrate raw `<button>` → `<Button>` for refresh; pass `loading` |
| `frontend/src/features/holdings/HoldingsPage.tsx` | Pass `loading={isSaving}` to save button |
| `frontend/src/features/portfolio/SimulationPanel.tsx` | Pass `loading={simulateMutation.isPending}` to simulate button |
| `frontend/src/features/profile/ProfileEditPage.tsx` | Pass `loading={saveMutation.isPending}` to save button |
| `frontend/src/features/profile/ProfileWizardPage.tsx` | Pass `loading={saveMutation.isPending}` to save button |
| `frontend/src/features/auth/LoginPage.tsx` | Add `isSending` state; pass `loading={isSending}` to magic link button |

---

## Task 1: Button `loading` primitive — test first

**Files:**
- Create: `frontend/src/components/ui/Button.test.tsx`
- Modify: `frontend/src/components/ui/Button.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1.1 — Write failing tests**

Create `frontend/src/components/ui/Button.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Button from "./Button";

describe("Button", () => {
  it("renders children normally", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("is not disabled and has no spinner by default", () => {
    render(<Button>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn).not.toBeDisabled();
    expect(btn).not.toHaveAttribute("aria-busy");
    expect(btn.querySelector(".button__spinner")).toBeNull();
  });

  it("when loading=true: sets aria-busy, disables, shows spinner", () => {
    render(<Button loading>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-busy", "true");
    expect(btn).toBeDisabled();
    expect(btn.querySelector(".button__spinner")).not.toBeNull();
  });

  it("when loading=true: hides icon and shows spinner instead", () => {
    const FakeIcon = () => <svg data-testid="icon" />;
    render(<Button loading icon={FakeIcon}>Save</Button>);
    const btn = screen.getByRole("button");
    expect(btn.querySelector("[data-testid='icon']")).toBeNull();
    expect(btn.querySelector(".button__spinner")).not.toBeNull();
  });

  it("when loading=false and icon provided: shows icon, no spinner", () => {
    const FakeIcon = () => <svg data-testid="icon" />;
    render(<Button icon={FakeIcon}>Save</Button>);
    const btn = screen.getByRole("button");
    expect(screen.getByTestId("icon")).toBeInTheDocument();
    expect(btn.querySelector(".button__spinner")).toBeNull();
  });

  it("disabled prop still disables without loading", () => {
    render(<Button disabled>Save</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

- [ ] **Step 1.2 — Run tests; confirm they fail**

```bash
cd frontend && npm run test -- --reporter=verbose src/components/ui/Button.test.tsx
```

Expected: multiple FAIL ("Button.test.tsx" not found or "loading" prop not recognised)

- [ ] **Step 1.3 — Add `loading` prop to `Button.tsx`**

Replace the entire content of `frontend/src/components/ui/Button.tsx`:

```tsx
import type { ButtonHTMLAttributes, ComponentType, SVGProps } from "react";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: IconComponent;
  loading?: boolean;
  variant?: "primary" | "secondary" | "ghost";
};

export default function Button({
  children,
  className = "",
  disabled,
  icon: Icon,
  loading = false,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      aria-busy={loading ? true : undefined}
      className={`button button--${variant} ${className}`.trim()}
      disabled={disabled || loading}
      type={type}
      {...props}
    >
      {loading
        ? <span aria-hidden="true" className="button__spinner" />
        : Icon
          ? <Icon aria-hidden="true" />
          : null}
      {children}
    </button>
  );
}
```

- [ ] **Step 1.4 — Add spinner CSS to `index.css`**

Insert after the `.button--ghost:hover:not(:disabled)` block (around line 1755):

```css
/* ---- Button loading spinner -------------------------------------------- */
@keyframes button-spin {
  to { transform: rotate(360deg); }
}

.button__spinner {
  display: inline-block;
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: button-spin 0.6s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .button__spinner {
    animation: none;
    opacity: 0.5;
  }
}
```

- [ ] **Step 1.5 — Run tests; confirm they pass**

```bash
cd frontend && npm run test -- --reporter=verbose src/components/ui/Button.test.tsx
```

Expected: 6 tests PASS

- [ ] **Step 1.6 — Full suite still green**

```bash
cd frontend && npm run test 2>&1 | tail -6
```

Expected: `Test Files  11 passed`, `Tests  83 passed` (77 existing + 6 new)

- [ ] **Step 1.7 — Commit**

```bash
cd frontend && git add src/components/ui/Button.tsx src/components/ui/Button.test.tsx src/index.css
git commit -m "feat: add loading prop with inline spinner to Button component"
```

---

## Task 2: Terminal mode — fix simulation warnings

**Files:**
- Modify: `frontend/src/index.css`

The `.simulation-warnings` element has `color: var(--ink-700)` and a light teal background tint — both are invisible/unreadable on the dark `--ink-900` panel background in terminal mode.

- [ ] **Step 2.1 — Add terminal override for simulation warnings**

Find the `.mode-terminal .simulation-panel` rule (around line 1197) and add immediately after it:

```css
.mode-terminal .simulation-warnings {
  border-color: color-mix(in srgb, var(--accent-300) 28%, transparent);
  border-left-color: var(--accent-300);
  background: color-mix(in srgb, var(--accent-300) 10%, transparent);
  color: var(--ink-200);
}
```

- [ ] **Step 2.2 — Build to confirm no CSS errors**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ built in ...`

- [ ] **Step 2.3 — Commit**

```bash
git add frontend/src/index.css
git commit -m "fix: theme simulation warnings panel for terminal mode"
```

---

## Task 3: Modernization — promote table body text from gray to foreground

**Files:**
- Modify: `frontend/src/index.css`

Currently `.allocation-table td` and `.holdings-table td` (non-first-child) use `color: var(--ink-700)` (#3B362B — a medium warm gray). Primary data cells should use `--fg-paper`/`--fg-terminal` for legibility; only column headers and truly secondary metadata should stay at `--ink-500`.

- [ ] **Step 3.1 — Promote allocation table data cells**

Find and replace:

```css
.allocation-table td {
  color: var(--ink-700);
}
```

with:

```css
.allocation-table td {
  color: var(--fg-paper);
}
```

- [ ] **Step 3.2 — Promote holdings table data cells**

Find and replace:

```css
.holdings-table td {
  color: var(--ink-700);
}
```

with:

```css
.holdings-table td {
  color: var(--fg-paper);
}
```

- [ ] **Step 3.3 — Update terminal overrides for both tables**

The existing terminal overrides for these tables set `color: var(--ink-200)`:

```css
.mode-terminal .allocation-table td {
  color: var(--ink-200);
  border-bottom-color: var(--ink-800);
}
```

and:

```css
.mode-terminal .holdings-table td {
  color: var(--ink-200);
  border-bottom-color: var(--ink-800);
}
```

These are already present and still correct (`--ink-200` is the right terminal body text tone). No change needed — verify they exist in the file and leave them as-is.

- [ ] **Step 3.4 — Build and run full test suite**

```bash
cd frontend && npm run build 2>&1 | tail -5 && npm run test 2>&1 | tail -6
```

Expected: build ✓, 83 tests pass

- [ ] **Step 3.5 — Commit**

```bash
git add frontend/src/index.css
git commit -m "style: promote table body text to fg token, reduce ink-700 gray"
```

---

## Task 4: Wire `loading` into async call sites

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/features/holdings/HoldingsPage.tsx`
- Modify: `frontend/src/features/portfolio/SimulationPanel.tsx`
- Modify: `frontend/src/features/profile/ProfileEditPage.tsx`
- Modify: `frontend/src/features/profile/ProfileWizardPage.tsx`
- Modify: `frontend/src/features/auth/LoginPage.tsx`

### 4a — DashboardPage: refresh prices button

The refresh button is currently a raw `<button>` with hand-applied classes. Migrate to the shared `Button` component.

- [ ] **Step 4a.1 — Add Button import to DashboardPage.tsx**

Add to the imports at the top of `frontend/src/pages/DashboardPage.tsx`:

```tsx
import Button from "../components/ui/Button";
```

- [ ] **Step 4a.2 — Replace the raw refresh button**

Find:

```tsx
        <button
          className="button button--primary"
          disabled={!accessToken || refreshMutation.isPending}
          type="button"
          onClick={() => refreshMutation.mutate()}
        >
          <RefreshCw aria-hidden="true" />
          {refreshMutation.isPending ? "Refreshing" : "Refresh prices"}
        </button>
```

Replace with:

```tsx
        <Button
          disabled={!accessToken}
          icon={RefreshCw}
          loading={refreshMutation.isPending}
          type="button"
          onClick={() => refreshMutation.mutate()}
        >
          {refreshMutation.isPending ? "Refreshing" : "Refresh prices"}
        </Button>
```

### 4b — HoldingsPage: save holding button

The `isSaving` variable already exists (`createMutation.isPending || updateMutation.isPending`).

- [ ] **Step 4b.1 — Pass `loading` to the save button**

Find in `frontend/src/features/holdings/HoldingsPage.tsx`:

```tsx
              <Button disabled={isSaving} icon={Plus} type="submit">
                {isSaving ? "Saving holding" : "Save holding"}
              </Button>
```

Replace with:

```tsx
              <Button icon={Plus} loading={isSaving} type="submit">
                {isSaving ? "Saving holding" : "Save holding"}
              </Button>
```

### 4c — SimulationPanel: simulate button

- [ ] **Step 4c.1 — Pass `loading` to the simulate button**

Find in `frontend/src/features/portfolio/SimulationPanel.tsx`:

```tsx
      <Button
        disabled={legs.length === 0 || simulateMutation.isPending}
        type="button"
        variant="primary"
        onClick={() => simulateMutation.mutate(legs)}
      >
        {simulateMutation.isPending ? "Simulating" : "Simulate"}
      </Button>
```

Replace with:

```tsx
      <Button
        disabled={legs.length === 0}
        loading={simulateMutation.isPending}
        type="button"
        variant="primary"
        onClick={() => simulateMutation.mutate(legs)}
      >
        {simulateMutation.isPending ? "Simulating" : "Simulate"}
      </Button>
```

### 4d — ProfileEditPage: save changes button

- [ ] **Step 4d.1 — Pass `loading` to save button**

Find in `frontend/src/features/profile/ProfileEditPage.tsx` (inside `ProfileEditForm`):

```tsx
          disabled={saveMutation.isPending}
          icon={Save}
```

Replace with:

```tsx
          loading={saveMutation.isPending}
          icon={Save}
```

(Remove the `disabled` line — `loading` already forces disabled.)

### 4e — ProfileWizardPage: save profile button

- [ ] **Step 4e.1 — Pass `loading` to save button**

Find in `frontend/src/features/profile/ProfileWizardPage.tsx`:

```tsx
          <Button
            disabled={saveMutation.isPending}
            icon={Save}
```

Replace with:

```tsx
          <Button
            loading={saveMutation.isPending}
            icon={Save}
```

### 4f — LoginPage: magic link button

The LoginPage has no pending state. Add one.

- [ ] **Step 4f.1 — Add `isSending` state**

In `frontend/src/features/auth/LoginPage.tsx`, change:

```tsx
export default function LoginPage() {
  const { signInWithGoogle, signInWithMagicLink } = useAuth();
  const [email, setEmail] = useState("");

  const canSubmit = useMemo(() => isValidEmail(email), [email]);

  async function handleMagicLinkSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    await signInWithMagicLink(email);
  }
```

to:

```tsx
export default function LoginPage() {
  const { signInWithGoogle, signInWithMagicLink } = useAuth();
  const [email, setEmail] = useState("");
  const [isSending, setIsSending] = useState(false);

  const canSubmit = useMemo(() => isValidEmail(email), [email]);

  async function handleMagicLinkSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setIsSending(true);
    try {
      await signInWithMagicLink(email);
    } finally {
      setIsSending(false);
    }
  }
```

- [ ] **Step 4f.2 — Pass `loading` to the magic link button**

Find:

```tsx
          <Button disabled={!canSubmit} icon={Mail} type="submit" variant="secondary">
            Send magic link
          </Button>
```

Replace with:

```tsx
          <Button
            disabled={!canSubmit}
            icon={Mail}
            loading={isSending}
            type="submit"
            variant="secondary"
          >
            Send magic link
          </Button>
```

### 4g — Verify and commit

- [ ] **Step 4g.1 — Build clean**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `✓ built in ...`

- [ ] **Step 4g.2 — Full test suite**

```bash
cd frontend && npm run test 2>&1 | tail -6
```

Expected: 83 tests pass

- [ ] **Step 4g.3 — Lint**

```bash
cd frontend && npm run lint 2>&1
```

Expected: no output (clean)

- [ ] **Step 4g.4 — Commit**

```bash
git add \
  frontend/src/pages/DashboardPage.tsx \
  frontend/src/features/holdings/HoldingsPage.tsx \
  frontend/src/features/portfolio/SimulationPanel.tsx \
  frontend/src/features/profile/ProfileEditPage.tsx \
  frontend/src/features/profile/ProfileWizardPage.tsx \
  frontend/src/features/auth/LoginPage.tsx
git commit -m "feat: wire Button loading state into all async call sites"
```

---

## Task 5: Responsive — validate and fix remaining 860/560 gaps

**Files:**
- Modify: `frontend/src/index.css` (only if gaps found)

- [ ] **Step 5.1 — Start dev server**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` in a browser.

- [ ] **Step 5.2 — Check Dashboard at 860px (tablet breakpoint)**

Resize to 860px width. Verify:
- Sidebar becomes a horizontal top bar with 4 nav items in a row — icon + label both visible
- KPI grid is 2 columns
- Allocation controls (6 dimension buttons + 3 chart type buttons) wrap cleanly without overflow
- Status strip collapses to 2 columns without horizontal scroll
- `Refresh prices` button fits in the page-header flex row without overflow

If the dimension segmented-control overflows (≥7 buttons × ~70px min = ~490px in a potentially narrow container), add to the 860px media query in `index.css`:

```css
@media (max-width: 860px) {
  /* existing rules ... */
  
  .allocation-controls {
    flex-direction: column;
    align-items: flex-start;
  }
}
```

- [ ] **Step 5.3 — Check Dashboard at 375px (mobile)**

Resize to 375px. Verify:
- KPI grid is 1 column
- Nav links show icon only (text hides at 560px)
- Allocation table rows reflow to label-value pairs (thead hidden, `data-label` pseudo-content)
- Composition popover fits (stacks to 1 column — fixed in prior task)

- [ ] **Step 5.4 — Check Holdings at 375px**

Verify:
- Holdings table reflows to stacked rows (thead hidden)
- Add holding form stacks to 1 column
- Instrument search dropdown fits within viewport

- [ ] **Step 5.5 — Check Profile wizard at 375px**

Verify:
- Form is 1 column
- Choice option tiles wrap cleanly
- Keyword entry chips wrap without overflow

- [ ] **Step 5.6 — Check terminal mode at 375px**

Toggle terminal mode. Verify:
- All surfaces adapt (dark bg, teal accents, no paper surfaces visible)
- Scrollbars on tables/assistant use dark theme
- Number inputs / selects use browser dark chrome (from `color-scheme: dark`)

- [ ] **Step 5.7 — Fix any gaps found, build + test**

For each gap, make the minimum targeted CSS addition to `index.css` in the appropriate media-query block.

```bash
cd frontend && npm run build 2>&1 | tail -5 && npm run test 2>&1 | tail -6
```

Expected: build ✓, 83 tests pass

- [ ] **Step 5.8 — Commit (even if no changes)**

```bash
git add frontend/src/index.css
git commit -m "fix: responsive audit pass — 860/560 breakpoint fixes" --allow-empty
```

---

## Final verification

- [ ] All 83 tests pass: `cd frontend && npm run test`
- [ ] Build clean: `cd frontend && npm run build`
- [ ] Lint clean: `cd frontend && npm run lint`
- [ ] Visual check: paper mode + terminal mode at 375 / 860 / desktop
- [ ] Spinner appears on: refresh prices, save holding, simulate, save profile, save profile wizard, send magic link
