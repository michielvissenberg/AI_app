# Improvements for Plan A and Plan B (Current Execution Window)

## 1. Executive Snapshot

- Stage A extraction hardening is materially implemented: pre-export deduplication, duplicate diagnostics, benchmark runner, and KPI gate verdicts are present.
- Stage B canonical envelope is implemented in compressed payloads: schema_version, company_context, filing_context, statement_metrics, market_metrics stubs, ratios, and provenance are present.
- Stage B validator exists and runs; latest run in terminal indicates validator pass on AAPL, DUOL, and MO compressed outputs.
- The main near-term risk is quality drift hidden by all green benchmark KPIs while payload semantics still show broad ambiguity and noise metrics entering statement_metrics.
- The current pipeline is strong on structure, but weaker on semantic precision, contract strictness, and benchmark representativeness.

Top risks blocking near-term progress:
- Overly optimistic KPI signals due to narrow benchmark anchors and favorable matching criteria.
- Noise filtering and duplicate resolution rely on static keyword heuristics that can silently drop useful fields or keep irrelevant ones.
- Provenance and contract controls are warning-only in critical places, so drift can enter data_compressed without failing fast.

## 2. Plan-Implementation Gap Report

### Plan A (Stabilize Extraction Contract)

- Planned item: Mandatory KPI release gate with explicit pass/fail behavior.
 - Status: Implemented.
 - Evidence: pdf_parser/evaluation/evaluation.py defines thresholds and verdict; pdf_parser/scripts/run_stage_a_benchmarks.py returns non-zero when any benchmark fails and writes stage summary.

- Planned item: Duplicate elimination in export path with diagnostics.
 - Status: Implemented.
 - Evidence: pdf_parser/main.py runs _deduplicate_statement_items before export and writes duplicate diagnostics JSON.

- Planned item: Benchmark expansion to >=3 filings and trend summary.
 - Status: Implemented.
 - Evidence: data_raw/stage_a_benchmarks.json has AAPL, DUOL, MO; data_raw/stage_a_benchmark_summary.json reports configured_benchmarks=3 and pass verdicts.

- Planned item: Extraction contract reliability for downstream consumers.
 - Status: Partial.
 - Evidence: structure is stable, but data_raw/AAPL_statement.md still contains large volumes of noisy/ambiguous rows and repeated semantic variants, indicating classification and period alignment uncertainty remains high.

### Plan B (Canonical Enriched Data Model)

- Planned item: Canonical top-level envelope and schema version.
 - Status: Implemented.
 - Evidence: data_compressed/AAPL_statement.json has schema_version plus all planned sections.

- Planned item: Expanded AggregatedMetric fields and null/status semantics.
 - Status: Implemented (with caveat).
 - Evidence: financial_ratios/models/models.py and financial_ratios/scripts/aggregator.py include status, yoy, scale, statement_type_confidence, source_raw_label. Caveat: many core metrics in compressed output are still status=ambiguous, limiting downstream trust.

- Planned item: Provenance section with run metadata and optional KPI forwarding.
 - Status: Implemented.
 - Evidence: financial_ratios/main.py builds provenance including run_id, aggregated_at, optional evaluation KPIs.

- Planned item: Schema validation.
 - Status: Implemented as warning-only.
 - Evidence: financial_ratios/models/validation.py validates required sections/units/status; financial_ratios/main.py logs violations as warnings instead of failing.

- Planned item: Backward compatibility for ratio pipeline.
 - Status: Implemented.
 - Evidence: financial_ratios/scripts/field_resolver.py and ratio_enricher.py support statement_metrics envelope while preserving output[ratios] access.

## 3. Priority Optimizations

1. Tighten semantic quality gates beyond current KPI pass
- Impact: High
- Effort: Medium
- Risk: Low
- Expected outcome: Fewer false-green benchmark runs; better trust in statement_metrics for later stages.
- Why now: Current KPIs can show 100 while many metrics remain ambiguous/noisy.
- Recommendation:
 - Add secondary gate metrics: ambiguous_rate, parse_error_rate, and noise_ratio in exported items.
 - Set alert thresholds first (warning), then enforce fail once baselines stabilize.

2. Replace static noise keywords with scored suppression + allowlist by role
- Impact: High
- Effort: Medium
- Risk: Medium
- Expected outcome: Reduced accidental drops and better portability across issuers without issuer-specific heuristics.
- Why now: global_todos explicitly flags table/header and unit issues; current _is_noise keyword list is brittle.
- Recommendation:
 - Keep deterministic scoring model (parse status, confidence, section context, value presence).
 - Separate exclusion classes: structural noise, supplemental detail, candidate canonical metric.

