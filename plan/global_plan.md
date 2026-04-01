# Global Project Plan

## Purpose

Complete the project end-to-end from stable filing extraction to retrieval-backed LLM financial analysis, while preserving data quality, provenance, and reproducibility.

## Current Baseline (from README)

- Phase 1 (research): done.
- Phase 2 (extracting data): done (Stage A complete).
- Phase 3 (architecture + database): in progress (Stage B complete; Stage C onward active).
- Phase 4 (UI): intentionally unchanged and out of scope for immediate implementation.

## Guiding Principles

- Keep every computed metric traceable to explicit inputs.
- Never infer missing financial or market values.
- Preserve provenance and run metadata for auditability.
- Only use deterministic transformations and never opaque heuristics.
- Keep output machine-readable first, human-readable second.

## Target End State

A single reliable pipeline:

1. Parse + normalize filing data.
2. Compute statement-based ratios.
3. Enrich with market data.
4. Compute market-aware/valuation ratios.
5. Persist structured + retrieval-friendly data.
6. Run LLM analysis with explicit evidence grounding.

## Delivery Plan

### Stage A - Stabilize Extraction Contract (Complete)

> Detailed plan: [plan/plan_A.md](plan_A.md)
> Extraction contract: [plan/extraction_contract.md](extraction_contract.md)
> Handoff: [plan/stage_a_handoff.md](stage_a_handoff.md)

**Goal:** make parser outputs dependable enough to support all downstream modules.

**Tasks**

1. Keep the extract -> normalize -> map -> validate -> export flow stable.
2. Fix known duplicate-output issues in JSON/markdown exports.
3. Add 1-2 additional benchmark filings to reduce sample bias.
4. Promote evaluation KPIs to mandatory release gate.

**Acceptance Criteria**

- No duplicate canonical metrics in final compressed outputs.
- Extraction KPIs stable across benchmark filings.
- Output format stays backward compatible for existing ratio scripts.

**Primary Areas**

- `pdf_parser/`
- `data_raw/`
- `data_compressed/`

**Status**

- Completed. Stage A outputs are now treated as baseline contract inputs for Stage B+.

---

### Stage B - Canonical Enriched Data Model (Complete)

> Detailed plan: [plan/plan_B.md](plan_B.md)
> Handoff: [plan/stage_b_handoff.md](stage_b_handoff.md)

**Goal:** define a versioned schema that combines filing data, market data, ratios, and provenance.

**Tasks**

1. Define canonical top-level sections:
   - `company_context`
   - `filing_context`
   - `statement_metrics`
   - `market_metrics`
   - `ratios`
   - `provenance`
2. Standardize required field behavior:
   - explicit `status`
   - `missing_fields`
   - `error` where relevant
3. Add schema versioning and compatibility notes.
4. Validate unit consistency (`USD`, `%`, `ratio`) and null semantics.

**Acceptance Criteria**

- One documented schema contract used by all downstream stages.
- Existing ratio output structure remains compatible.

**Primary Areas**

- `financial_ratios/models/`
- `financial_ratios/scripts/`

**Status**

- Completed. Canonical schema envelope and compatibility shims are in place; Stage C can build directly on `market_metrics` stubs.

---

### Stage C - Market Data Enrichment

> Detailed plan: [plan/plan_C.md](plan_C.md)

**Goal:** add market context per ticker/period via Python data source integration (Yahoo Finance first).

**Tasks**

1. Build market data fetch module for core fields:
   - `share_price`
   - `shares_outstanding`
   - `market_cap`
   - `total_debt`
   - `cash_and_cash_equivalents` (reconciled with filing field)
2. Add fetch metadata:
   - source provider
   - fetch timestamp
   - as-of date
   - availability status
3. Implement graceful failure behavior:
   - mark unavailable fields explicitly
   - do not block entire pipeline if market data is missing
4. Merge market block into aggregated company JSON.

**Acceptance Criteria**

- Market metrics are present when available, explicitly missing when unavailable.
- No silent fallbacks or guessed values.

**Primary Areas**

- `financial_ratios/scripts/aggregator.py`
- new market enrichment module under `financial_ratios/scripts/`

---

### Stage D - Extended Ratio Computation

> Detailed plan: [plan/plan_D.md](plan_D.md)

**Goal:** compute additional market-aware ratios using enriched data.

**Tasks**

1. Add initial market-based ratios:
   - `price_to_earnings`
   - `price_to_sales`
   - `price_to_book`
   - `enterprise_value_to_sales`
   - `enterprise_value_to_ebit`
2. Add formula safeguards:
   - division by zero
   - negative/invalid denominator policy
   - stale market snapshot warning
3. Preserve ratio output shape:
   - `value`, `unit`, `description`, `inputs`, `status`, `missing_fields`, `error`
