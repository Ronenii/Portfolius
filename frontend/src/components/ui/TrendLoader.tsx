type TrendLoaderProps = {
  /** Optional small caption shown under the chart (e.g. "Loading profile"). */
  label?: string;
  /** Accessible status text announced to screen readers. Defaults to `label`. */
  srLabel?: string;
};

// An upward-trending line with short-term fluctuations. The path is normalised
// to a length of 100 (pathLength) so the stroke draw + leading dot stay in sync
// regardless of the rendered size.
const TREND_PATH =
  "M4 76 L20 70 L36 74 L52 58 L68 64 L84 44 L100 50 L116 32 L132 38 L148 20 L160 14";

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function TrendLoader({ label, srLabel }: TrendLoaderProps) {
  const reducedMotion = prefersReducedMotion();
  return (
    <div className="trend-loader" role="status" aria-live="polite">
      <svg
        className="trend-loader__svg"
        viewBox="0 0 164 88"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="trend-loader-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Baseline grid for a "chart" feel */}
        <line className="trend-loader__grid" x1="4" y1="84" x2="160" y2="84" />

        {/* Area under the trend line */}
        <path
          className="trend-loader__area"
          d={`${TREND_PATH} L160 84 L4 84 Z`}
          fill="url(#trend-loader-fill)"
        />

        {/* The trend line, drawn repeatedly left-to-right */}
        <path
          className="trend-loader__line"
          d={TREND_PATH}
          pathLength={100}
        />

        {/* Leading dot rides the tip as the line draws */}
        {reducedMotion ? (
          <circle className="trend-loader__dot" cx="160" cy="14" r="3.5" />
        ) : (
          <circle className="trend-loader__dot" r="3.5">
            <animateMotion
              dur="1.8s"
              repeatCount="indefinite"
              keyPoints="0;1;1"
              keyTimes="0;0.65;1"
              calcMode="linear"
              path={TREND_PATH}
            />
          </circle>
        )}
      </svg>

      {label ? <p className="trend-loader__label">{label}</p> : null}
      <span className="sr-only">{srLabel ?? label ?? "Loading"}</span>
    </div>
  );
}
