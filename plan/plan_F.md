# Stage F - LLM Analysis Pipeline

## Objective

Stage F implements a grounded analysis layer that converts persisted financial evidence into structured company analysis. The pipeline must be retrieval-first, citation-backed, deterministic in structure, and explicit about uncertainty and missing data.

## Scope

**Included**
- Retrieval-first analysis orchestration consuming Stage E outputs.
- Prompt and response contract for financial analysis sections.
- Evidence grounding and citation validation rules.
- JSON-first analysis output schema with optional markdown rendering.
- Quality gates and evaluation harness for analysis reliability.

**Excluded**
- Data extraction, enrichment, and ratio computation changes (Stages A-D).
- Persistence/index implementation changes (Stage E).
- Frontend/UI presentation work (Phase 4).

## Hard Quality Gates for Stage F Exit

1. Every major conclusion cites at least one retrieved evidence item.
2. Analysis output is schema-valid for all benchmark runs.
3. Missing/ambiguous data is disclosed explicitly, never inferred silently.
4. Output structure is deterministic across repeated runs with fixed input/evidence.
5. Unsupported claims are rejected or downgraded to uncertainty statements.

## Workstream 0: Orchestration Bootstrap and Interface Contracts

**Goal**
Establish a stable analysis entrypoint and contracts with Stage E retrieval APIs.

**Tasks**
1. Define analysis orchestration interface:
   - `generate_financial_analysis(ticker, period_ending, report_type, mode)`.
2. Integrate Stage E retrieval methods:
   - exact record fetch,
   - semantic chunk fetch,
   - hybrid evidence package.
3. Add dry-run mode to inspect assembled evidence without model generation.
4. Add compatibility adapter for legacy payload shape if needed.

**Exit checks**
1. Analysis entrypoint runs end-to-end with mocked model output.
2. Evidence package can be inspected prior to generation.

## Workstream 1: Evidence Package Builder

**Goal**
Build an auditable evidence bundle used as the sole source of truth for analysis generation.

**Evidence package contents**
1. Company and filing context:
   - ticker, company_name, report_type, period_ending.
2. Structured metrics snapshot:
   - key statement metrics,
   - market metrics,
   - selected ratio values + statuses.
3. Retrieved semantic chunks:
   - top-k chunks with metadata and similarity scores.
4. Provenance and quality context:
   - run_id,
   - schema_version,
   - data freshness/staleness flags,
   - KPI verdict summary.

**Tasks**
1. Define strict evidence package schema and required fields.
2. Add filtering policy to avoid noisy or irrelevant chunks.
3. Add deterministic ordering for evidence items.

**Exit checks**
1. Evidence package is reproducible for fixed retrieval inputs.
2. All downstream analysis sections can be traced to evidence package IDs.

## Workstream 2: Analysis Prompting Contract

**Goal**
Define a prompt template that produces consistent, grounded, and machine-parseable outputs.

**Required analysis sections**
1. Business Snapshot
2. Profitability
3. Liquidity and Solvency
4. Efficiency and Growth
5. Valuation
6. Risk Signals
7. Confidence and Unknowns

**Prompt requirements**
1. Force explicit citation tags in each section.
2. Require factual statements to map to metric IDs or chunk IDs.
3. For missing evidence, require explicit uncertainty language.
4. Disallow recommendations unsupported by retrieved evidence.

**Tasks**
1. Create system and task prompt templates with strict output contract.
2. Add model-agnostic prompt builder (no provider lock-in).
3. Add token budget strategy:
   - prioritize critical metrics and high-score chunks,
   - deterministic truncation for oversized evidence sets.

**Exit checks**
1. Prompt consistently yields all required sections.
2. Citation placeholders are produced in every section.

## Workstream 3: Output Schema and Rendering

**Goal**
Standardize analysis outputs for storage, downstream consumption, and optional human-readable rendering.

**JSON output schema (required)**
- `analysis_id`
- `ticker`
- `period_ending`
- `report_type`
- `generated_at`
- `sections`:
  - `business_snapshot`
  - `profitability`
  - `liquidity_solvency`
  - `efficiency_growth`
  - `valuation`
  - `risk_signals`
  - `confidence_unknowns`
- `citations` (global list of referenced evidence IDs)
- `unsupported_claims` (if any)
- `warnings`
- `model_metadata` (model name/version, temperature, token stats)

**Optional markdown rendering**
1. Render JSON sections into readable narrative.
2. Keep citation markers visible in markdown output.

**Tasks**
1. Implement schema validator for analysis output.
2. Build markdown renderer from JSON source to avoid divergence.
3. Add serialization checks for stable field ordering.

**Exit checks**
1. JSON schema validation passes for benchmark outputs.
2. Markdown rendering preserves all section conclusions and citation tags.

## Workstream 4: Grounding and Citation Enforcement

**Goal**
Prevent hallucinations by enforcing evidence-backed statements.

**Rules**
1. Every conclusion sentence must include at least one evidence reference.
2. Citations must resolve to evidence package IDs.
3. If evidence does not support a claim:
   - mark as `unsupported`,
   - move claim to uncertainty section or remove.
