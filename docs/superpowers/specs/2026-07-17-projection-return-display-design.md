# Expected Annual Return: Static Display Design Spec

Follow-up to M5 Step 7b (auto-computed expected annual return). Now that
`annual_return_expected` is always derived from the user's actual holdings
(never a manual guess), the interactive "Expected annual return" slider in
the goal projection panel is misleading — it invites the user to edit a
number that isn't really an input, it's a computed fact. This spec replaces
the slider with a plain, non-editable display of that computed value, plus a
hover/focus disclaimer explaining how it's derived.

## Background

`ProjectionPanel.tsx` currently renders three interactive controls: a
horizon selector, a contribution-amount slider, and an annual-return slider.
The annual-return slider lets the user drag to an arbitrary override value,
which the backend's `/api/v1/portfolio/projection` endpoint accepts via an
`annual_return` query param and threads through
`build_projection_for_user`. Nothing else in the app uses this override —
it exists solely for this one slider.

Since the slider is being removed and nothing else depends on the override,
the override capability is removed end-to-end (backend query param, service
function parameter, and the frontend override plumbing) rather than left in
place unused.

## A. Backend: remove the `annual_return` override

- `backend/app/api/v1/portfolio.py`: `read_portfolio_projection` drops the
  `annual_return: Decimal | None = None` parameter and the
  `annual_return=annual_return` kwarg passed to `build_projection_for_user`.
- `backend/app/domain/portfolio_service.py`: `build_projection_for_user`
  drops the `annual_return: Decimal | None = None` parameter. Its resolution
  collapses to just the computed-weighted-average-or-risk-tolerance-fallback
  branch (the `if annual_return is not None` branch is deleted entirely, not
  just made unreachable).
- No schema change needed: `ProjectionResponse.annual_return_expected` is
  unchanged in shape — it already carries the single resolved value. Once
  the override is gone, that value is always the computed baseline, which
  is exactly what the new static display needs — no new field required.

## B. Frontend: static display instead of a slider

In `frontend/src/features/portfolio/ProjectionPanel.tsx`:

- Delete: `annualReturnDraft`/`annualReturn` state, their debounce `useEffect`,
  the `annualReturn` entry in the query key and `overrides` object, and the
  entire annual-return `projection-slider-field` JSX block.
- `hasOverride` becomes `years !== null || contribution !== null` (drops the
  `annualReturn !== null` clause) — the reset button still governs the
  remaining two overrides.
- `displayedAnnualReturn` is simplified to just `Number(data?.annual_return_expected ?? "0")`
  (no draft/override fallback chain — there's nothing to fall back from).
- New static block, in the same position the slider occupied:
  ```tsx
  <div className="projection-static-field">
    <div className="projection-static-heading">
      <span>Expected annual return</span>
      <InfoTooltip text="Estimated from your current holdings — a weighted average of each holding's 5-year historical return, or a broad asset-class estimate where history isn't available yet.">
        ?
      </InfoTooltip>
    </div>
    <span className="num">{formatPercent(String(displayedAnnualReturn))}</span>
  </div>
  ```

## C. `InfoTooltip` component

A small, new, reusable component — nothing like it exists in the codebase
yet, but it's generic enough to justify a shared component rather than
inlining it once:

- `frontend/src/components/ui/InfoTooltip.tsx`: renders a `<button
  type="button" aria-label="How is this calculated?">` containing the `?`
  glyph, with a `<span role="tooltip">` sibling holding the disclaimer text.
  The tooltip span is visually hidden by default and revealed via CSS on the
  button's `:hover`/`:focus-visible` (and the button's `:focus-within`
  wrapper) — no JS state, no positioning library. This makes it keyboard
  accessible (tab to the button, tooltip appears on focus) as well as
  mouse-hover accessible.
- CSS added to `frontend/src/index.css`, following the existing
  `.projection-slider-field`/`.projection-reset` naming conventions:
  `.info-tooltip`, `.info-tooltip-trigger`, `.info-tooltip-bubble` (hidden by
  default, shown on `:hover`/`:focus-visible` of the trigger).
- Props: `text: string` (the disclaimer) and `children` (the trigger glyph/
  label — always `"?"` for this usage, but kept generic so a future caller
  isn't forced to reuse this exact copy).

## D. Testing

**Backend:** update `test_projection_api.py` — remove the `annual_return`
query-param override tests entirely (the override no longer exists); the
existing computed-return tests (Task 3's work) already prove the resolution
logic without needing an override path.

**Frontend:**
- `InfoTooltip.test.tsx` (new): renders the trigger with the given
  `aria-label`; the disclaimer text is present in the DOM and associated to
  the trigger via `aria-describedby` (a generated/fixed id on the tooltip
  span), so screen readers announce it on focus even though it's visually
  hidden until hover/focus — verified via the CSS class toggling, not a
  JS-driven show/hide test (there is no JS state).
- `projection.test.tsx`: remove the annual-return slider interaction test(s);
  add a test asserting the static value renders from
  `data.annual_return_expected` and is not an editable control (no `role`
  matching a slider/input for it); add a test that the tooltip trigger is
  present with the expected disclaimer text.

## Out of scope

- Any change to the contribution-amount slider or horizon selector — both
  remain interactive overrides, unaffected by this change.
- Any change to how `annual_return_expected` is computed (that's M5 Step 7b,
  already shipped) — this spec only changes how it's *displayed* and removes
  the now-pointless override path.
- Making `InfoTooltip` support rich content (links, formatting) — plain text
  only, per this one usage.
