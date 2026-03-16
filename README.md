# Phase 1: research

what am i creating, what tech stack am i using, is it going to work?

status: done

- defined the scope: extract, normalize, and structure financial statement data from annual and quarterly reports
- validated a python-first stack for pdf processing, data cleanup, and modular ratio calculations
- confirmed feasibility with sample filings and baseline output artifacts (.json + .md)

# Phase 2: extracting data

how am i extracting data from pdfs, can i let an ai interpret the data?

status: mostly done

- parse report pdfs into structured intermediate data (statement lines, values, periods, labels)
- normalize labels and map extracted rows into consistent financial statement fields
- run evaluation checks to track extraction quality and catch regressions
- export clean machine-readable outputs for downstream computation
- keep improving edge cases (for example duplicate fields in final json/markdown exports)

# Phase 3: achitecture + database

how am i saving investing principles in a readable manner for ai and how am i using ai agents to connect
this to the given pdf data?

status: in progress (current main focus)

1) market data enrichment
- add a market data extractor (starting with yahoofinance via python)
- ingest key market-linked inputs such as share_price, shares_outstanding, market_cap, total_debt, and cash_and_cash_equivalents
- merge market data into the aggregated company json so statement + market context live together

2) extended financial ratios
- compute additional valuation and market-aware ratios after enrichment (for example p/e, p/s, ev/sales, ev/ebit, and market-cap-based comparisons)
- keep all ratio outputs traceable to explicit input fields
- mark missing-input cases explicitly instead of inferring unknown values

3) persistence layer for llm retrieval
- persist enriched outputs in a retrieval-friendly store, with vector database as the preferred target
- store both structured numeric fields and chunked textual context so an llm can retrieve facts + narrative together
- keep provenance metadata (ticker, period, report type, extraction run metadata, source labels) so analysis is auditable

4) llm analysis workflow
- build a retrieval + analysis pipeline that pulls company-specific numeric and textual evidence
- generate structured analysis sections (profitability, leverage, liquidity, growth, valuation, risk signals)
- require evidence-backed conclusions with explicit field/ratio references and clear unknown/missing-data handling

# Phase 4: UI

how am i letting users upload their data to the app and letting them interact with the analyses
