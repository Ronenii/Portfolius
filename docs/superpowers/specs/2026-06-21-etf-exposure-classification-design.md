# ETF Exposure Classification Design

## Goal

Classify ETFs by the geography and sector they invest in rather than by the
location of their exchange listing. A U.S.-listed country ETF must therefore
retain its U.S. exchange metadata while reporting the underlying exposure:

- INDA: country `India`, region `Asia ex-Japan`
- EWJ: country `Japan`, region `Japan`
- MCHI: country `China`, region `Asia ex-Japan`

The classification must work for ETF families, not only a catalog of known
symbols.

## Scope

This change will:

- infer ETF country, region, and fallback sector from fund names and provider
  categories;
- normalize inferred countries to full display names;
- distinguish `Japan`, `Asia ex-Japan`, and `Asia Pacific`;
- preserve higher-quality provider data such as sector holdings weights;
- correct existing stored INDA metadata during deployment;
- add regression coverage for geography, precedence, sector aliases, and
  false-positive boundaries.

It will not introduce a security-master dependency, model constituent-level
country weights, or assign a single country to genuinely multi-country funds.

## Classification Model

ETF geography inference returns one structured exposure:

```python
EtfGeography(country: str | None, region: str | None)
```

Country and region are inferred together so they cannot contradict each other.
A country-focused ETF receives both values. A multi-country regional ETF
receives only a region.

Representative mappings:

| Fund exposure | Country | Region |
| --- | --- | --- |
| India | India | Asia ex-Japan |
| Japan | Japan | Japan |
| China | China | Asia ex-Japan |
| South Korea | South Korea | Asia ex-Japan |
| Taiwan | Taiwan | Asia ex-Japan |
| Australia | Australia | Asia Pacific |
| Brazil | Brazil | Latin America |
| Mexico | Mexico | Latin America |
| Israel | Israel | Middle East |
| South Africa | South Africa | Africa |
| United States | United States | North America |
| Canada | Canada | North America |
| United Kingdom | United Kingdom | Europe |

Country inference will cover common investable markets across:

- North America;
- Latin America;
- Europe;
- Asia ex-Japan;
- Japan;
- Asia Pacific;
- Middle East;
- Africa.

Aliases will include common fund-name forms such as `U.S.`, `USA`, `UK`,
`Korea`, and `Türkiye`, while outputs use full display names.

## Precedence

Inference uses most-specific phrases before broad keywords:

1. explicit exclusions and composite phrases, including `Global ex-US`,
   `Developed ex-US`, `Asia ex-Japan`, and `Pacific ex-Japan`;
2. broad multi-country regions, including `Asia Pacific`, `Europe`,
   `Latin America`, `Middle East`, and `Africa`;
3. specific countries;
4. broad market groups, including `Emerging Markets`, `Developed Markets`,
   and `Global`;
5. existing provider metadata as fallback.

Explicit phrases prevent broad substrings from winning incorrectly. For
example, `Asia Pacific ex-Japan` must not become `Asia Pacific`, and `Global
ex-US` must not become `Global`.

Country-focused funds use their country-derived region even when the primary
provider reports the U.S. listing country. Multi-country funds leave country
unset rather than inventing one.

## Matching Rules

Keywords are matched as normalized words or phrases, not arbitrary substrings.
Normalization will be case-insensitive and collapse punctuation and
whitespace. This avoids false positives such as matching `US` inside another
word.

The classifier consumes the combined ETF name and provider category. Name and
category are treated as exposure hints; ticker symbols are not used as the
primary classification mechanism.

## Sector Fallback

Provider holdings weights remain authoritative:

- when yfinance supplies usable sector weights, the existing dominant-sector
  calculation is retained;
- when weights are present but no sector dominates, the result remains
  `Diversified ETF`;
- only when weights are unavailable will name/category aliases infer a sector.

Fallback aliases will cover the standard sector set already used by the
application:

- Basic Materials
- Communication Services
- Consumer Cyclical
- Consumer Defensive
- Energy
- Financial Services
- Healthcare
- Industrials
- Real Estate
- Technology
- Utilities

Common ETF wording such as `semiconductor`, `biotech`, `banks`, `clean energy`,
`consumer staples`, `REIT`, and `software` will map to those canonical labels.
Names indicating broad, total-market, dividend, factor, bond, commodity, or
multi-sector exposure will not be forced into a sector.

## Provider Integration

`YFinanceEtfProfileClient` and `AlphaVantageEtfProfileClient` will use the
shared structured classifier. The composite lookup will prefer inferred ETF
exposure over primary-provider listing geography while preserving exchange,
currency, and other listing metadata.

The FMP country-to-region mapping for ordinary stocks and ADRs remains
separate. This work changes ETF exposure semantics only.

## Stored Metadata Correction

The existing INDA data migration will set:

- `country = 'India'`;
- `region = 'Asia ex-Japan'`.

The update will target INDA rows carrying the known incorrect listing-derived
geography. It will not overwrite unrelated symbols or arbitrary user-edited
regions.

Future ETF refreshes will receive the corrected country and region directly
from the classifier.

## Testing

Table-driven unit tests will cover:

- representative countries in every supported broad region;
- `Japan`, `Asia ex-Japan`, and `Asia Pacific`;
- explicit exclusion and broad-region precedence;
- full-name country normalization;
- multi-country funds leaving country unset;
- every canonical fallback sector and representative aliases;
- sector-weight precedence over name inference;
- punctuation, casing, whitespace, and substring false positives;
- composite-provider behavior where U.S. listing geography is overridden;
- migration of existing INDA metadata.

The backend test suite and Ruff checks must remain green.

## Error and Unknown Handling

Unknown geography or sector remains `None`; the portfolio UI will continue to
show it as unclassified. The classifier will not guess from exchange, currency,
or ticker when the fund name/category lacks a reliable exposure signal.