4. Add tests for success and failure/missing-input paths.

**Acceptance Criteria**

- Extended ratios are deterministic and transparent.
- Missing inputs produce `missing_inputs` status, not fabricated outputs.

**Primary Areas**

- `financial_ratios/models/ratio_definitions.py`
- `financial_ratios/scripts/ratio_calculation.py`
- `financial_ratios/scripts/ratio_enricher.py`

---

### Stage E - Persistence and Retrieval Layer

> Detailed plan: [plan/plan_E.md](plan_E.md)

**Goal:** persist enriched financial records for both exact queries and semantic retrieval.

**Tasks**

1. Implement two-layer persistence strategy:
   - structured record store for numeric/factual data
   - vector retrieval store for semantic context chunks
2. Define indexing keys:
   - `ticker`, `period_ending`, `report_type`, `run_id`
3. Define retrieval metadata:
   - source type (`filing`, `market`, `ratio`, `analysis`)
   - statement type
   - field names included
   - timestamps and versions
4. Implement write policy:
   - immutable raw records
   - curated upsert when quality gates pass
5. Add read-back smoke tests by ticker/period.

**Acceptance Criteria**

- Successful write/read path for at least one full company record.
- Retrieval can return both metric facts and supporting context chunks.

**Primary Areas**

- persistence module (new)
- integration points in `financial_ratios/` and `pdf_parser/`

---

### Stage F - LLM Analysis Pipeline

> Detailed plan: [plan/plan_F.md](plan_F.md)

**Goal:** generate grounded financial analysis from retrieved evidence.

**Tasks**

1. Build retrieval-first analysis orchestration.
2. Define output sections:
   - business snapshot
   - profitability
   - liquidity/solvency
   - efficiency/growth
   - valuation
   - risk signals
   - confidence and unknowns
3. Enforce grounding policy:
   - each conclusion references retrieved metrics/chunks
   - unsupported claims are disallowed
4. Produce structured analysis output (JSON) and optional markdown narrative.

**Acceptance Criteria**

- Each major conclusion has evidence references.
- Missing data is explicitly disclosed in output.

**Primary Areas**

- analysis orchestration module (new)
- retrieval integration layer (new)

---

### Stage G - End-to-End Integration and Release Gate

> Detailed plan: [plan/plan_G.md](plan_G.md)

**Goal:** prove reliable pipeline behavior on multiple companies/periods.

**Tasks**

1. Run full pipeline:
   - PDF -> extraction -> ratios -> market enrichment -> persistence -> LLM analysis
2. Add regression suite for:
   - extraction KPIs
   - ratio snapshots
   - retrieval integrity
   - analysis schema + citation checks
3. Validate across at least:
   - AAPL and DUOL
   - annual + one quarterly period each
4. Prepare release checklist and known-limitations log.

**Acceptance Criteria**

- End-to-end runs pass for required benchmark set.
- No critical schema drift or uncited analysis claims.

## Dependency Graph

1. Stage A is complete.
2. Stage B is complete and built on Stage A.
3. Stage C depends on Stage B.
4. Stage D depends on Stage B and Stage C.
5. Stage E depends on Stage B (full usefulness after Stage D).
6. Stage F depends on Stage D and Stage E.
7. Stage G depends on Stages A through F.

## Suggested Milestones

1. M1: Stage A complete (stable extraction contract). Done.
2. M2: Stage B complete (canonical enriched schema). Done.
3. M3: Stage C complete (market enrichment online).
4. M4: Stage D complete (extended ratio engine).
5. M5: Stage E complete (persistence + retrieval online).
6. M6: Stage F complete (grounded analysis output).
7. M7: Stage G complete (release candidate).

## Risks and Mitigations

- Risk: market API gaps or intermittent failures.
  - Mitigation: explicit source status + non-blocking pipeline behavior.
- Risk: schema drift between modules.
  - Mitigation: versioned schema and validation tests in CI.
- Risk: LLM unsupported conclusions.
  - Mitigation: mandatory evidence references and output validation.
- Risk: quality regression when adding new filings.
  - Mitigation: benchmark expansion + strict KPI gate.

## Definition of Done (Project)

- Stable extraction and cleanup with benchmark-backed KPIs.
- Market-enriched canonical company records.
- Statement + market ratio set with transparent missing-input behavior.
- Retrieval-ready persistence with provenance metadata.
- LLM analysis outputs that are structured, evidence-backed, and auditable.
- Repeatable end-to-end execution on multiple companies and periods.

## Immediate Next Actions (Execution Order)

1. Implement Stage C market fetch + merge path.
2. Extend Stage D ratio definitions and tests.
3. Stand up Stage E persistence adapter and read-back tests.
4. Implement Stage F analysis orchestration with grounding checks.
5. Run Stage G full-pipeline validation and release checklist.
