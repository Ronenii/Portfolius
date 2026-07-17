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
