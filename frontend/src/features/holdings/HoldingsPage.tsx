import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { type FormEvent, useState } from "react";

import Button from "../../components/ui/Button";
import { ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import InstrumentSearchInput from "../instruments/InstrumentSearchInput";
import type { InstrumentSearchResult } from "../instruments/instrument-search-api";
import {
  createHolding,
  deleteHolding,
  listHoldings,
  updateHolding,
  type Holding,
  type HoldingPayload,
} from "./holdings-api";

type HoldingFormErrors = Partial<Record<keyof HoldingPayload | "form", string>>;

const emptyForm: HoldingPayload = {
  symbol: "",
  name: "",
  exchange: "",
  currency: "",
  asset_class: "",
  sector: "",
  country: "",
  region: "",
  quantity: "",
  average_cost: "",
};

function optionalValue(value: string | null | undefined): string {
  return value ?? "";
}

function payloadFromHolding(holding: Holding): HoldingPayload {
  return {
    symbol: holding.instrument.symbol,
    name: optionalValue(holding.instrument.name),
    exchange: optionalValue(holding.instrument.exchange),
    currency: optionalValue(holding.instrument.currency),
    asset_class: optionalValue(holding.instrument.asset_class),
    sector: optionalValue(holding.instrument.sector),
    country: optionalValue(holding.instrument.country),
    region: optionalValue(holding.instrument.region),
    quantity: holding.quantity,
    average_cost: holding.average_cost,
  };
}

function cleanedPayload(form: HoldingPayload): HoldingPayload {
  return {
    symbol: form.symbol.trim(),
    name: form.name?.trim() || null,
    exchange: form.exchange?.trim() || null,
    currency: form.currency?.trim() || null,
    asset_class: form.asset_class?.trim() || null,
    sector: form.sector?.trim() || null,
    country: form.country?.trim() || null,
    region: form.region?.trim() || null,
    quantity: form.quantity.trim(),
    average_cost: form.average_cost.trim(),
  };
}

function validateHolding(payload: HoldingPayload): HoldingFormErrors {
  const errors: HoldingFormErrors = {};

  if (!payload.symbol.trim()) {
    errors.symbol = "Symbol is required";
  }
  if (!payload.quantity.trim()) {
    errors.quantity = "Quantity is required";
  }
  if (!payload.average_cost.trim()) {
    errors.average_cost = "Average cost is required";
  }

  return errors;
}

function mutationErrorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Holding could not be saved. Try again.";
}

function displayValue(value: string | null | undefined) {
  return value && value.trim() ? value : "-";
}

