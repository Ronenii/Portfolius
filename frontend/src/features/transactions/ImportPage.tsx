import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type ChangeEvent, type DragEvent, useState } from "react";
import { Link } from "react-router-dom";

import Button from "../../components/ui/Button";
import { ApiError } from "../../lib/api";
import { buildImportRows, type ImportRow, type ParsedRow, type ParseResult } from "../../lib/csv";
import { useAuth } from "../auth/AuthContext";
import { importTransactions, type ImportResultRow } from "./transactions-api";

const TRANSACTIONS_TEMPLATE_CSV =
  "trade_date,action,symbol,quantity,price,fees,notes\n" +
  "2026-01-15,buy,AAPL,10,150.00,1.00,Initial purchase\n";

const POSITIONS_TEMPLATE_CSV = "symbol,quantity,average_cost\n" + "AAPL,10,150.00\n";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function downloadCsv(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function readFileText(file: File): Promise<string> {
  if (typeof file.text === "function") {
    return file.text();
  }
  // Fallback for environments (e.g. this project's jsdom test setup) where
  // Blob.prototype.text is unavailable on File instances.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Could not read file"));
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.readAsText(file);
  });
}

function mutationErrorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Import failed. Check the file and try again.";
}

export default function ImportPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const importMutation = useMutation({
    mutationFn: (rows: ImportRow[]) => importTransactions(accessToken ?? "", rows),
    onSuccess: async () => {
      await invalidateImportQueries();
    },
  });

  async function invalidateImportQueries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["transactions"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolio-snapshot"] }),
      queryClient.invalidateQueries({ queryKey: ["holdings"] }),
      queryClient.invalidateQueries({ queryKey: ["portfolio-breakdowns"] }),
    ]);
  }

  async function loadFile(file: File) {
    const text = await readFileText(file);
    setParseResult(buildImportRows(text, today()));
    setFileName(file.name);
    importMutation.reset();
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) {
      void loadFile(file);
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) {
      void loadFile(file);
    }
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
  }

  function handleImport() {
    // The backend import is not idempotent (one create_transaction per row, no
    // dedup), so re-submitting the same parsed file would double the
    // transactions and the derived holding. Block a re-import until a fresh
    // file is loaded (which calls importMutation.reset()).
    if (!parseResult || importMutation.isSuccess) {
      return;
    }
    const validRows = parseResult.rows
      .filter((parsedRow) => parsedRow.error === null)
      .map((parsedRow) => parsedRow.row);
    importMutation.mutate(validRows);
  }

  const validRows: ParsedRow[] = parseResult
    ? parseResult.rows.filter((parsedRow) => parsedRow.error === null)
    : [];
  const invalidCount = parseResult ? parseResult.rows.length - validRows.length : 0;
  const results = importMutation.data?.results ?? null;

  const resultsByRow = new Map<ParsedRow, ImportResultRow>();
  if (results) {
    validRows.forEach((parsedRow, index) => {
      const result = results[index];
      if (result) {
        resultsByRow.set(parsedRow, result);
      }
    });
  }

  const importedCount = results
    ? results.filter((result) => result.status === "imported").length
    : 0;
  const failedCount = results
    ? results.filter((result) => result.status === "failed").length + invalidCount
    : 0;

  function statusForRow(parsedRow: ParsedRow): { text: string; failed: boolean } {
    if (parsedRow.error) {
      return { text: `Skipped: ${parsedRow.error}`, failed: true };
    }
    const result = resultsByRow.get(parsedRow);
    if (!result) {
      return { text: "Ready to import", failed: false };
    }
    return result.status === "imported"
      ? { text: "Imported", failed: false }
      : { text: `Failed: ${result.reason ?? "Unknown error"}`, failed: true };
  }

  return (
    <section className="dashboard-page holdings-page" aria-labelledby="import-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Ledger</p>
          <h1 id="import-title">Import CSV</h1>
        </div>
        <Link to="/transactions">Back to transactions</Link>
      </header>

      <div className="holdings-workspace">
        <section className="holdings-panel" aria-labelledby="import-upload-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">Upload</p>
              <h2 id="import-upload-title">Choose a CSV file</h2>
            </div>
          </div>

          <p className="field-hint">
            Accepts a transactions template (trade_date,action,symbol,quantity,price,fees,notes)
            or a positions template (symbol,quantity,average_cost) for opening balances. Rows
            with a non-numeric quantity/price/fees or an invalid trade date are skipped locally
            and never sent, so one bad row can&apos;t block the rest of the import.
          </p>

          <div className="import-dropzone" onDragOver={handleDragOver} onDrop={handleDrop}>
            <label htmlFor="import-file-input">
              Drag and drop a CSV file here, or choose a file
            </label>
            <input
              accept=".csv,text/csv"
              id="import-file-input"
              type="file"
              onChange={handleFileInputChange}
            />
            {fileName ? <span className="field-hint">Loaded {fileName}</span> : null}
          </div>

          <div className="form-actions">
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                downloadCsv("portfolius-transactions-template.csv", TRANSACTIONS_TEMPLATE_CSV)
              }
            >
              Download transactions template
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                downloadCsv("portfolius-positions-template.csv", POSITIONS_TEMPLATE_CSV)
              }
            >
              Download positions template
            </Button>
          </div>

          {parseResult?.headerError ? (
            <p className="form-error">{parseResult.headerError}</p>
          ) : null}
        </section>

        {parseResult && !parseResult.headerError ? (
          <section className="holdings-panel" aria-labelledby="import-preview-title">
            <div className="panel-heading">
              <div>
                <p className="panel-label">Preview</p>
                <h2 id="import-preview-title">
                  {parseResult.rows.length} row
                  {parseResult.rows.length === 1 ? "" : "s"} detected
                </h2>
              </div>
              <Button
                type="button"
                disabled={
                  validRows.length === 0 ||
                  importMutation.isPending ||
                  importMutation.isSuccess
                }
                loading={importMutation.isPending}
                onClick={handleImport}
              >
                {importMutation.isPending
                  ? "Importing"
                  : importMutation.isSuccess
                    ? "Imported — load a new file to import again"
                    : `Import ${validRows.length} valid row${validRows.length === 1 ? "" : "s"}`}
              </Button>
            </div>

            {importMutation.isError ? (
              <p className="form-error">{mutationErrorMessage(importMutation.error)}</p>
            ) : null}

            {results ? (
              <p className="field-hint">
                {importedCount} imported, {failedCount} failed
              </p>
            ) : null}

            <div className="holdings-table-wrap">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>Symbol</th>
                    <th>Action</th>
                    <th className="num-col">Quantity</th>
                    <th className="num-col">Price</th>
                    <th className="num-col">Fees</th>
                    <th>Date</th>
                    <th>Notes</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {parseResult.rows.map((parsedRow) => {
                    const status = statusForRow(parsedRow);
                    return (
                      <tr key={parsedRow.line}>
                        <td data-label="Line">{parsedRow.line}</td>
                        <td data-label="Symbol">{parsedRow.row.symbol}</td>
                        <td data-label="Action">{parsedRow.row.action}</td>
                        <td data-label="Quantity" className="num">
                          {parsedRow.row.quantity}
                        </td>
                        <td data-label="Price" className="num">
                          {parsedRow.row.price}
                        </td>
                        <td data-label="Fees" className="num">
                          {parsedRow.row.fees}
                        </td>
                        <td data-label="Date">{parsedRow.row.trade_date}</td>
                        <td data-label="Notes">{parsedRow.row.notes ?? "-"}</td>
                        <td data-label="Status">
                          <span className={status.failed ? "form-error" : undefined}>
                            {status.text}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </div>
    </section>
  );
}
