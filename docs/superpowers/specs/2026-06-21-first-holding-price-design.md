# First Holding Price Design

## Goal

Make a newly added holding appear in portfolio value and allocation views
without requiring the user to run a manual price refresh.

## Behavior

When `POST /api/v1/holdings` succeeds:

- create or reuse the instrument and create the holding;
- if that instrument has no stored price, request its latest close from the
  existing market-data client;
- store a finite returned price through the existing price upsert path;
- if the provider raises, returns no price, or returns a non-finite price,
  keep the holding and return success;
- if any price already exists for the instrument, skip the provider call.

The lookup applies to the first stored price for an instrument, not the first
holding per user. Instruments and prices are shared records, so later holdings
reuse the cached price.

## Architecture

The holdings endpoint will receive the same `MarketDataClient` dependency used
by portfolio simulation and price refresh. A focused domain helper will check
for an existing latest price and, only when absent, fetch and upsert one.

The helper commits only the price operation after the holding has already been
created. Price lookup is best-effort and never rolls back or rejects a valid
holding.

No new endpoint, queue, or background worker is introduced.

## Frontend Cache Consistency

Successful create, update, and delete mutations will invalidate:

- `holdings`;
- `portfolio-snapshot`;
- `portfolio-breakdowns`.

This ensures navigation back to the Dashboard cannot display allocation data
cached before the holding mutation.

## Testing

Backend tests will verify:

- a first holding fetches and stores a finite price;
- a later holding for an already-priced instrument does not fetch again;
- provider exceptions, missing prices, and non-finite prices do not fail
  holding creation.

Frontend tests will verify successful create, update, and delete mutations
invalidate all three affected query families.

The full backend and frontend verification commands must remain green.
