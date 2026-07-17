# Expected Annual Return Static Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the "Expected annual return" slider from the goal projection panel (it's misleading now that the value is always computed from real holdings, not a manual guess) and replace it with a non-editable value plus a hover/focus tooltip explaining how it's derived.

**Architecture:** The backend's `annual_return` override capability (query param → service parameter) is removed entirely, since nothing but this one slider used it — once it's gone, `ProjectionResponse.annual_return_expected` is always the computed baseline. The frontend drops the slider's state/effects/JSX and renders that value as plain text next to a new reusable `InfoTooltip` component (a `?` button whose disclaimer is shown via CSS `:hover`/`:focus-visible`, no JS-driven visibility state).

**Tech Stack:** FastAPI (backend query param removal), React + TypeScript (frontend), Vitest + Testing Library (tests), plain CSS (no new dependencies for the tooltip).

## Global Constraints

- The `annual_return` override capability is removed entirely — the FastAPI query param, the `build_projection_for_user` parameter, and all frontend override plumbing (type, state, query key, JSX). Not just hidden in the UI.
- `ProjectionResponse`'s shape is unchanged — no new/removed fields. `annual_return_expected` simply becomes always-the-computed-value once the override path is gone.
- The new static display must be genuinely non-editable: no slider/input `role` for annual return anywhere in the DOM.
- `InfoTooltip`'s show/hide is CSS-only (`:hover`/`:focus-visible` on the trigger revealing an adjacent sibling) — no JS state for visibility. It must be keyboard-accessible (revealed on focus, not just mouse hover) and associate its disclaimer text to the trigger via `aria-describedby`.
- Disclaimer copy (exact, user-approved): `Estimated from your current holdings — a weighted average of each holding's 5-year historical return, or a broad asset-class estimate where history isn't available yet.`
- The contribution-amount slider and the horizon selector are unaffected — both remain fully interactive overrides.

---

### Task 1: Remove the `annual_return` override (backend)

**Files:**
- Modify: `backend/app/api/v1/portfolio.py`
- Modify: `backend/app/domain/portfolio_service.py`
- Modify: `backend/tests/test_projection_api.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `build_projection_for_user`'s signature drops `annual_return` — nothing later depends on it (this is the only task touching the backend).

- [ ] **Step 1: Update the test that exercises the override**

In `backend/tests/test_projection_api.py`, find:

```python
def test_projection_overrides_take_precedence_over_profile_values(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        goal_target_amount="50000",
        contribution_amount="200",
    )

    response = read_portfolio_projection(
        authenticated_user,
        db_session,
        target=Decimal("90000"),
        contribution=Decimal("500"),
        annual_return=Decimal("10"),
        years=20,
    )

    assert response.target_amount == Decimal("90000")
    assert response.contribution_amount == Decimal("500")
    assert response.annual_return_expected == Decimal("10")
    assert response.horizon_years == 20
```

Replace with (drops the `annual_return` override — the remaining `target`/`contribution`/`years` overrides still prove precedence-over-profile-values):

```python
def test_projection_overrides_take_precedence_over_profile_values(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        goal_target_amount="50000",
        contribution_amount="200",
    )

    response = read_portfolio_projection(
        authenticated_user,
        db_session,
        target=Decimal("90000"),
        contribution=Decimal("500"),
        years=20,
    )

    assert response.target_amount == Decimal("90000")
    assert response.contribution_amount == Decimal("500")
    assert response.horizon_years == 20
```

- [ ] **Step 2: Remove the query param from the endpoint**

In `backend/app/api/v1/portfolio.py`, find:

```python
@router.get("/api/v1/portfolio/projection", response_model=ProjectionResponse)
def read_portfolio_projection(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Decimal | None = None,
    contribution: Decimal | None = None,
    annual_return: Decimal | None = None,
    years: int | None = None,
) -> ProjectionResponse:
```

Replace with:

```python
@router.get("/api/v1/portfolio/projection", response_model=ProjectionResponse)
def read_portfolio_projection(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    target: Decimal | None = None,
    contribution: Decimal | None = None,
    years: int | None = None,
) -> ProjectionResponse:
```

Find:

```python
    return build_projection_for_user(
        db,
        current_user.user_id,
        target=target,
        contribution=contribution,
        annual_return=annual_return,
        years=years,
    )
