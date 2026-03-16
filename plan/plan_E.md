# Stage E - Persistence and Retrieval Layer

## Objective

Stage E establishes a production-ready persistence layer that stores enriched company records for both exact analytical queries and semantic retrieval. The design must preserve provenance, support deterministic read-back, and prepare clean inputs for Stage F analysis.

## Scope

**Included**

- Two-layer storage architecture:
  - structured store for canonical numeric/factual records
  - vector store for semantic retrieval chunks
- Record keys, indexes, and metadata contracts.
- Write policy for immutable raw runs and curated upserts.
- Retrieval APIs and read-back behavior.
- Validation, smoke tests, and operational guardrails.

**Excluded**

- Market enrichment logic (Stage C).
- Ratio computation logic (Stage D).
- LLM generation/prompting/orchestration (Stage F).
- UI workflow integration (Phase 4).

## Hard Quality Gates for Stage E Exit

1. End-to-end write/read succeeds for at least one full company record.
2. Structured and vector layers both retain provenance metadata required for auditability.
3. Curated upsert policy only accepts records passing quality gates.
4. Retrieval returns both exact metrics and relevant semantic chunks for the same company-period query.
5. All persistence operations are deterministic and idempotent for repeated identical runs.

## Workstream 0: Bootstrap and Storage Readiness

**Goal**
Ensure Stage E can start regardless of current repository drift or missing integration modules.

**Tasks**

1. Confirm active pipeline outputs to persist:
   - Stage B envelope shape,
   - Stage C market section,
   - Stage D ratio section.
2. Create persistence module skeleton if missing:
   - storage interface,
   - structured repository implementation,
   - vector repository implementation,
   - persistence orchestrator entrypoint.
3. Add compatibility adapter for legacy flat payloads so migration can proceed incrementally.

**Exit checks**

1. A persistence entrypoint exists that accepts enriched payload JSON.
2. Entry point can run in dry-run mode without writing data.

## Workstream 1: Canonical Persistence Data Model

**Goal**
Define how enriched payloads are persisted across raw, curated, and retrieval layers.

**Collections / tables (logical model)**

1. `filings_raw`
   - immutable write-once records for every pipeline run.
2. `filings_curated`
   - latest accepted record per `(ticker, period_ending, report_type)`.
3. `evaluations`
   - quality gate outcomes, mismatch diagnostics, and threshold context.
4. `retrieval_chunks`
   - semantic chunks + embeddings + metadata references.

**Core persisted sections**

- `company_context`
- `filing_context`
- `statement_metrics`
- `market_metrics`
- `ratios`
- `provenance`

**Tasks**

1. Define strict persisted schema for each logical collection.
2. Add schema versioning fields to every persisted document.
3. Add document-level hashes for idempotency and dedupe checks.

**Exit checks**

1. Model definitions are documented and validated in code.
2. All required Stage B-D sections are mapped without loss.

## Workstream 2: Keys, Indexes, and Lookup Strategy

**Goal**
Enable fast exact lookups and traceable history queries.

**Required keys and indexes**

1. Primary uniqueness key:
   - `(ticker, period_ending, report_type, source_pdf_sha256, pipeline_version)`
2. Operational indexes:
   - `run_id`
   - `extracted_at`
   - `source_engine_effective`
   - `schema_version`
3. Query indexes for analyst-facing retrieval:
   - `ticker`
   - `period_ending`
   - `report_type`
   - ratio status buckets (`ok`, `missing_inputs`, `invalid_denominator`)

**Tasks**

1. Implement index creation/migration routines.
2. Add index health check command.
3. Ensure writes fail fast with clear diagnostics on unique-key conflicts.

**Exit checks**

1. Exact query by `(ticker, period_ending, report_type)` returns deterministic latest record.
2. Historical query by `run_id` returns immutable raw record.

## Workstream 3: Write Policy and Curation Rules

**Goal**
Protect curated quality while retaining full raw audit history.

**Write policy**

1. Always write to `filings_raw` if payload is structurally valid.
2. Write to `filings_curated` only if quality gates pass:
   - extraction KPIs above thresholds,
   - schema validation passes,
   - no blocking errors in ratios.
3. If gates fail:
   - keep raw + evaluation,
   - set `review_required = true`,
   - skip curated upsert.
4. Upsert strategy for curated:
   - replace only when incoming run passes and is newer or higher-quality per policy.

**Tasks**

1. Implement gate evaluator for persistence-time decisions.
2. Add deterministic conflict resolution policy for competing candidate records.
3. Persist rejection reason list when curated write is skipped.

**Exit checks**

1. Failed records never overwrite curated state.
2. Accepted records update curated state predictably.

## Workstream 4: Vectorization and Chunking Strategy

**Goal**
Store semantic retrieval content aligned with financial evidence and metadata traceability.

**Chunk sources**

1. filing narrative text (`.md` outputs)
2. selected statement/market/ratio summaries generated from structured payload
3. optional evaluation diagnostics snippets

**Chunk metadata contract**

- `chunk_id`
- `ticker`
- `period_ending`
- `report_type`
- `run_id`
- `source_type` (`filing`, `market`, `ratio`, `analysis_seed`)
- `statement_type` (if applicable)
- `field_names` (list)
- `schema_version`
- `embedding_model`
- `created_at`

**Tasks**

1. Define deterministic chunking policy:
   - chunk size,
   - overlap,
   - section-aware splitting for statements and narrative.