export default function HoldingsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<HoldingPayload>(emptyForm);
  const [editingHolding, setEditingHolding] = useState<Holding | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [errors, setErrors] = useState<HoldingFormErrors>({});

  const holdingsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["holdings", accessToken],
    queryFn: () => listHoldings(accessToken ?? ""),
  });

  const createMutation = useMutation({
    mutationFn: (payload: HoldingPayload) => createHolding(accessToken ?? "", payload),
    onSuccess: async () => {
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["holdings"] });
    },
    onError: (error) => {
      setErrors({ form: mutationErrorMessage(error) });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      holdingId,
      payload,
    }: {
      holdingId: number;
      payload: HoldingPayload;
    }) => updateHolding(accessToken ?? "", holdingId, payload),
    onSuccess: async () => {
      resetForm();
      await queryClient.invalidateQueries({ queryKey: ["holdings"] });
    },
    onError: (error) => {
      setErrors({ form: mutationErrorMessage(error) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (holdingId: number) => deleteHolding(accessToken ?? "", holdingId),
    onSuccess: async () => {
      setConfirmDeleteId(null);
      await queryClient.invalidateQueries({ queryKey: ["holdings"] });
    },
  });

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const holdings = holdingsQuery.data ?? [];

  function resetForm() {
    setForm(emptyForm);
    setEditingHolding(null);
    setErrors({});
  }

  function updateField<Key extends keyof HoldingPayload>(
    field: Key,
    value: HoldingPayload[Key]
  ) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  function editHolding(holding: Holding) {
    setEditingHolding(holding);
    setForm(payloadFromHolding(holding));
    setErrors({});
  }

  function selectInstrument(result: InstrumentSearchResult) {
    setForm((current) => ({
      ...current,
      symbol: result.symbol,
      name: result.name ?? "",
      exchange: result.exchange ?? "",
      currency: result.currency ?? "",
      asset_class: result.asset_class ?? "",
      sector: result.sector ?? "",
      country: result.country ?? "",
      region: result.region ?? "",
    }));
    setErrors((current) => ({ ...current, symbol: undefined, form: undefined }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = cleanedPayload(form);
    const validationErrors = validateHolding(payload);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    if (editingHolding) {
      updateMutation.mutate({ holdingId: editingHolding.id, payload });
      return;
    }

    createMutation.mutate(payload);
  }

  return (
    <section className="dashboard-page holdings-page" aria-labelledby="holdings-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Positions</p>
          <h1 id="holdings-title">Holdings</h1>
        </div>
      </header>

      <div className="holdings-workspace">
        <section className="holdings-panel" aria-labelledby="holdings-list-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">Manual holdings</p>
              <h2 id="holdings-list-title">Positions</h2>
            </div>
          </div>

          {holdingsQuery.isLoading ? (
            <p className="muted-copy">Loading holdings</p>
          ) : null}

          {holdingsQuery.error ? (
            <p className="form-error">Holdings unavailable</p>
          ) : null}

          {!holdingsQuery.isLoading && !holdingsQuery.error && holdings.length === 0 ? (
            <div className="empty-state">
              <strong>No holdings yet</strong>
              <span>Add a manual position to start building this portfolio.</span>
            </div>
          ) : null}

          {holdings.length > 0 ? (
            <div className="holdings-table-wrap">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Exchange</th>
                    <th>Currency</th>
                    <th>Quantity</th>
                    <th>Average cost</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((holding) => (
                    <tr key={holding.id}>
                      <td data-label="Symbol">
                        <strong>{holding.instrument.symbol.toUpperCase()}</strong>
                      </td>
                      <td data-label="Name">{displayValue(holding.instrument.name)}</td>
                      <td data-label="Exchange">
                        {displayValue(holding.instrument.exchange)}
                      </td>
                      <td data-label="Currency">
                        {holding.instrument.currency?.toUpperCase() ?? "-"}
                      </td>
                      <td data-label="Quantity" className="num">
                        {holding.quantity}
                      </td>
                      <td data-label="Average cost" className="num">
                        {holding.average_cost}
                      </td>
                      <td data-label="Actions">
                        <div className="row-actions">
                          <button
                            aria-label={`Edit ${holding.instrument.symbol}`}
                            className="icon-button"
                            type="button"
                            onClick={() => editHolding(holding)}
                          >
                            <Pencil aria-hidden="true" />
                          </button>
                          {confirmDeleteId === holding.id ? (
                            <>
                              <button
                                aria-label={`Confirm delete ${holding.instrument.symbol}`}
                                className="icon-button icon-button--danger"
                                disabled={deleteMutation.isPending}
                                type="button"
                                onClick={() => deleteMutation.mutate(holding.id)}
                              >
                                <Check aria-hidden="true" />
                              </button>
                              <button
                                aria-label={`Cancel delete ${holding.instrument.symbol}`}
                                className="icon-button"
                                type="button"
                                onClick={() => setConfirmDeleteId(null)}
                              >
                                <X aria-hidden="true" />
                              </button>
                            </>
                          ) : (
                            <button
                              aria-label={`Delete ${holding.instrument.symbol}`}
                              className="icon-button icon-button--danger"
                              type="button"
                              onClick={() => setConfirmDeleteId(holding.id)}
                            >
                              <Trash2 aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>

        <section className="holdings-panel" aria-labelledby="holding-form-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">{editingHolding ? "Edit" : "Create"}</p>
              <h2 id="holding-form-title">
                {editingHolding ? `Edit ${editingHolding.instrument.symbol}` : "Add holding"}
              </h2>
            </div>
            {editingHolding ? (
              <Button variant="ghost" type="button" onClick={resetForm}>
                Cancel
              </Button>
            ) : null}
          </div>

          <form className="holding-form" noValidate onSubmit={handleSubmit}>
            {errors.form ? <p className="form-error">{errors.form}</p> : null}

            <div className="form-grid holdings-form-grid">
              <div className="field">
                <InstrumentSearchInput
                  accessToken={accessToken ?? ""}
                  id="holding-symbol"
                  label="Symbol"
                  value={form.symbol}
                  onChange={(value) => updateField("symbol", value)}
                  onSelect={selectInstrument}
                />
                {errors.symbol ? <span className="field-error">{errors.symbol}</span> : null}
              </div>
              <div className="field">
                <label htmlFor="holding-name">Name</label>
                <input
                  id="holding-name"
                  value={optionalValue(form.name)}
                  onChange={(event) => updateField("name", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-exchange">Exchange</label>
                <input
                  id="holding-exchange"
                  value={optionalValue(form.exchange)}
                  onChange={(event) => updateField("exchange", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-currency">Currency</label>
                <input
                  id="holding-currency"
                  value={optionalValue(form.currency)}
                  onChange={(event) => updateField("currency", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-asset-class">Asset class</label>
                <input
                  id="holding-asset-class"
                  value={optionalValue(form.asset_class)}
                  onChange={(event) => updateField("asset_class", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-sector">Sector</label>
                <input
                  id="holding-sector"
                  value={optionalValue(form.sector)}
                  onChange={(event) => updateField("sector", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-country">Country</label>
                <input
                  id="holding-country"
                  value={optionalValue(form.country)}
                  onChange={(event) => updateField("country", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-region">Region</label>
                <input
                  id="holding-region"
                  value={optionalValue(form.region)}
                  onChange={(event) => updateField("region", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="holding-quantity">Quantity</label>
                <input
                  id="holding-quantity"
                  inputMode="decimal"
                  value={form.quantity}
                  onChange={(event) => updateField("quantity", event.target.value)}
                />
                {errors.quantity ? (
                  <span className="field-error">{errors.quantity}</span>
                ) : null}
              </div>
              <div className="field">
                <label htmlFor="holding-average-cost">Average cost</label>
                <input
                  id="holding-average-cost"
                  inputMode="decimal"
                  value={form.average_cost}
                  onChange={(event) => updateField("average_cost", event.target.value)}
                />
                {errors.average_cost ? (
                  <span className="field-error">{errors.average_cost}</span>
                ) : null}
              </div>
            </div>

            <div className="form-actions">
              <Button disabled={isSaving} icon={Plus} type="submit">
                {isSaving ? "Saving holding" : "Save holding"}
              </Button>
            </div>
          </form>
        </section>
      </div>
    </section>
  );
}