```

Replace with:

```python
    return build_projection_for_user(
        db,
        current_user.user_id,
        target=target,
        contribution=contribution,
        years=years,
    )
```

- [ ] **Step 3: Remove the parameter and resolution branch from the service function**

In `backend/app/domain/portfolio_service.py`, find:

```python
def build_projection_for_user(
    db: Session,
    user_id: str,
    *,
    target: Decimal | None = None,
    contribution: Decimal | None = None,
    annual_return: Decimal | None = None,
    years: int | None = None,
) -> ProjectionResponse:
    profile = get_profile_by_user_id(db, user_id)
    if profile is None:
        raise profile_not_found()

    snapshot = build_snapshot_for_user(db, user_id)

    resolved_target = target if target is not None else profile.goal_target_amount
    resolved_contribution = (
        contribution if contribution is not None else profile.contribution_amount
    )

    if annual_return is not None:
        resolved_annual_return = annual_return
    else:
        computed_return = compute_weighted_average_return(
            snapshot.holdings, snapshot.summary.base_currency
        )
        resolved_annual_return = (
            computed_return
            if computed_return is not None
            else RISK_TOLERANCE_DEFAULT_RETURN.get(
                profile.risk_tolerance, DEFAULT_ANNUAL_RETURN
            )
        )
```

Replace with:

```python
def build_projection_for_user(
    db: Session,
    user_id: str,
    *,
    target: Decimal | None = None,
    contribution: Decimal | None = None,
    years: int | None = None,
) -> ProjectionResponse:
    profile = get_profile_by_user_id(db, user_id)
    if profile is None:
        raise profile_not_found()

    snapshot = build_snapshot_for_user(db, user_id)

    resolved_target = target if target is not None else profile.goal_target_amount
    resolved_contribution = (
        contribution if contribution is not None else profile.contribution_amount
    )

    computed_return = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )
    resolved_annual_return = (
        computed_return
        if computed_return is not None
        else RISK_TOLERANCE_DEFAULT_RETURN.get(
            profile.risk_tolerance, DEFAULT_ANNUAL_RETURN
        )
    )
```

- [ ] **Step 4: Run the full backend suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing (no test outside `test_projection_api.py` references `annual_return=` as a kwarg to `read_portfolio_projection`/`build_projection_for_user`, so nothing else should be affected).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/portfolio.py backend/app/domain/portfolio_service.py backend/tests/test_projection_api.py
git commit -m "feat: remove the annual-return override from the projection endpoint"
```

---

### Task 2: Remove the `annualReturn` override (frontend API layer)

