import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { TrendLoader } from "../../components/ui/TrendLoader";
import {
  getComposition,
  type AllocationRow,
  type CompositionResponse,
} from "./portfolio-api";

type CompositionPopoverProps = {
  accessToken: string;
  dimensionLabel: string;
  formatPercent: (value: string | null | undefined) => string;
  formatValue: (value: string | null | undefined, currency?: string) => string;
  onClose: () => void;
  selectedBucket: AllocationRow;
};

export function CompositionPopover({
  accessToken,
  dimensionLabel,
  formatPercent,
  formatValue,
  onClose,
  selectedBucket,
}: CompositionPopoverProps) {
  const compositionQuery = useQuery<CompositionResponse>({
    enabled: Boolean(accessToken),
    queryFn: () =>
      getComposition(
        accessToken,
        selectedBucket.dimension,
        selectedBucket.label,
        selectedBucket.currency
      ),
    queryKey: [
      "portfolio-composition",
      accessToken,
      selectedBucket.dimension,
      selectedBucket.label,
      selectedBucket.currency,
    ],
  });

  const response = compositionQuery.data;
  const headingId = `composition-${selectedBucket.dimension}-${selectedBucket.label}-${selectedBucket.currency}`;
  const portfolioShare = formatPercent(
    response?.percent_of_portfolio ?? selectedBucket.percent
  );

  return (
    <section
      aria-labelledby={headingId}
      className="composition-popover"
      role="dialog"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.stopPropagation();
          onClose();
        }
      }}
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{dimensionLabel} composition</p>
          <h3 id={headingId}>{selectedBucket.label} composition</h3>
        </div>
        <div className="composition-popover__meta">
          <span className="allocation-note">{portfolioShare} of portfolio</span>
          <button
            aria-label="Close composition"
            className="icon-button"
            type="button"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </button>
        </div>
      </div>

      {compositionQuery.isLoading ? (
        <TrendLoader label="Reading child instruments" srLabel="Loading composition" />
      ) : null}

      {compositionQuery.error ? (
        <div className="empty-state">
          <strong>Composition unavailable</strong>
          <span>
            {compositionQuery.error instanceof Error
              ? compositionQuery.error.message
              : "Composition request failed."}
          </span>
        </div>
      ) : null}

      {response && response.children.length === 0 ? (
        <div className="empty-state">
          <strong>No child instruments</strong>
          <span>This bucket has no priced child rows in the selected currency.</span>
        </div>
      ) : null}

      {response && response.children.length > 0 ? (
        <div className="composition-list" aria-label={`${selectedBucket.label} instruments`}>
          {response.children.map((child) => (
            <article className="composition-row" key={`${child.instrument_id}-${child.currency}`}>
              <div>
                <strong>{child.symbol}</strong>
                <span>{child.name}</span>
              </div>
              <div className="composition-row__values">
                <span className="num">{formatValue(child.market_value, child.currency)}</span>
                <span className="num">
                  {formatPercent(child.percent_of_parent)} of slice ·{" "}
                  {formatPercent(child.percent_of_portfolio)} of portfolio
                </span>
                <span className="num">
                  {child.holding_count} holding{child.holding_count === 1 ? "" : "s"}
                </span>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {response?.unpriced_holding_count ? (
        <span className="allocation-note">
          {response.unpriced_holding_count} unpriced excluded
        </span>
      ) : null}
    </section>
  );
}
