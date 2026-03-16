# Stage C - Market Data Enrichment

## Objective

Stage C adds reliable market context to each filing-derived company record using a provider-first, fallback-safe enrichment workflow. The output must remain deterministic, auditable, and compatible with the Stage B canonical schema, while never fabricating values when market data is unavailable.

## Scope

**Included**
- Market data provider integration (Yahoo Finance first).
- Canonical market field mapping and normalization.
- As-of date alignment with filing period.
- Provider/fetch metadata and quality statuses.
- Non-blocking failure behavior and diagnostics.
- Merge logic into Stage B schema (`market_metrics` section).
- Verification and benchmark checks for AAPL and DUOL.

**Excluded**
- New ratio formulas (Stage D).
- Storage/vector DB write path (Stage E).
- LLM analysis orchestration (Stage F).
- UI work (Phase 4).

## Hard Quality Gates for Stage C Exit

1. Every enriched output includes a `market_metrics` section with explicit status per field.
2. No market field is inferred when provider data is missing.
3. Enrichment step never crashes the full pipeline for recoverable provider failures.
4. Fetch metadata (`provider`, `as_of_date`, `fetched_at`, `source_status`) is always present.
5. Benchmark runs produce deterministic market output snapshots for fixed as-of dates.

## Workstream 0: Bootstrap and Dependency Readiness

**Goal**
Ensure Stage C can start even if financial ratio module files are missing or moved.

**Tasks**
1. Confirm active code locations for:
   - aggregation/orchestration entrypoint,
   - model definitions,
   - output writer.
2. If files are missing, restore minimal Stage B scaffold first:
   - model layer for enriched output envelope,
   - orchestrator that reads statement JSON and writes enriched JSON.
3. Add a small compatibility shim so Stage C works whether market enrichment is called from:
   - existing ratio pipeline entrypoint, or
   - temporary standalone market enricher runner.

**Exit checks**
1. One executable path exists that accepts statement input and emits Stage B-shaped output.
2. Stage C module can be invoked from that path.

## Workstream 1: Canonical Market Field Contract

**Goal**
Define exactly which market fields are required and how each field is represented in `market_metrics`.

**Required MVP market fields**
1. `share_price`
2. `shares_outstanding`
3. `market_cap`
4. `total_debt`
5. `cash_and_cash_equivalents_market`
6. `enterprise_value`

**Per-field structure (uniform contract)**
- `value`: float | null
- `unit`: string (`USD`, `shares`, `ratio` where appropriate)
- `source_field`: provider-native field name used
- `source_status`: `ok` | `not_fetched` | `missing_from_provider` | `provider_error` | `stale`
- `as_of_date`: ISO date
- `fetched_at`: ISO timestamp
- `provider`: string (`yahoo_finance`)
- `notes`: optional diagnostic note

**Field derivation policy**
1. Prefer direct provider fields when available.
2. Compute `market_cap` only when both `share_price` and `shares_outstanding` exist and provider value absent.
3. Compute `enterprise_value` only from explicit components with full input trace:
   - `market_cap + total_debt - cash_and_cash_equivalents_market`.
4. If any required component is missing, set `value = null` and `source_status = missing_from_provider`.

**Exit checks**
1. Contract is fully documented and represented in code model/types.
2. Every field in `market_metrics` uses the same metadata structure.

## Workstream 2: Provider Adapter (Yahoo Finance Primary)

**Goal**
Implement a provider adapter that fetches ticker-level market data and returns normalized raw payload for Stage C mapping.

**Tasks**
1. Build adapter interface:
   - `fetch_market_snapshot(ticker: str, as_of_date: str | None) -> ProviderSnapshot`.
2. Implement Yahoo Finance adapter with robust parsing and null handling.
3. Map known provider keys to internal raw fields:
   - price, shares, market cap, debt, cash, currency, exchange timezone.
4. Add request timeout, retry policy, and categorized error handling:
   - network timeout,
   - invalid ticker,
   - empty payload,
   - transient provider response error.
5. Log provider call diagnostics with sanitized payload summary (no full raw dump by default).

**Operational rules**
1. Hard timeout per request (for example 10s).
2. Max retry attempts (for example 2 retries with backoff).
3. No pipeline abort on recoverable provider errors.

**Exit checks**
1. Adapter returns normalized snapshot object for AAPL and DUOL.
2. Failure modes produce structured error categories, not uncaught exceptions.

## Workstream 3: As-Of Date Alignment and Staleness Logic

**Goal**
Ensure market data is temporally aligned with filing analysis needs.

**Alignment policy (MVP)**
1. Primary: nearest trading day on or after filing `period_ending` within tolerance window.
2. Fallback: nearest trading day before `period_ending` if no forward date available.
3. Staleness threshold: mark stale if abs(as_of_date - target_date) exceeds configured days.

**Tasks**
1. Add date alignment helper:
   - inputs: `period_ending`, optional override date.
   - output: selected `as_of_date`, `staleness_days`, `is_stale`.
2. Apply staleness status per field:
   - if stale, keep value but set `source_status = stale` and include note.
3. Expose alignment behavior as config flags for reproducibility.

**Exit checks**
1. Enrichment output always records chosen `as_of_date`.
2. Stale snapshots are explicitly flagged and auditable.

## Workstream 4: Normalization and Merge into Stage B Envelope

**Goal**
Convert provider snapshot into canonical `market_metrics` and merge without disturbing existing `statement_metrics` and `ratios` shape.