**Files:**
- Modify: `frontend/src/features/portfolio/portfolio-api.ts`
- Modify: `frontend/src/features/portfolio/portfolio.test.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: `ProjectionOverrides` type without `annualReturn` — Task 4's `ProjectionPanel` consumes this type and must not reference `annualReturn` after this task lands.

- [ ] **Step 1: Update the test that exercises the override**

In `frontend/src/features/portfolio/portfolio.test.tsx`, find:

```tsx
  it("requests the projection with query overrides", async () => {
    const projection = {
      base_currency: "USD",
      start_value: "1000",
      target_amount: "50000",
      horizon_years: 3,
      contribution_amount: "100",
      contribution_frequency: "monthly",
      annual_return_expected: "5",
      series: [],
      target_progress_percent: "2",
      on_track: true,
      target_reached_year: 3,
    };
    vi.mocked(apiRequest).mockResolvedValue(projection);

    await expect(
      getProjection("access-token", {
        target: "50000",
        contribution: "100",
        annualReturn: "5",
        years: 3,
      })
    ).resolves.toEqual(projection);

    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/portfolio/projection?target=50000&contribution=100&annual_return=5&years=3",
      { accessToken: "access-token" }
    );
```

Replace with:

```tsx
  it("requests the projection with query overrides", async () => {
    const projection = {
      base_currency: "USD",
      start_value: "1000",
      target_amount: "50000",
      horizon_years: 3,
      contribution_amount: "100",
      contribution_frequency: "monthly",
      annual_return_expected: "5",
      series: [],
      target_progress_percent: "2",
      on_track: true,
      target_reached_year: 3,
    };
    vi.mocked(apiRequest).mockResolvedValue(projection);

    await expect(
      getProjection("access-token", {
        target: "50000",
        contribution: "100",
        years: 3,
      })
    ).resolves.toEqual(projection);

    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/portfolio/projection?target=50000&contribution=100&years=3",
      { accessToken: "access-token" }
    );
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- portfolio.test -v`
Expected: FAIL — the mocked call no longer matches (`getProjection` still sends `annual_return=5` in the query string because `overrides.annualReturn` is still read).

- [ ] **Step 3: Remove `annualReturn` from the type and the query-building logic**

In `frontend/src/features/portfolio/portfolio-api.ts`, find:

```ts
export type ProjectionOverrides = {
  target?: string;
  contribution?: string;
  annualReturn?: string;
  years?: number;
};
```

Replace with:

```ts
export type ProjectionOverrides = {
  target?: string;
  contribution?: string;
  years?: number;
};
```

Find:

```ts
  const params = new URLSearchParams();
  if (overrides.target !== undefined) params.set("target", overrides.target);
  if (overrides.contribution !== undefined)
    params.set("contribution", overrides.contribution);
  if (overrides.annualReturn !== undefined)
    params.set("annual_return", overrides.annualReturn);
  if (overrides.years !== undefined)
    params.set("years", String(overrides.years));
```

Replace with:

```ts
  const params = new URLSearchParams();
  if (overrides.target !== undefined) params.set("target", overrides.target);
  if (overrides.contribution !== undefined)
    params.set("contribution", overrides.contribution);
  if (overrides.years !== undefined)
    params.set("years", String(overrides.years));
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npm test -- portfolio.test -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Run the full frontend suite, lint, and build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all clean/passing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/portfolio/portfolio-api.ts frontend/src/features/portfolio/portfolio.test.tsx
git commit -m "feat: remove the annualReturn override from the projection API client"
```

---

### Task 3: `InfoTooltip` component

**Files:**
- Create: `frontend/src/components/ui/InfoTooltip.tsx`
- Create: `frontend/src/components/ui/InfoTooltip.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: nothing new.
- Produces: `InfoTooltip({ text: string, children: ReactNode })` — a named export from `frontend/src/components/ui/InfoTooltip.tsx`. Task 4 imports and renders it as `<InfoTooltip text="...">?</InfoTooltip>`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ui/InfoTooltip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InfoTooltip } from "./InfoTooltip";

describe("InfoTooltip", () => {
  it("renders a trigger labeled for how the value is calculated", () => {
    render(<InfoTooltip text="Some explanation.">?</InfoTooltip>);

    expect(
      screen.getByRole("button", { name: "How is this calculated?" })
    ).toBeInTheDocument();
  });

  it("renders the trigger's children as its visible content", () => {
    render(<InfoTooltip text="Some explanation.">?</InfoTooltip>);

    expect(
      screen.getByRole("button", { name: "How is this calculated?" })
    ).toHaveTextContent("?");
  });

  it("associates the disclaimer text with the trigger via aria-describedby", () => {
    render(<InfoTooltip text="Some explanation.">?</InfoTooltip>);

    const trigger = screen.getByRole("button", {
      name: "How is this calculated?",
    });
    const describedById = trigger.getAttribute("aria-describedby");

    expect(describedById).toBeTruthy();
    expect(
      document.getElementById(describedById as string)
    ).toHaveTextContent("Some explanation.");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- InfoTooltip -v`
Expected: FAIL — `Cannot find module './InfoTooltip'` (the component doesn't exist yet).

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/ui/InfoTooltip.tsx`:

```tsx
import { useId, type ReactNode } from "react";

type InfoTooltipProps = {
  text: string;
  children: ReactNode;
};

export function InfoTooltip({ text, children }: InfoTooltipProps) {
  const tooltipId = useId();

  return (
    <span className="info-tooltip">
      <button
        aria-describedby={tooltipId}
        aria-label="How is this calculated?"
        className="info-tooltip-trigger"
        type="button"
      >
        {children}
      </button>
      <span className="info-tooltip-bubble" id={tooltipId} role="tooltip">
        {text}
      </span>
    </span>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- InfoTooltip -v`
Expected: PASS (all 3 tests).

- [ ] **Step 5: Add the CSS**

In `frontend/src/index.css`, find:

```css
.mode-terminal .projection-reset {
  color: var(--accent-300);
}
```

Replace with (adds the new tooltip styles right after the existing projection-panel block, following the same `.mode-terminal` override convention used throughout this file):

```css
.mode-terminal .projection-reset {
  color: var(--accent-300);
}

.info-tooltip {
  position: relative;
  display: inline-flex;
}

.info-tooltip-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: 1px solid var(--rule);
  border-radius: 50%;
  background: none;
  color: var(--ink-600);
  font-size: 11px;
  line-height: 1;
  cursor: help;
}

.info-tooltip-bubble {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  z-index: 10;
  width: max-content;
  max-width: 240px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--ink-900);
  color: var(--paper-50);
  font-size: 12px;
  line-height: 1.4;
  opacity: 0;
  pointer-events: none;
  transform: translateX(-50%);
  transition: opacity 120ms ease;
}

.info-tooltip-trigger:hover + .info-tooltip-bubble,
.info-tooltip-trigger:focus-visible + .info-tooltip-bubble {
  opacity: 1;
}

.mode-terminal .info-tooltip-trigger {
  border-color: var(--ink-700);
  color: var(--ink-300);
}

.mode-terminal .info-tooltip-bubble {
  background: var(--ink-700);
  color: var(--fg-terminal);
}
```

- [ ] **Step 6: Run the full frontend suite, lint, and build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all clean/passing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/InfoTooltip.tsx frontend/src/components/ui/InfoTooltip.test.tsx frontend/src/index.css
git commit -m "feat: add a reusable InfoTooltip component"
```

---

### Task 4: Replace the annual-return slider with the static display

**Files:**
- Modify: `frontend/src/features/portfolio/ProjectionPanel.tsx`
- Modify: `frontend/src/features/portfolio/projection.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: Task 2's `ProjectionOverrides` (without `annualReturn`); Task 3's `InfoTooltip` component.
- Produces: nothing for later tasks — this is the final task.

- [ ] **Step 1: Update the obsolete slider test and fixture, and add new tests**

In `frontend/src/features/portfolio/projection.test.tsx`, find:

```tsx
const projectionWithTarget: ProjectionResponse = {
  base_currency: "USD",
  start_value: "10000",
  target_amount: "50000",
  horizon_years: 10,
  contribution_amount: "500",
  contribution_frequency: "monthly",
  annual_return_expected: "0.06",
```

Replace with (this field is a plain percentage value throughout the codebase, e.g. `"8"` means 8% — `"0.06"` was never actually asserted against and doesn't match that convention; fixing it here so the new assertions below are meaningful):

```tsx
const projectionWithTarget: ProjectionResponse = {
  base_currency: "USD",
  start_value: "10000",
  target_amount: "50000",
  horizon_years: 10,
  contribution_amount: "500",
  contribution_frequency: "monthly",
  annual_return_expected: "6",
```

Find:

```tsx
  it("debounces an annual return slider change into a committed override", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    const slider = screen.getByLabelText("Expected annual return");
    fireEvent.change(slider, { target: { value: "7.5" } });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 400));
    });

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {
        annualReturn: "7.5",
      });
    });
  });
```

Replace with:

```tsx
  it("shows the computed expected annual return as static, non-editable text", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    expect(screen.getByText("6%")).toBeInTheDocument();
    expect(
      screen.queryByRole("slider", { name: "Expected annual return" })
    ).not.toBeInTheDocument();
  });

  it("shows a tooltip trigger explaining how the expected annual return is computed", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    expect(
      screen.getByRole("button", { name: "How is this calculated?" })
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- projection.test -v`
Expected: FAIL — `getByText("6%")` and the tooltip trigger don't exist yet; the slider (`getByLabelText("Expected annual return")`) still does.

- [ ] **Step 3: Remove the annual-return slider's state and effects**

In `frontend/src/features/portfolio/ProjectionPanel.tsx`, find:

```tsx
  const [contribution, setContribution] = useState<string | null>(null);
  const [annualReturnDraft, setAnnualReturnDraft] = useState<string | null>(
    null
  );
  const [annualReturn, setAnnualReturn] = useState<string | null>(null);
```

Replace with:

```tsx
  const [contribution, setContribution] = useState<string | null>(null);
```

Find:

```tsx
  useEffect(() => {
    const timer = setTimeout(() => {
      setContribution(contributionDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [contributionDraft]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnnualReturn(annualReturnDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [annualReturnDraft]);
```

Replace with:

```tsx
  useEffect(() => {
    const timer = setTimeout(() => {
      setContribution(contributionDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [contributionDraft]);
```

- [ ] **Step 4: Remove `annualReturn` from the query key and query function**

Find:

```tsx
    queryKey: [
      "portfolio-projection",
      accessToken,
      years,
      contribution,
      annualReturn,
    ],
    queryFn: () => {
      const overrides: Parameters<typeof getProjection>[1] = {};
      if (years !== null) overrides.years = years;
      if (contribution !== null) overrides.contribution = contribution;
      if (annualReturn !== null) overrides.annualReturn = annualReturn;
      return getProjection(accessToken, overrides);
    },
```

Replace with:

```tsx
    queryKey: ["portfolio-projection", accessToken, years, contribution],
    queryFn: () => {
      const overrides: Parameters<typeof getProjection>[1] = {};
      if (years !== null) overrides.years = years;
      if (contribution !== null) overrides.contribution = contribution;
      return getProjection(accessToken, overrides);
    },
```

- [ ] **Step 5: Simplify the displayed value and drop the override from `hasOverride`/`resetOverrides`**

Find:

```tsx
  const displayedAnnualReturn = Number(
    annualReturnDraft ?? annualReturn ?? data?.annual_return_expected ?? "0"
  );
```

Replace with:

```tsx
  const displayedAnnualReturn = Number(data?.annual_return_expected ?? "0");
```

Find:

```tsx
  const hasOverride = years !== null || contribution !== null || annualReturn !== null;

  function resetOverrides() {
    setYears(null);
    setContributionDraft(null);
    setContribution(null);
    setAnnualReturnDraft(null);
    setAnnualReturn(null);
  }
```

Replace with:

```tsx
  const hasOverride = years !== null || contribution !== null;

  function resetOverrides() {
    setYears(null);
    setContributionDraft(null);
    setContribution(null);
  }
```

- [ ] **Step 6: Replace the slider JSX with the static display**

Find:

```tsx
          <div className="projection-slider-field">
            <div className="projection-slider-heading">
              <label htmlFor="projection-annual-return">
                Expected annual return
              </label>
              <span className="num">
                {formatPercent(String(displayedAnnualReturn))}
              </span>
            </div>
            <input
              className="projection-slider"
              id="projection-annual-return"
              max={20}
              min={-5}
              step={0.5}
              type="range"
              value={displayedAnnualReturn}
              onChange={(event) =>
                setAnnualReturnDraft(event.target.value)
              }
            />
          </div>
```

Replace with:

```tsx
          <div className="projection-static-field">
            <div className="projection-static-heading">
              <span className="projection-static-label">
                Expected annual return
                <InfoTooltip text="Estimated from your current holdings — a weighted average of each holding's 5-year historical return, or a broad asset-class estimate where history isn't available yet.">
                  ?
                </InfoTooltip>
              </span>
              <span className="num">
                {formatPercent(String(displayedAnnualReturn))}
              </span>
            </div>
          </div>
```

- [ ] **Step 7: Add the import**

Find:

```tsx
import { ProjectionChart } from "../../components/charts/ProjectionChart";
import { TrendLoader } from "../../components/ui/TrendLoader";
```

Replace with:

```tsx
import { ProjectionChart } from "../../components/charts/ProjectionChart";
import { InfoTooltip } from "../../components/ui/InfoTooltip";
import { TrendLoader } from "../../components/ui/TrendLoader";
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd frontend && npm test -- projection.test -v`
Expected: PASS (all tests in the file).

- [ ] **Step 9: Add the static-field CSS**

In `frontend/src/index.css`, find:

```css
.projection-slider-field {
  display: grid;
  gap: 6px;
}
```

Replace with:

```css
.projection-slider-field {
  display: grid;
  gap: 6px;
}

.projection-static-field {
  display: grid;
  gap: 6px;
}

.projection-static-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--ink-600);
}

.projection-static-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
```

- [ ] **Step 10: Run the full frontend suite, lint, and build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all clean/passing.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/features/portfolio/ProjectionPanel.tsx frontend/src/features/portfolio/projection.test.tsx frontend/src/index.css
git commit -m "feat: replace the annual-return slider with a static, tooltip-explained value"
```
