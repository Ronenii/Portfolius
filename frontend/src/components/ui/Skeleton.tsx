import type { CSSProperties } from "react";

type SkeletonProps = {
  /** Number → px. String is used verbatim (e.g. "100%", "1.5rem"). */
  width?: number | string;
  /** Number → px. String is used verbatim (e.g. "100%", "1.5rem"). */
  height?: number | string;
  /** Renders an equal-radius pill/circle instead of the default rounded rect. */
  circle?: boolean;
  /** Appended after the base class. */
  className?: string;
};

const toDimension = (value: number | string | undefined) =>
  value === undefined ? undefined : typeof value === "number" ? `${value}px` : value;

const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function Skeleton({ width, height, circle, className }: SkeletonProps) {
  const reducedMotion = prefersReducedMotion();

  const style: CSSProperties = {};
  const widthValue = toDimension(width);
  const heightValue = toDimension(height);
  if (widthValue !== undefined) style.width = widthValue;
  if (heightValue !== undefined) style.height = heightValue;

  const classes = ["skeleton"];
  if (circle) classes.push("skeleton--circle");
  if (reducedMotion) classes.push("skeleton--static");
  if (className) classes.push(className);

  return <div className={classes.join(" ")} style={style} aria-hidden="true" />;
}
