import { describe, expect, it } from "vitest";

import { buildImportRows, parseCsv } from "./csv";

describe("parseCsv", () => {
  it("handles a quoted field containing a comma", () => {
    const result = parseCsv('a,"b,c",d\n1,2,3\n');
    expect(result).toEqual([
      ["a", "b,c", "d"],
      ["1", "2", "3"],
    ]);
  });

  it("unescapes a doubled quote inside a quoted field", () => {
    const result = parseCsv('a,"she said ""hi""",c\n');
    expect(result).toEqual([["a", 'she said "hi"', "c"]]);
  });

  it("skips fully blank lines", () => {
    const result = parseCsv("a,b\n\nc,d\n");
    expect(result).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("does not produce a phantom empty row for a trailing newline", () => {
    const result = parseCsv("a,b\nc,d\n");
    expect(result).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("handles CRLF line endings", () => {
    const result = parseCsv("a,b\r\nc,d\r\n");
    expect(result).toEqual([
      ["a", "b"],
      ["c", "d"],
    ]);
  });

  it("trims whitespace on unquoted cells but preserves quoted content verbatim", () => {
    const result = parseCsv('  a  ,"  b  "\n');
    expect(result).toEqual([["a", "  b  "]]);
  });
});

describe("buildImportRows", () => {
  const today = "2026-07-17";

  it("maps a transactions template directly", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,10,145.20,1.50,Initial buy\n";

    const result = buildImportRows(text, today);

    expect(result.headerError).toBeNull();
    expect(result.template).toBe("transactions");
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]).toEqual({
      line: 2,
      row: {
        symbol: "AAPL",
        action: "buy",
        quantity: "10",
        price: "145.20",
        fees: "1.50",
        trade_date: "2026-01-05",
        notes: "Initial buy",
      },
      error: null,
    });
  });

  it("defaults missing fees to '0' and missing notes to null", () => {
    const text =
      "trade_date,action,symbol,quantity,price\n" + "2026-01-05,sell,TSLA,3,180\n";

    const result = buildImportRows(text, today);

    expect(result.headerError).toBeNull();
    expect(result.template).toBe("transactions");
    expect(result.rows[0].row.fees).toBe("0");
    expect(result.rows[0].row.notes).toBeNull();
    expect(result.rows[0].error).toBeNull();
  });

  it("maps a positions template to an opening-balance buy", () => {
    const text = "symbol,quantity,average_cost\n" + "MSFT,5,300.00\n";

    const result = buildImportRows(text, today);

    expect(result.headerError).toBeNull();
    expect(result.template).toBe("positions");
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]).toEqual({
      line: 2,
      row: {
        symbol: "MSFT",
        action: "buy",
        quantity: "5",
        price: "300.00",
        fees: "0",
        trade_date: today,
        notes: null,
      },
      error: null,
    });
  });

  it("is case-insensitive and order-insensitive when matching the header", () => {
    const text = "Symbol,Average_Cost,Quantity\n" + "GOOG,100,2\n";

    const result = buildImportRows(text, today);

    expect(result.headerError).toBeNull();
    expect(result.template).toBe("positions");
    expect(result.rows[0].row.symbol).toBe("GOOG");
    expect(result.rows[0].row.price).toBe("100");
  });

  it("sets a headerError when the header matches neither template", () => {
    const text = "foo,bar,baz\n1,2,3\n";

    const result = buildImportRows(text, today);

    expect(result.headerError).not.toBeNull();
    expect(result.rows).toEqual([]);
  });

  it("flags a row with a non-numeric quantity as invalid", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,abc,145.20,0,\n";

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).not.toBeNull();
  });

  it("flags a row with an empty symbol as invalid", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,,10,145.20,0,\n";

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).not.toBeNull();
  });

  it("flags a row with a bad action as invalid", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,hold,AAPL,10,145.20,0,\n";

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).not.toBeNull();
  });

  it("flags a row with a negative price as invalid", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,buy,AAPL,10,-5,0,\n";

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).not.toBeNull();
  });

  it("flags a row with an invalid trade_date as invalid", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "not-a-date,buy,AAPL,10,145.20,0,\n";

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).not.toBeNull();
  });

  it("rejects a quantity containing a stray comma like '1,2'", () => {
    const text = "symbol,quantity,average_cost\n" + 'MSFT,"1,2",300.00\n';

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).not.toBeNull();
  });

  it("marks a fully valid row as error === null", () => {
    const text =
      "trade_date,action,symbol,quantity,price,fees,notes\n" +
      "2026-01-05,sell,TSLA,3,180.00,0,\n";

    const result = buildImportRows(text, today);

    expect(result.rows[0].error).toBeNull();
  });
});