4. Claims with stale or low-confidence evidence must include caution flag.

**Tasks**
1. Build citation parser and resolver.
2. Add post-generation grounding validator.
3. Add auto-repair pass:
   - remove unsupported claims,
   - inject missing-data disclosures.

**Exit checks**
1. No uncited conclusion remains in final output.
2. Citation resolver maps all references to valid evidence entries.

## Workstream 5: Uncertainty and Missing-Data Handling

**Goal**
Make uncertainty explicit and standardized across analyses.

**Tasks**
1. Define uncertainty categories:
   - `missing_inputs`,
   - `stale_market_data`,
   - `low_confidence_mapping`,
   - `inconsistent_signals`.
2. Add section-level confidence scoring rubric.
3. Require `confidence_unknowns` section to summarize:
   - what is known,
   - what is uncertain,
   - what additional data would improve confidence.
4. Ensure no section presents uncertain claims as confirmed facts.

**Exit checks**
1. Missing/stale data states are surfaced in outputs consistently.
2. Confidence section appears in all generated analyses.

## Workstream 6: Model Strategy and Runtime Controls

**Goal**
Make generation operationally stable and reproducible.

**Tasks**
1. Define model runtime config:
   - model name,
   - temperature,
   - max tokens,
   - retry strategy.
2. Add deterministic mode for benchmark runs.
3. Add fallback behavior:
   - retry on transient API failures,
   - return partial structured output with warnings if generation aborts.
4. Capture full model metadata in output for auditability.

**Exit checks**
1. Benchmark runs are reproducible in deterministic mode.
2. Runtime failures do not crash full pipeline; failure is explicit in output status.

## Workstream 7: Evaluation Harness and Regression Pack

**Goal**
Measure analysis quality and detect regressions before Stage G integration.

**Evaluation dimensions**
1. Grounding completeness:
   - percent of conclusion sentences with valid citations.
2. Factual consistency:
   - sampled claims match referenced metric values.
3. Structure completeness:
   - all required sections present.
4. Uncertainty handling:
   - missing/stale inputs disclosed.
5. Hallucination guard:
   - unsupported claims count.

**Tasks**
1. Implement automated analysis validator.
2. Build benchmark set:
   - AAPL annual,
   - DUOL annual,
   - one additional period case.
3. Add regression snapshots for JSON analysis outputs.
4. Define pass/fail thresholds for Stage F sign-off.

**Exit checks**
1. Stage F passes all validation thresholds across benchmark set.
2. Regression suite catches structural and grounding regressions.

## Workstream 8: Stage G Handoff Package

**Goal**
Prepare Stage G integration with clear runbooks and acceptance boundaries.

**Tasks**
1. Publish analysis contract docs:
   - input evidence schema,
   - output schema,
   - citation validation rules,
   - failure statuses.
2. Provide integration runbook:
   - persistence retrieval -> evidence package -> generation -> validation.
3. Provide sample outputs:
   - fully grounded analysis,
   - missing-data heavy analysis,
   - partial failure analysis with warnings.

**Exit checks**
1. Stage G can run full pipeline with Stage F as black-box module.
2. Handoff artifacts are sufficient for release-gate testing.

## Sequencing and Dependencies

1. Step 1: Workstream 0 orchestration bootstrap.
2. Step 2: Workstream 1 evidence package builder.
3. Step 3: Workstream 2 prompt contract and Workstream 3 output schema (parallel).
4. Step 4: Workstream 4 grounding enforcement (depends on 1-3).
5. Step 5: Workstream 5 uncertainty handling and Workstream 6 runtime controls (parallel with late 4).
6. Step 6: Workstream 7 evaluation/regression harness.
7. Step 7: Workstream 8 Stage G handoff package.

## Verification Checklist for Stage F Completion

1. Generate analyses for benchmark cases with deterministic runtime settings.
2. Validate all required sections are present in JSON output.
3. Validate citation coverage and citation resolvability.
4. Validate missing/stale data disclosures are present where needed.
5. Confirm unsupported claims are zero or explicitly flagged.
6. Confirm markdown rendering preserves section meaning and citation markers.
7. Confirm Stage G handoff docs and sample outputs are complete.

## Risks and Mitigations

1. Risk: LLM outputs fluent but weakly grounded analysis.
   - Mitigation: strict citation enforcement + post-generation validator.
2. Risk: retrieval noise pollutes analysis quality.
   - Mitigation: evidence filtering, deterministic ranking, and score thresholds.
3. Risk: output schema drift across model versions.
   - Mitigation: schema validator and regression snapshots.
4. Risk: runtime API instability causes partial failures.
   - Mitigation: retry policy + partial-output fallback with warnings.
5. Risk: uncertainty under-reporting leads to overconfident conclusions.
   - Mitigation: mandatory confidence/unknowns section and uncertainty rubric.

## Deliverables

1. Stage F analysis orchestrator integrated with Stage E retrieval.
2. Evidence package schema and builder.
3. Prompt templates and deterministic generation controls.
4. JSON analysis schema validator and markdown renderer.
5. Grounding/citation validation module.
6. Analysis regression harness with benchmark fixtures.
7. Stage G handoff runbook and sample outputs.
