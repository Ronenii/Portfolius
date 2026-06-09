import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";

import Button from "../../components/ui/Button";
import InstrumentSearchInput from "../instruments/InstrumentSearchInput";
import { type InstrumentSearchResult } from "../instruments/instrument-search-api";
import {
  simulatePortfolio,
  type AllocationDelta,
  type SimulationResponse,
  type TradeLeg,
} from "./portfolio-api";

const breakdownDimensions = [
  { key: "instrument", label: "Instrument" },
  { key: "asset_class", label: "Asset class" },
  { key: "sector", label: "Sector" },
  { key: "country", label: "Country" },
  { key: "region", label: "Region" },
  { key: "currency", label: "Currency" },
] as const;

type BreakdownDimension = (typeof breakdownDimensions)[number]["key"];
type DraftLeg = {
  action: "buy" | "sell";
  price: string;
  quantity: string;
  symbol: string;
};

const emptyDraft: DraftLeg = {
  action: "buy",
  price: "",
  quantity: "",
  symbol: "",
};

function formatPercent(value: string) {
  const numericValue = Number(value);
  return `${new Intl.NumberFormat("en", {
    maximumFractionDigits: 2,
    minimumFractionDigits: Number.isInteger(numericValue) ? 0 : 1,
  }).format(Number.isFinite(numericValue) ? numericValue : 0)}%`;
}

function legLabel(leg: TradeLeg) {
  return `${leg.symbol ?? "Instrument"} ${leg.action} leg`;
}

export default function SimulationPanel({ accessToken }: { accessToken: string }) {
  const [draft, setDraft] = useState<DraftLeg>(emptyDraft);
  const [legs, setLegs] = useState<TradeLeg[]>([]);
  const [selectedDimension, setSelectedDimension] =
    useState<BreakdownDimension>("instrument");

  const simulateMutation = useMutation({
    mutationFn: (nextLegs: TradeLeg[]) => simulatePortfolio(accessToken, nextLegs),
  });

  function updateDraft<Key extends keyof DraftLeg>(field: Key, value: DraftLeg[Key]) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function selectInstrument(result: InstrumentSearchResult) {
    updateDraft("symbol", result.symbol);
  }

  function addLeg(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = draft.symbol.trim().toUpperCase();
    const quantity = draft.quantity.trim();
    const price = draft.price.trim();
    if (!symbol || !quantity) {
      return;
    }

    setLegs((current) => [
      ...current,
      {
        action: draft.action,
        price: price || null,
        quantity,
        symbol,
      },
    ]);
    setDraft(emptyDraft);
  }

  function removeLeg(index: number) {
    setLegs((current) => current.filter((_leg, legIndex) => legIndex !== index));
  }

  const result = simulateMutation.data;
  const selectedDelta = (result?.delta ?? []).filter(
    (row) => row.dimension === selectedDimension
  );

  return (
    <section className="simulation-panel" aria-labelledby="simulation-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">What-if</p>
          <h2 id="simulation-title">Simulation</h2>
        </div>
      </div>

      <form className="simulation-leg-editor" onSubmit={addLeg}>
        <div className="field">
          <label htmlFor="simulation-action">Action</label>
          <select
            id="simulation-action"
            value={draft.action}
            onChange={(event) =>
              updateDraft("action", event.target.value as DraftLeg["action"])
            }
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </div>
        <InstrumentSearchInput
          accessToken={accessToken}
          id="simulation-symbol"
          label="Symbol"
          value={draft.symbol}
          onChange={(value) => updateDraft("symbol", value)}
          onSelect={selectInstrument}
        />
        <div className="field">
          <label htmlFor="simulation-quantity">Quantity</label>
          <input
            id="simulation-quantity"
            min="0"
            step="any"
            type="number"
            value={draft.quantity}
            onChange={(event) => updateDraft("quantity", event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="simulation-price">Price</label>
          <input
            id="simulation-price"
            min="0"
            step="any"
            type="number"
            value={draft.price}
            onChange={(event) => updateDraft("price", event.target.value)}
          />
        </div>
        <Button icon={Plus} type="submit" variant="secondary">
          Add leg
        </Button>
      </form>

      {legs.length > 0 ? (
        <div className="simulation-leg-list" aria-label="Simulation legs">
          {legs.map((leg, index) => (
            <div className="simulation-leg" key={`${leg.symbol}-${index}`}>
              <span className="num">{leg.symbol}</span>
              <span>{leg.action}</span>
              <span className="num">{leg.quantity}</span>
              {leg.price ? <span className="num">@ {leg.price}</span> : null}
              <button
                aria-label={`Remove ${legLabel(leg)}`}
                type="button"
                onClick={() => removeLeg(index)}
              >
                <Trash2 aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state simulation-empty">
          <strong>No simulation legs</strong>
          <span>Add a buy or sell leg to preview allocation changes.</span>
        </div>
      )}

      <Button
        disabled={legs.length === 0 || simulateMutation.isPending}
        type="button"
        variant="primary"
        onClick={() => simulateMutation.mutate(legs)}
      >
        {simulateMutation.isPending ? "Simulating" : "Simulate"}
      </Button>

      {simulateMutation.error ? (
        <p className="form-error" role="alert">
          {simulateMutation.error instanceof Error
            ? simulateMutation.error.message
            : "Simulation failed"}
        </p>
      ) : null}

      {result ? (
        <SimulationResult
          result={result}
          selectedDelta={selectedDelta}
          selectedDimension={selectedDimension}
          onSelectDimension={setSelectedDimension}
        />
      ) : null}
    </section>
  );
}

function SimulationResult({
  onSelectDimension,
  result,
  selectedDelta,
  selectedDimension,
}: {
  onSelectDimension: (dimension: BreakdownDimension) => void;
  result: SimulationResponse;
  selectedDelta: AllocationDelta[];
  selectedDimension: BreakdownDimension;
}) {
  return (
    <div className="simulation-result">
      {result.warnings.length > 0 ? (
        <div className="simulation-warnings" aria-label="Simulation warnings">
          {result.warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}

      <div
        className="segmented-control simulation-dimension-control"
        aria-label="Simulation dimension"
      >
        {breakdownDimensions.map((dimension) => (
          <button
            aria-pressed={selectedDimension === dimension.key}
            className={
              selectedDimension === dimension.key
                ? "segmented-button segmented-button--active"
                : "segmented-button"
            }
            key={dimension.key}
            type="button"
            onClick={() => onSelectDimension(dimension.key)}
          >
            {dimension.label}
          </button>
        ))}
      </div>

      {selectedDelta.length > 0 ? (
        <div className="allocation-table-wrap">
          <table className="allocation-table" aria-label="Simulation delta">
            <thead>
              <tr>
                <th scope="col">Label</th>
                <th scope="col">Currency</th>
                <th scope="col">Before</th>
                <th scope="col">After</th>
                <th scope="col">Change</th>
              </tr>
            </thead>
            <tbody>
              {selectedDelta.map((row) => (
                <tr key={`${row.dimension}-${row.label}-${row.currency}`}>
                  <td data-label="Label">{row.label}</td>
                  <td className="num" data-label="Currency">
                    {row.currency}
                  </td>
                  <td className="num" data-label="Before">
                    {formatPercent(row.percent_before)}
                  </td>
                  <td className="num" data-label="After">
                    {formatPercent(row.percent_after)}
                  </td>
                  <td className="num" data-label="Change">
                    {formatPercent(row.percent_change)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state simulation-empty">
          <strong>No delta rows</strong>
          <span>This dimension did not change in the simulated basket.</span>
        </div>
      )}
    </div>
  );
}
