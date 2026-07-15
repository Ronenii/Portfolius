import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ProjectionChart } from "../../components/charts/ProjectionChart";
import { TrendLoader } from "../../components/ui/TrendLoader";
import { ApiError } from "../../lib/api";
import { getProjection } from "./portfolio-api";

function formatMoney(value: string, currency = "USD") {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    currency,
    style: "currency",
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

function formatPercent(value: string) {
  const numericValue = Number(value);
  return `${new Intl.NumberFormat("en", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(Number.isFinite(numericValue) ? numericValue : 0)}%`;
}

function projectionErrorCopy(error: unknown) {
  if (error instanceof ApiError && error.status === 404) {
    return {
      detail: "Create a profile to see your goal projection.",
      title: "No profile yet",
    };
  }

  return {
    detail: error instanceof Error ? error.message : "Projection request failed.",
    title: "Projection unavailable",
  };
}

const HORIZON_OPTIONS = [3, 5, 10, 15, 20, 30];
const DEBOUNCE_MS = 350;

export default function ProjectionPanel({ accessToken }: { accessToken: string }) {
  const [years, setYears] = useState<number | null>(null);
  const [contributionDraft, setContributionDraft] = useState<string | null>(
    null
  );
  const [contribution, setContribution] = useState<string | null>(null);
  const [annualReturnDraft, setAnnualReturnDraft] = useState<string | null>(
    null
  );
  const [annualReturn, setAnnualReturn] = useState<string | null>(null);

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

  const projectionQuery = useQuery({
    enabled: Boolean(accessToken),
    placeholderData: keepPreviousData,
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
  });

  const data = projectionQuery.data;
  const effectiveYears = years ?? data?.horizon_years ?? null;
  const displayedContribution = Number(
    contributionDraft ?? contribution ?? data?.contribution_amount ?? "0"
  );
  const displayedAnnualReturn = Number(
    annualReturnDraft ?? annualReturn ?? data?.annual_return_expected ?? "0"
  );
  const contributionMax = Math.max(
    Number(data?.contribution_amount ?? 0) * 4,
    1000
  );
  const hasOverride = years !== null || contribution !== null || annualReturn !== null;

  function resetOverrides() {
    setYears(null);
    setContributionDraft(null);
    setContribution(null);
    setAnnualReturnDraft(null);
    setAnnualReturn(null);
  }

  const isProfileMissing =
    projectionQuery.error instanceof ApiError && projectionQuery.error.status === 404;
  const clampedPercent =
    data?.target_progress_percent != null
      ? Math.min(100, Math.max(0, Number(data.target_progress_percent)))
      : null;

  return (
    <section className="projection-panel" aria-labelledby="projection-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Goal tracking</p>
          <h2 id="projection-title">Goal projection</h2>
        </div>
      </div>

      {projectionQuery.isLoading ? (
        <TrendLoader
          label="Reading your goal projection"
          srLabel="Loading projection"
        />
      ) : null}

      {projectionQuery.error ? (
        <div className="empty-state">
          <strong>{projectionErrorCopy(projectionQuery.error).title}</strong>
          <span>{projectionErrorCopy(projectionQuery.error).detail}</span>
          {isProfileMissing ? (
            <Link className="button button--ghost" to="/profile">
              Go to Profile
            </Link>
          ) : null}
        </div>
      ) : null}

      {data ? (
        <>
          <div
            aria-label="Projection horizon"
            className="segmented-control projection-horizon-control"
          >
            {HORIZON_OPTIONS.map((option) => (
              <button
                aria-pressed={effectiveYears === option}
                className={
                  effectiveYears === option
                    ? "segmented-button segmented-button--active"
                    : "segmented-button"
                }
                key={option}
                type="button"
                onClick={() => setYears(option)}
              >
                {option}y
              </button>
            ))}
          </div>

          <div className="projection-slider-field">
            <div className="projection-slider-heading">
              <label htmlFor="projection-contribution">
                Contribution amount
              </label>
              <span className="num">
                {formatMoney(String(displayedContribution), data.base_currency)}
              </span>
            </div>
            <input
              className="projection-slider"
              id="projection-contribution"
              max={contributionMax}
              min={0}
              step={10}
              type="range"
              value={displayedContribution}
              onChange={(event) =>
                setContributionDraft(event.target.value)
              }
            />
          </div>

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

          {projectionQuery.isFetching && !projectionQuery.isLoading ? (
            <span className="projection-updating" role="status">
              Updating…
            </span>
          ) : null}

          {hasOverride ? (
            <button
              className="projection-reset"
              type="button"
              onClick={resetOverrides}
            >
              Reset to my profile values
            </button>
          ) : null}

          <ProjectionChart
            currency={data.base_currency}
            formatValue={formatMoney}
            onTrack={data.on_track}
            series={data.series}
            targetAmount={data.target_amount}
            targetReachedYear={data.target_reached_year}
          />

          <p className="projection-caption">
            Projected over {data.horizon_years} years, {data.contribution_frequency}{" "}
            contributions of {formatMoney(data.contribution_amount, data.base_currency)}.
          </p>

          {data.target_progress_percent != null && clampedPercent != null ? (
            <div className="projection-goal">
              <div className="projection-progress-heading">
                <span>Progress to target</span>
                <span className="num">
                  {formatPercent(data.target_progress_percent)}
                </span>
              </div>
              <div className="projection-progress">
                <div
                  className="projection-progress-bar"
                  style={{ width: `${clampedPercent}%` }}
                />
              </div>
              {data.on_track != null ? (
                <p className={data.on_track ? "gain" : "loss"}>
                  {data.on_track
                    ? `On track${
                        data.target_reached_year
                          ? ` — reaches your target by ${data.target_reached_year}`
                          : ""
                      }`
                    : "Behind pace — consider increasing contributions."}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="empty-state projection-empty">
              <strong>No goal set</strong>
              <span>Set a goal target in your profile to track progress toward it.</span>
              <Link className="button button--ghost" to="/profile">
                Go to Profile
              </Link>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
