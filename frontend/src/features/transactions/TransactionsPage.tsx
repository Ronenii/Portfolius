import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";
import { type FormEvent, useState } from "react";

import Button from "../../components/ui/Button";
import { TrendLoader } from "../../components/ui/TrendLoader";
import { ApiError } from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import InstrumentSearchInput from "../instruments/InstrumentSearchInput";
import type { InstrumentSearchResult } from "../instruments/instrument-search-api";
import {
  createTransaction,
  deleteTransaction,
  listTransactions,
  updateTransaction,
  type Transaction,
  type TransactionPayload,
} from "./transactions-api";

type TransactionFormErrors = Partial<Record<keyof TransactionPayload | "form", string>>;

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function emptyForm(): TransactionPayload {
  return {
    symbol: "",
    name: "",
    exchange: "",
    currency: "",
    asset_class: "",
    sector: "",
    country: "",
    region: "",
    action: "buy",
    quantity: "",
    price: "",
    fees: "0",
    trade_date: today(),
    notes: "",
  };
}

function optionalValue(value: string | null | undefined): string {
  return value ?? "";
}

function payloadFromTransaction(transaction: Transaction): TransactionPayload {
  return {
    symbol: transaction.instrument.symbol,
    name: optionalValue(transaction.instrument.name),
    exchange: optionalValue(transaction.instrument.exchange),
    currency: optionalValue(transaction.instrument.currency),
    asset_class: optionalValue(transaction.instrument.asset_class),
    sector: optionalValue(transaction.instrument.sector),
    country: optionalValue(transaction.instrument.country),
    region: optionalValue(transaction.instrument.region),
    action: transaction.action,
    quantity: transaction.quantity,
    price: transaction.price,
    fees: transaction.fees,
    trade_date: transaction.trade_date,
    notes: optionalValue(transaction.notes),
  };
}

function cleanedPayload(form: TransactionPayload): TransactionPayload {
  return {
    symbol: form.symbol.trim(),
    name: form.name?.trim() || null,
    exchange: form.exchange?.trim() || null,
    currency: form.currency?.trim() || null,
    asset_class: form.asset_class?.trim() || null,
    sector: form.sector?.trim() || null,
    country: form.country?.trim() || null,
    region: form.region?.trim() || null,
    action: form.action,
    quantity: form.quantity.trim(),
    price: form.price.trim(),
    fees: form.fees.trim() || "0",
    trade_date: form.trade_date.trim(),
    notes: form.notes?.trim() || null,
  };
}

function validateTransaction(payload: TransactionPayload): TransactionFormErrors {
  const errors: TransactionFormErrors = {};

  if (!payload.symbol.trim()) {
    errors.symbol = "Symbol is required";
  }
  if (!payload.quantity.trim()) {
    errors.quantity = "Quantity is required";
  }
  if (!payload.price.trim()) {
    errors.price = "Price is required";
  }
  if (!payload.trade_date.trim()) {
    errors.trade_date = "Trade date is required";
  }

  return errors;
}

function mutationErrorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Transaction could not be saved. Try again.";
}

function displayValue(value: string | null | undefined) {
  return value && value.trim() ? value : "-";
}

