# Allocation units and positions

## Problem

Allocation rows currently expose `holding_count`, which counts persisted holding
records. When the same instrument was entered in several lots, the dashboard can
show `3 holdings` even though the user owns `44` units of one instrument. The
number is technically a lot count but is presented as an ownership count.

## Desired behavior

- The Instrument allocation view displays the summed quantity for each
  instrument under a `Units` heading.
- Quantities from multiple lots of the same instrument are added together.
- Asset class, sector, country, region, and currency views display `Positions`.
- A position is a distinct instrument within that allocation bucket, not a
  persisted holding lot.
- Quantity formatting removes unnecessary trailing zeroes while preserving
  fractional units.
- Chart tooltips use the same terminology and values as the allocation table.

For example, three VOO lots with quantities `10`, `14`, and `20` produce:

- Instrument / VOO: `44` units.
- Asset class / ETF: `1` position, assuming VOO is the only ETF.

## Backend contract

`AllocationRow` will distinguish the two concepts:

- `position_count`: the number of distinct instruments represented by the row.
- `unit_quantity`: the summed quantity when `dimension == "instrument"`;
  otherwise `null`.

The ambiguous `holding_count` field will be removed from allocation rows.
Composition rows use `unit_quantity`, summing quantities across saved lots for
each child instrument. Saved lot count is an implementation detail and is not
shown in allocation drill-downs.

Allocation grouping will track distinct instrument IDs for every dimension and
sum quantities for instrument rows. Market-value and percentage calculations
remain unchanged. Unpriced holdings remain excluded from allocation rows, so
units and positions describe the same priced population represented by the
row's value and percentage.

## Frontend behavior

The allocation table chooses its final column from the selected dimension:

- Instrument: heading `Units`, value `unit_quantity`.
- Every other dimension: heading `Positions`, value `position_count`.

Bar and donut tooltips follow the same rule. Numeric values retain the existing
monospace treatment. The frontend API types will mirror the backend response.

The composition popover displays each child instrument's summed quantity as
`<quantity> units`, using the same trailing-zero-free quantity formatting as the
Instrument allocation table. For example, IEUR lots of `5` and `15` display as
one IEUR child row with `20 units`.

## Testing

Backend regression coverage will build multiple lots for one instrument and
verify:

- instrument quantity is summed;
- the instrument position count is one;
- broader buckets count distinct instruments rather than lots;
- fractional quantities serialize without losing precision.

Frontend regression coverage will verify:

- the Instrument table and chart tooltip show `44` units for multiple VOO lots;
- broader dimensions show `1` position;
- a broader bucket's composition shows summed units rather than saved lot count;
- the ambiguous `Holdings` heading is absent from allocation views.

Existing allocation, composition, simulation, lint, and build checks will be
run after implementation.
