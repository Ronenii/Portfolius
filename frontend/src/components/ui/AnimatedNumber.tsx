import { useCountUp } from "./useCountUp";

type AnimatedNumberProps = {
  /** The target numeric value to animate toward. */
  value: number;
  /** Formats the (possibly fractional, mid-tween) number for display. */
  format: (value: number) => string;
  className?: string;
  /** Override the tween duration in ms (defaults to the brand 320ms). */
  durationMs?: number;
};

/**
 * Renders a number that counts up/down to `value` over a short tween. Pairs
 * with the brand's one sanctioned delight — numerics animating on update.
 */
export function AnimatedNumber({
  className,
  durationMs,
  format,
  value,
}: AnimatedNumberProps) {
  const animated = useCountUp(value, durationMs ? { durationMs } : undefined);
  return <span className={className}>{format(animated)}</span>;
}