**Tasks**
1. Add mapper from provider snapshot -> canonical market field contract.
2. Enforce unit normalization:
   - currency amounts in USD where possible,
   - shares as raw counts,
   - no mixed unit ambiguity.
3. Merge strategy:
   - preserve all existing Stage B sections unchanged,
   - update only `market_metrics` and related provenance fields.
4. Keep source separation:
   - filing-derived `cash_and_cash_equivalents` remains in `statement_metrics`,
   - market adapter value stored as `cash_and_cash_equivalents_market`.

**Exit checks**
1. Enriched output validates against Stage B schema.
2. Existing ratio section remains byte-shape compatible.
3. No accidental overwrite of statement-derived metrics.

## Workstream 5: Failure Handling and Non-Blocking Behavior

**Goal**
Guarantee reliability when provider data is partial/unavailable.

**Tasks**
1. Define failure taxonomy:
   - `provider_unreachable`,
   - `ticker_not_found`,
   - `malformed_response`,
   - `missing_fields`.
2. On failure:
   - keep pipeline running,
   - emit null market values with explicit `source_status`,
   - add error summary in enrichment diagnostics block.
3. Add configurable strict mode:
   - default `strict = false` for non-blocking behavior,
   - optional strict mode for tests to fail on missing critical fields.

**Exit checks**
1. Full pipeline completes when provider fails.
2. Output clearly distinguishes unavailable vs stale vs not_fetched.

## Workstream 6: Provenance and Auditability

**Goal**
Make each market value traceable and reproducible.

**Tasks**
1. Extend provenance with market enrichment metadata:
   - `market_provider_primary`,
   - `market_fetch_started_at`,
   - `market_fetch_completed_at`,
   - `market_as_of_date`,
   - `market_fetch_verdict`,
   - `market_error_count`.
2. Store provider field mapping trace for each canonical market field.
3. Add enrichment run summary:
   - fetched_field_count,
   - missing_field_count,
   - stale_field_count.

**Exit checks**
1. Every enriched output has reproducible market provenance metadata.
2. Field-level source mapping can be inspected without re-querying provider.

## Workstream 7: Validation and Regression Pack

**Goal**
Validate Stage C correctness and stability across benchmark filings.

**Tests**
1. Unit tests:
   - provider payload normalization,
   - field mapping,
   - enterprise value computation,
   - status assignment rules.
2. Integration tests:
   - AAPL and DUOL enrichment with fixed as-of date.
3. Failure-path tests:
   - provider timeout,
   - missing market_cap,
   - missing shares_outstanding,
   - stale date case.
4. Golden snapshot tests:
   - deterministic output for fixed input + mocked provider responses.

**Exit checks**
1. All Stage C tests pass.
2. Golden snapshots detect unintended schema/value regressions.

## Workstream 8: Handoff to Stage D

**Goal**
Provide Stage D with a stable market input contract for new valuation ratios.

**Tasks**
1. Publish ratio-input readiness matrix mapping market fields -> Stage D formulas.
2. Mark required vs optional fields for each planned ratio.
3. Provide sample enriched payloads:
   - full-data case,
   - partial-data case,
   - provider-failure case.

**Exit checks**
1. Stage D can implement ratio formulas without changing Stage C output format.
2. Missing-input semantics align with existing ratio status conventions.

## Sequencing and Dependencies

1. Step 1: Workstream 0 bootstrap readiness.
2. Step 2: Workstream 1 field contract.
3. Step 3: Workstream 2 provider adapter and Workstream 3 date alignment (parallel).
4. Step 4: Workstream 4 normalization/merge (depends on 1-3).
5. Step 5: Workstream 5 failure handling and Workstream 6 provenance (parallel after 4 baseline wiring).
6. Step 6: Workstream 7 validation/regression (depends on 4-6).
7. Step 7: Workstream 8 handoff package for Stage D.

## Verification Checklist for Stage C Completion

1. Run enrichment for benchmark tickers with fixed as-of date and verify deterministic output.
2. Confirm all required market fields exist with explicit status tags.
3. Confirm no inferred values are produced when provider data is missing.
4. Confirm stage remains non-blocking under simulated provider failures.
5. Confirm provenance includes market provider, timings, and verdict.
6. Validate schema compliance against Stage B validator.
7. Confirm Stage D readiness matrix is complete and consistent.

## Risks and Mitigations

1. Risk: provider field drift or API shape changes.
   - Mitigation: adapter normalization layer + payload contract tests.
2. Risk: stale market snapshots distort valuation analysis.
   - Mitigation: explicit staleness flags and threshold policy.
3. Risk: currency mismatches across global tickers.
   - Mitigation: capture provider currency, convert only when deterministic and logged; otherwise mark status.
4. Risk: missing financial ratio module files block integration.
   - Mitigation: Workstream 0 bootstrap track and temporary standalone enricher entrypoint.
5. Risk: silent overwrite of filing metrics during merge.
   - Mitigation: section-isolated merge policy and snapshot diff checks.

## Deliverables

1. Stage C market field contract and typed model.
2. Yahoo Finance adapter with retry/timeout/error taxonomy.
3. Date alignment and staleness evaluator.
4. Canonical market mapper + merge logic into Stage B envelope.
5. Market provenance and diagnostics block.
6. Regression and failure-path test suite.
7. Stage D handoff matrix and sample enriched payloads.