2. Define embedding adapter interface with provider-agnostic design.
3. Store embedding vectors and text together with full metadata.
4. Add optional re-embedding workflow for model upgrades.

**Exit checks**

1. Retrieval chunks are reproducible from same source input.
2. Each chunk links back to source record via run and period metadata.

## Workstream 5: Retrieval API and Query Semantics

**Goal**
Provide consistent retrieval behavior for Stage F and manual validation.

**Required retrieval paths**

1. Exact structured lookup:
   - by `(ticker, period_ending, report_type)`.
2. Semantic retrieval:
   - similarity search constrained by ticker and optionally period/report type.
3. Hybrid retrieval:
   - return exact key metrics + top-k semantic chunks in one response.

**Tasks**

1. Implement retrieval service interface:
   - `get_company_record(...)`
   - `search_company_context(...)`
   - `get_hybrid_evidence_package(...)`
2. Add metadata filters and score threshold options.
3. Add deterministic sort policy for tie scores.

**Exit checks**

1. Hybrid retrieval returns aligned metrics and chunks for same query context.
2. Retrieval outputs are stable for repeated fixed queries.

## Workstream 6: Validation, Smoke Tests, and Regression

**Goal**
Prove correctness and reliability before Stage F integration.

**Tests**

1. Structured write/read smoke test:
   - AAPL annual payload persisted and read back.
2. Curation policy test:
   - failing KPI payload does not overwrite curated record.
3. Vector retrieval smoke test:
   - DUOL query returns relevant top-k chunks with metadata.
4. Idempotency test:
   - repeated same payload write does not create duplicate curated rows.
5. Schema evolution test:
   - versioned record validation for backward compatibility.

**Regression checks**

1. Compare retrieved metrics with source payload values for drift.
2. Verify ratio status fields survive storage round-trip unchanged.

**Exit checks**

1. All Stage E tests pass.
2. No data-loss or schema drift detected in round-trip tests.

## Workstream 7: Operational Guardrails and Observability

**Goal**
Make persistence behavior transparent and safe in ongoing runs.

**Tasks**

1. Add structured logging for all persistence operations:
   - write start/end,
   - gate decisions,
   - curated upsert outcomes,
   - vector index writes.
2. Add metrics dashboard counters:
   - raw writes,
   - curated writes,
   - rejected records,
   - retrieval query counts,
   - average retrieval latency.
3. Add retry policy for transient write failures with bounded attempts.
4. Add backup/export command for curated snapshots.

**Exit checks**

1. Persistence runs are traceable by run_id.
2. Failure diagnostics can be triaged from logs without code instrumentation.

## Workstream 8: Stage F Handoff Package

**Goal**
Provide Stage F with a stable retrieval contract and evidence packaging rules.

**Tasks**

1. Publish evidence package schema:
   - structured metrics,
   - selected ratios,
   - retrieved chunks,
   - provenance/citation metadata.
2. Provide query templates for Stage F:
   - latest annual analysis,
   - period-specific analysis,
   - multi-period comparison seed.
3. Deliver sample persisted datasets:
   - full success case,
   - curated rejection case,
   - sparse-market-data case.

**Exit checks**

1. Stage F can consume persistence outputs without schema translation.
2. Evidence package supports grounded citations in analysis sections.

## Sequencing and Dependencies

1. Step 1: Workstream 0 bootstrap readiness.
2. Step 2: Workstream 1 canonical persistence model and Workstream 2 indexing (parallel).
3. Step 3: Workstream 3 write policy (depends on 1-2).
4. Step 4: Workstream 4 vectorization/chunking (parallel with late 3).
5. Step 5: Workstream 5 retrieval API (depends on 2-4).
6. Step 6: Workstream 6 validation/regression (depends on 3-5).
7. Step 7: Workstream 7 observability hardening.
8. Step 8: Workstream 8 Stage F handoff package.

## Verification Checklist for Stage E Completion

1. Persist and read back at least one full AAPL and one DUOL enriched record.
2. Verify exact lookup keys return deterministic curated records.
3. Verify semantic retrieval returns relevant chunks with metadata filters.
4. Verify curated write policy blocks failing-quality payloads.
5. Verify run_id and provenance metadata survive round-trip unchanged.
6. Verify idempotent behavior on repeated writes of identical payloads.
7. Verify Stage F evidence package schema is complete and documented.

## Risks and Mitigations

1. Risk: schema drift between Stage D outputs and persistence model.
   - Mitigation: strict validator and versioned contracts at write boundary.
2. Risk: vector retrieval returns low-signal chunks.
   - Mitigation: section-aware chunking, metadata filters, and score thresholds.
3. Risk: curated record corruption from bad runs.
   - Mitigation: gate-based curated upsert with rejection reasons.
4. Risk: repository module drift blocks integration.
   - Mitigation: Workstream 0 bootstrap track and compatibility adapters.
5. Risk: operational overhead from index growth.
   - Mitigation: index audits, retention policy, and archival strategy.

## Deliverables

1. Persistence module with structured + vector adapters.
2. Canonical storage schema and index migration scripts.
3. Gate-aware write policy for raw and curated records.
4. Retrieval API for exact, semantic, and hybrid evidence queries.
5. Validation and regression suite with smoke tests.
6. Observability package (logs, counters, failure diagnostics).
7. Stage F handoff evidence schema and sample persisted datasets.
