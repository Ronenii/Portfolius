import type { AllocationRow } from "./portfolio-api";

export function allocationUnitValue(value: string | null) {
  const quantity = Number(value ?? 0);
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 12,
  }).format(Number.isFinite(quantity) ? quantity : 0);
}

export function allocationQuantityLabel(row: AllocationRow) {
  return row.dimension === "instrument" ? "Units" : "Positions";
}

export function allocationQuantityValue(row: AllocationRow) {
  return row.dimension === "instrument"
    ? allocationUnitValue(row.unit_quantity)
    : String(row.position_count);
}
