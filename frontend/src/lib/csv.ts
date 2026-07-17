export type ImportRow = {
  symbol: string;
  action: "buy" | "sell";
  quantity: string;
  price: string;
  fees: string;
  trade_date: string; // ISO yyyy-mm-dd
  notes: string | null;
};

export type ParsedRow = {
  line: number; // 1-based source line for display
  row: ImportRow;
  error: string | null; // client-side validation error, null if valid
};

export type ParseResult = {
  template: "transactions" | "positions";
  rows: ParsedRow[];
  headerError: string | null; // set when header matches neither template
};

const TRANSACTIONS_REQUIRED_COLUMNS = [
  "trade_date",
  "action",
  "symbol",
  "quantity",
  "price",
];
const TRANSACTIONS_OPTIONAL_COLUMNS = ["fees", "notes"];
const POSITIONS_COLUMNS = ["symbol", "quantity", "average_cost"];

const HEADER_ERROR_MESSAGE =
  "Unrecognized header row. Expected either a transactions template " +
  "(trade_date,action,symbol,quantity,price,fees,notes) or a positions " +
  "template (symbol,quantity,average_cost).";

/**
 * A small hand-rolled CSV parser (no dependency). Handles quoted fields
 * (which may contain commas, newlines, and escaped `""` quotes), both `\n`
 * and `\r\n` line endings, skips fully blank lines, and never emits a
 * phantom trailing empty row.
 */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;
  let cellWasQuoted = false;
  let i = 0;
  const length = text.length;

  function endCell() {
    row.push(cellWasQuoted ? cell : cell.trim());
    cell = "";
    cellWasQuoted = false;
  }

  function endRow() {
    endCell();
    const isBlank = row.every((value) => value === "");
    if (!isBlank) {
      rows.push(row);
    }
    row = [];
  }

  while (i < length) {
    const char = text[i];

    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i += 1;
        continue;
      }
      cell += char;
      i += 1;
      continue;
    }

    if (char === '"' && cell === "") {
      inQuotes = true;
      cellWasQuoted = true;
      i += 1;
      continue;
    }

    if (char === ",") {
      endCell();
      i += 1;
      continue;
    }

    if (char === "\r" && text[i + 1] === "\n") {
      endRow();
      i += 2;
      continue;
    }

    if (char === "\n") {
      endRow();
      i += 1;
      continue;
    }

    cell += char;
    i += 1;
  }

  if (cell !== "" || row.length > 0) {
    endRow();
  }

  return rows;
}

function normalizeHeader(header: string[]): string[] {
  return header.map((value) => value.trim().toLowerCase());
}

function detectTemplate(header: string[]): "transactions" | "positions" | null {
  const normalized = normalizeHeader(header);
  const set = new Set(normalized);

  const hasAllRequiredTransactionColumns = TRANSACTIONS_REQUIRED_COLUMNS.every(
    (column) => set.has(column)
  );
  const allowedTransactionColumns = new Set([
    ...TRANSACTIONS_REQUIRED_COLUMNS,
    ...TRANSACTIONS_OPTIONAL_COLUMNS,
  ]);
  const onlyAllowedTransactionColumns = normalized.every((column) =>
    allowedTransactionColumns.has(column)
  );

  if (hasAllRequiredTransactionColumns && onlyAllowedTransactionColumns) {
    return "transactions";
  }

  const hasExactlyPositionsColumns =
    normalized.length === POSITIONS_COLUMNS.length &&
    POSITIONS_COLUMNS.every((column) => set.has(column));

  if (hasExactlyPositionsColumns) {
    return "positions";
  }

  return null;
}

function columnIndex(header: string[], name: string): number {
  return normalizeHeader(header).indexOf(name);
}

function cellAt(cells: string[], index: number): string {
  return index >= 0 && index < cells.length ? cells[index] : "";
}

function mapTransactionsRow(cells: string[], header: string[]): ImportRow {
  const symbolIndex = columnIndex(header, "symbol");
  const actionIndex = columnIndex(header, "action");
  const quantityIndex = columnIndex(header, "quantity");
  const priceIndex = columnIndex(header, "price");
  const feesIndex = columnIndex(header, "fees");
  const notesIndex = columnIndex(header, "notes");
  const tradeDateIndex = columnIndex(header, "trade_date");

  const fees = cellAt(cells, feesIndex).trim();
  const notes = cellAt(cells, notesIndex).trim();

  return {
    symbol: cellAt(cells, symbolIndex).trim(),
    action: cellAt(cells, actionIndex).trim().toLowerCase() as ImportRow["action"],
    quantity: cellAt(cells, quantityIndex).trim(),
    price: cellAt(cells, priceIndex).trim(),
    fees: fees === "" ? "0" : fees,
    trade_date: cellAt(cells, tradeDateIndex).trim(),
    notes: notes === "" ? null : notes,
  };
}

function mapPositionsRow(cells: string[], header: string[], today: string): ImportRow {
  const symbolIndex = columnIndex(header, "symbol");
  const quantityIndex = columnIndex(header, "quantity");
  const averageCostIndex = columnIndex(header, "average_cost");

  return {
    symbol: cellAt(cells, symbolIndex).trim(),
    action: "buy",
    quantity: cellAt(cells, quantityIndex).trim(),
    price: cellAt(cells, averageCostIndex).trim(),
    fees: "0",
    trade_date: today,
    notes: null,
  };
}

const NUMBER_PATTERN = /^-?(\d+(\.\d+)?|\.\d+)$/;

function isValidNumber(value: string, { allowZero }: { allowZero: boolean }): boolean {
  const trimmed = value.trim();
  if (trimmed === "" || !NUMBER_PATTERN.test(trimmed)) {
    return false;
  }
  const numericValue = Number(trimmed);
  if (!Number.isFinite(numericValue)) {
    return false;
  }
  return allowZero ? numericValue >= 0 : numericValue > 0;
}

function isValidIsoDate(value: string): boolean {
  const trimmed = value.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    return false;
  }
  const [year, month, day] = trimmed.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

function validateRow(row: ImportRow, template: "transactions" | "positions"): string | null {
  if (!row.symbol.trim()) {
    return "Symbol is required.";
  }
  if (template === "transactions" && row.action !== "buy" && row.action !== "sell") {
    return "Action must be \"buy\" or \"sell\".";
  }
  if (!isValidNumber(row.quantity, { allowZero: false })) {
    return "Quantity must be a number greater than 0.";
  }
  if (!isValidNumber(row.price, { allowZero: true })) {
    return "Price must be a number 0 or greater.";
  }
  if (!isValidNumber(row.fees, { allowZero: true })) {
    return "Fees must be a number 0 or greater.";
  }
  if (!isValidIsoDate(row.trade_date)) {
    return "Trade date must be a valid date (yyyy-mm-dd).";
  }
  return null;
}

export function buildImportRows(text: string, today: string): ParseResult {
  const allRows = parseCsv(text);

  if (allRows.length === 0) {
    return {
      template: "transactions",
      rows: [],
      headerError: "The CSV file is empty.",
    };
  }

  const [header, ...dataRows] = allRows;
  const template = detectTemplate(header);

  if (!template) {
    return {
      template: "transactions",
      rows: [],
      headerError: HEADER_ERROR_MESSAGE,
    };
  }

  const rows: ParsedRow[] = dataRows.map((cells, index) => {
    const row =
      template === "transactions"
        ? mapTransactionsRow(cells, header)
        : mapPositionsRow(cells, header, today);
    return {
      line: index + 2,
      row,
      error: validateRow(row, template),
    };
  });

  return { template, rows, headerError: null };
}
