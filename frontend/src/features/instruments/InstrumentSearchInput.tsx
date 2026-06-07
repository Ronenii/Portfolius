import { useEffect, useId, useRef, useState } from "react";

import { searchInstruments, type InstrumentSearchResult } from "./instrument-search-api";

type InstrumentSearchInputProps = {
  accessToken: string;
  id?: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSelect: (result: InstrumentSearchResult) => void;
};

export default function InstrumentSearchInput({
  accessToken,
  id,
  label,
  value,
  onChange,
  onSelect,
}: InstrumentSearchInputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const listboxId = `${inputId}-results`;
  const [inputValue, setInputValue] = useState(value);
  const [results, setResults] = useState<InstrumentSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const latestQueryRef = useRef("");

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  useEffect(() => {
    const query = inputValue.trim();
    if (!accessToken || query.length < 2) {
      setResults([]);
      setIsSearching(false);
      return;
    }

    latestQueryRef.current = query;
    setIsSearching(true);
    const timeout = window.setTimeout(() => {
      searchInstruments(accessToken, query)
        .then((matches) => {
          if (latestQueryRef.current === query) {
            setResults(matches);
          }
        })
        .catch(() => {
          if (latestQueryRef.current === query) {
            setResults([]);
          }
        })
        .finally(() => {
          if (latestQueryRef.current === query) {
            setIsSearching(false);
          }
        });
    }, 150);

    return () => window.clearTimeout(timeout);
  }, [accessToken, inputValue]);

  function handleChange(nextValue: string) {
    setInputValue(nextValue);
    onChange(nextValue);
  }

  function selectResult(result: InstrumentSearchResult) {
    setInputValue(result.symbol);
    setResults([]);
    onSelect(result);
  }

  return (
    <div className="instrument-search">
      <label htmlFor={inputId}>{label}</label>
      <input
        aria-autocomplete="list"
        aria-controls={results.length > 0 ? listboxId : undefined}
        aria-expanded={results.length > 0}
        autoComplete="off"
        id={inputId}
        role="combobox"
        value={inputValue}
        onChange={(event) => handleChange(event.target.value)}
      />
      {isSearching ? <span className="field-hint">Searching</span> : null}
      {results.length > 0 ? (
        <div className="instrument-results" id={listboxId} role="listbox">
          {results.map((result) => (
            <button
              key={`${result.symbol}-${result.exchange ?? ""}`}
              className="instrument-result"
              role="option"
              type="button"
              onClick={() => selectResult(result)}
            >
              <strong>{result.symbol}</strong>
              <span>{result.name ?? "Unnamed instrument"}</span>
              <small>
                {[result.exchange, result.currency].filter(Boolean).join(" · ")}
              </small>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