function formatDecimal(value: string) {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 8,
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

function formatMoney(value: string, currency = "USD") {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    currency,
    style: "currency",
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

export default function TransactionsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TransactionPayload>(emptyForm);
  const [editingTransaction, setEditingTransaction] = useState<Transaction | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [errors, setErrors] = useState<TransactionFormErrors>({});

  const transactionsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["transactions", accessToken],
    queryFn: () => listTransactions(accessToken ?? ""),
  });

  const createMutation = useMutation({
    mutationFn: (payload: TransactionPayload) => createTransaction(accessToken ?? "", payload),
    onSuccess: async () => {
      resetForm();
      await invalidateTransactionQueries();
    },
    onError: (error) => {
      setErrors({ form: mutationErrorMessage(error) });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      transactionId,
      payload,
    }: {
      transactionId: number;
      payload: TransactionPayload;
    }) => updateTransaction(accessToken ?? "", transactionId, payload),
    onSuccess: async () => {
      resetForm();
      await invalidateTransactionQueries();
    },
    onError: (error) => {
      setErrors({ form: mutationErrorMessage(error) });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (transactionId: number) => deleteTransaction(accessToken ?? "", transactionId),
    onSuccess: async () => {
      setConfirmDeleteId(null);
      await invalidateTransactionQueries();
    },
  });

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const transactions = transactionsQuery.data ?? [];

  function resetForm() {
    setForm(emptyForm());
    setEditingTransaction(null);
    setErrors({});
  }

  async function invalidateTransactionQueries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["transactions"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolio-snapshot"] }),
      queryClient.invalidateQueries({ queryKey: ["holdings"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolio-breakdowns"] }),
    ]);
  }

  function updateField<Key extends keyof TransactionPayload>(
    field: Key,
    value: TransactionPayload[Key]
  ) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined, form: undefined }));
  }

  function editTransaction(transaction: Transaction) {
    setEditingTransaction(transaction);
    setForm(payloadFromTransaction(transaction));
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
    const validationErrors = validateTransaction(payload);

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    if (editingTransaction) {
      updateMutation.mutate({ transactionId: editingTransaction.id, payload });
      return;
    }

    createMutation.mutate(payload);
  }

  return (
    <section className="dashboard-page holdings-page" aria-labelledby="transactions-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Ledger</p>
          <h1 id="transactions-title">Transactions</h1>
        </div>
      </header>

      <div className="holdings-workspace">
        <section className="holdings-panel" aria-labelledby="transactions-list-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">Transaction log</p>
              <h2 id="transactions-list-title">All transactions</h2>
            </div>
          </div>

          {transactionsQuery.isLoading ? (
            <TrendLoader label="Loading transactions" />
          ) : null}

          {transactionsQuery.error ? (
            <p className="form-error">Transactions unavailable</p>
          ) : null}

          {!transactionsQuery.isLoading &&
          !transactionsQuery.error &&
          transactions.length === 0 ? (
            <div className="empty-state">
              <strong>No transactions yet</strong>
              <span>Record a buy or sell to start building this ledger.</span>
            </div>
          ) : null}

          {transactions.length > 0 ? (
            <div className="holdings-table-wrap">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Action</th>
                    <th>Symbol</th>
                    <th className="num-col">Quantity</th>
                    <th className="num-col">Price</th>
                    <th className="num-col">Fees</th>
                    <th>Notes</th>
                    <th className="actions-col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td data-label="Date">{transaction.trade_date}</td>
                      <td data-label="Action">
                        {transaction.action === "buy" ? "Buy" : "Sell"}
                      </td>
                      <td data-label="Symbol">
                        <strong>{transaction.instrument.symbol.toUpperCase()}</strong>
                      </td>
                      <td data-label="Quantity" className="num">
                        {formatDecimal(transaction.quantity)}
                      </td>
                      <td data-label="Price" className="num">
                        {formatMoney(transaction.price, transaction.currency)}
                      </td>
                      <td data-label="Fees" className="num">
                        {formatMoney(transaction.fees, transaction.currency)}
                      </td>
                      <td data-label="Notes">{displayValue(transaction.notes)}</td>
                      <td data-label="Actions">
                        <div className="row-actions">
                          <button
                            aria-label={`Edit ${transaction.instrument.symbol}`}
                            className="icon-button"
                            type="button"
                            onClick={() => editTransaction(transaction)}
                          >
                            <Pencil aria-hidden="true" />
                          </button>
                          {confirmDeleteId === transaction.id ? (
                            <>
                              <button
                                aria-label={`Confirm delete ${transaction.instrument.symbol}`}
                                className="icon-button icon-button--danger"
                                disabled={deleteMutation.isPending}
                                type="button"
                                onClick={() => deleteMutation.mutate(transaction.id)}
                              >
                                <Check aria-hidden="true" />
                              </button>
                              <button
                                aria-label={`Cancel delete ${transaction.instrument.symbol}`}
                                className="icon-button"
                                type="button"
                                onClick={() => setConfirmDeleteId(null)}
                              >
                                <X aria-hidden="true" />
                              </button>
                            </>
                          ) : (
                            <button
                              aria-label={`Delete ${transaction.instrument.symbol}`}
                              className="icon-button icon-button--danger"
                              type="button"
                              onClick={() => setConfirmDeleteId(transaction.id)}
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

        <section className="holdings-panel" aria-labelledby="transaction-form-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">{editingTransaction ? "Edit" : "Create"}</p>
              <h2 id="transaction-form-title">
                {editingTransaction
                  ? `Edit ${editingTransaction.instrument.symbol}`
                  : "Add transaction"}
              </h2>
            </div>
            {editingTransaction ? (
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
                  id="transaction-symbol"
                  label="Symbol"
                  value={form.symbol}
                  onChange={(value) => updateField("symbol", value)}
                  onSelect={selectInstrument}
                />
                {errors.symbol ? <span className="field-error">{errors.symbol}</span> : null}
              </div>
              <div className="field">
                <label htmlFor="transaction-name">Name</label>
                <input
                  id="transaction-name"
                  value={optionalValue(form.name)}
                  onChange={(event) => updateField("name", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-exchange">Exchange</label>
                <input
                  id="transaction-exchange"
                  value={optionalValue(form.exchange)}
                  onChange={(event) => updateField("exchange", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-currency">Currency</label>
                <input
                  id="transaction-currency"
                  value={optionalValue(form.currency)}
                  onChange={(event) => updateField("currency", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-asset-class">Asset class</label>
                <input
                  id="transaction-asset-class"
                  value={optionalValue(form.asset_class)}
                  onChange={(event) => updateField("asset_class", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-sector">Sector</label>
                <input
                  id="transaction-sector"
                  value={optionalValue(form.sector)}
                  onChange={(event) => updateField("sector", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-country">Country</label>
                <input
                  id="transaction-country"
                  value={optionalValue(form.country)}
                  onChange={(event) => updateField("country", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-region">Region</label>
                <input
                  id="transaction-region"
                  value={optionalValue(form.region)}
                  onChange={(event) => updateField("region", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-action">Action</label>
                <select
                  id="transaction-action"
                  value={form.action}
                  onChange={(event) =>
                    updateField("action", event.target.value as "buy" | "sell")
                  }
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="transaction-quantity">Quantity</label>
                <input
                  id="transaction-quantity"
                  inputMode="decimal"
                  value={form.quantity}
                  onChange={(event) => updateField("quantity", event.target.value)}
                />
                {errors.quantity ? (
                  <span className="field-error">{errors.quantity}</span>
                ) : null}
              </div>
              <div className="field">
                <label htmlFor="transaction-price">Price</label>
                <input
                  id="transaction-price"
                  inputMode="decimal"
                  value={form.price}
                  onChange={(event) => updateField("price", event.target.value)}
                />
                {errors.price ? <span className="field-error">{errors.price}</span> : null}
              </div>
              <div className="field">
                <label htmlFor="transaction-fees">Fees</label>
                <input
                  id="transaction-fees"
                  inputMode="decimal"
                  value={form.fees}
                  onChange={(event) => updateField("fees", event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="transaction-trade-date">Trade date</label>
                <input
                  id="transaction-trade-date"
                  type="date"
                  value={form.trade_date}
                  onChange={(event) => updateField("trade_date", event.target.value)}
                />
                {errors.trade_date ? (
                  <span className="field-error">{errors.trade_date}</span>
                ) : null}
              </div>
              <div className="field">
                <label htmlFor="transaction-notes">Notes</label>
                <input
                  id="transaction-notes"
                  value={optionalValue(form.notes)}
                  onChange={(event) => updateField("notes", event.target.value)}
                />
              </div>
            </div>

            <div className="form-actions">
              <Button icon={Plus} loading={isSaving} type="submit">
                {isSaving ? "Saving transaction" : "Save transaction"}
              </Button>
            </div>
          </form>
        </section>
      </div>
    </section>
  );
}