3. Add contract tests for Stage A -> Stage B handoff invariants
- Impact: High
- Effort: Low
- Risk: Low
- Expected outcome: Immediate detection of schema drift or missing mandatory fields.
- Why now: B output is structurally richer, but enforcement is split and partly warning-only.
- Recommendation:
 - Add fixture-based tests asserting required top-level fields, status tag legality, and stable ratio output shape.

4. Strengthen period/scale/unit fidelity checks
- Impact: Medium-High
- Effort: Medium
- Risk: Medium
- Expected outcome: Fewer magnitude/unit mistakes and cleaner Stage C/D calculations.
- Why now: global_todos notes thousands/millions correctness and percentage detection concerns.
- Recommendation:
 - Track original table header context for each numeric parse and keep scale evidence in provenance-lite fields.
 - Add checks that mixed-scale rows cannot be treated as directly comparable without normalization flags.

5. Make validation mode configurable (warn vs strict)
- Impact: Medium
- Effort: Low
- Risk: Low
- Expected outcome: Safe migration now, strict enforcement readiness for Stage E writes.
- Why now: Plan B already anticipates warning-only today and strictness later.
- Recommendation:
 - Add --validation-mode warn|strict to financial_ratios/main.py.
 - Fail in CI benchmark tasks under strict mode while local iteration can stay warn.

6. Introduce cross-stage observability summary artifact
- Impact: Medium
- Effort: Medium
- Risk: Low
- Expected outcome: Faster triage when regressions appear between parser and ratio layers.
- Why now: Provenance exists, but there is no single artifact showing extraction quality + aggregation ambiguity + ratio missing_inputs in one place.
- Recommendation:
 - Emit one run-level quality dashboard JSON per filing linking statement diagnostics, evaluation KPIs, validator output, and ratio statuses.

## 4. Action Plan

1. Add semantic quality metrics to benchmark reports (warnings first).
- Dependencies: none.
- Validation checks:
 - run python pdf_parser/scripts/run_stage_a_benchmarks.py --reuse-existing-statements
 - confirm summary includes ambiguous_rate, parse_error_rate, noise_ratio.
- Success criteria:
 - new metrics generated for all benchmarks; no pipeline break.

2. Refactor noise handling into deterministic scored classifier.
- Dependencies: Step 1 baseline metrics.
- Validation checks:
 - compare duplicates_removed, ambiguous_rate, and anchor-field preservation before/after.
- Success criteria:
 - anchor metrics preserved; noisy rows reduced without issuer-specific rules.

3. Add handoff contract tests between raw statement and enriched record.
- Dependencies: Steps 1-2.
- Validation checks:
 - run validator on all data_compressed filings.
 - assert required sections/fields and allowed tags/units.
- Success criteria:
 - tests fail on malformed fixtures and pass on benchmark outputs.

4. Implement validation mode switch in financial_ratios pipeline.
- Dependencies: Step 3.
- Validation checks:
 - warn mode: pipeline succeeds with warnings.
 - strict mode: malformed payload exits non-zero.
- Success criteria:
 - predictable enforcement behavior for local vs CI.

5. Add unit/scale confidence guardrails and table-context retention.
- Dependencies: Step 2.
- Validation checks:
 - targeted tests for percent rows, thousands/millions, and mixed-column scales.
- Success criteria:
 - reduced unit mismatch violations and fewer anomalous magnitudes.

6. Build a single run health artifact for Stage A+B.
- Dependencies: Steps 1,3,4.
- Validation checks:
 - each benchmark emits one health JSON linking gate verdict, ambiguity stats, duplicate collisions, validation violations, and ratio missing_inputs counts.
- Success criteria:
 - one-file triage for every run with consistent keys.

## 5. Open Questions

- Should ambiguous core anchors (revenue, net_income, total_assets) be allowed in Stage B outputs, or should they block compression in strict mode?
 - Trade-off: strict blocking improves trust but may reduce throughput on hard filings.

- For markdown output migration (todo: remove raw md, create compressed md), should markdown become a derived view from data_compressed only?
 - Trade-off: single source of truth vs easier debugging from parser-native artifacts.

- Should market-related fields already present in statement metrics (for example cash_and_cash_equivalents) be reconciled into market_metrics in Stage C or remain separated by source forever?
 - Trade-off: cleaner consumer API vs clearer source provenance separation.

- Is benchmark success defined only by KPI thresholds, or also by bounded ambiguity/noise rates?
 - Trade-off: simpler gate maintenance vs stronger real-world reliability.

- Do you want to freeze schema_version 1.0 until Stage D completes, or allow 1.1 for stricter validation mode and observability additions?
 - Trade-off: fewer migrations now vs cleaner incremental contract evolution.
