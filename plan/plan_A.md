# Stage A - Stabilize Extraction Contract

## Objective

Make extraction outputs reliable, auditable, and regression-safe before any new architecture work begins. This stage focuses on eliminating duplicate leakage, tightening statement mapping quality, and enforcing KPI-based release gates so downstream ratio, storage, and LLM layers receive stable inputs.

## Scope

**Included**

- Extraction hardening from parsed table cells to exported statement artifacts.
- Deduplication strategy in parser exports and compressed outputs.
- Evaluation gate design and benchmark expansion.
- Backward compatibility checks for ratio input consumers.

**Excluded**

- Market data ingestion.
- New ratio categories.
- Persistence or vector database implementation.
- LLM orchestration.

## Hard Quality Gates for Stage A Exit

These must all pass before Stage B starts:

1. Statement detection accuracy >= 97.0%
2. Canonical line-item mapping accuracy >= 97.0%
3. Numeric parse accuracy >= 99.0% (within configured tolerance)
4. Zero critical duplicate collisions in curated benchmark outputs
5. All benchmark runs produce an evaluation report with an explicit pass/fail verdict

---

## Workstream 1 - Baseline Freeze and Contract Definition

**Goal:** capture the current behavior as a baseline and define an explicit extraction contract that all subsequent changes must preserve or improve.

**Tasks**

1. Freeze baseline artifacts for AAPL and DUOL:
   - raw statement JSON (`data_raw/`)
   - statement markdown (`data_raw/`)
   - compressed output JSON (`data_compressed/`)
   - evaluation JSON (`data_raw/`)
2. Define extraction contract document including:
   - required top-level fields on the statement payload
   - required item-level fields on each line item
   - allowed nullability and status tag values
   - expected unit semantics (`USD`, `%`, `ratio`, `shares`)
3. Add deterministic ordering rules for statement items in exports (stable sort keys) to make output diffing reliable.
4. Define compatibility matrix for downstream consumers in the financial ratio pipeline.

**Primary files**

- `pdf_parser/main.py`
- `pdf_parser/models/schemas.py`
- `financial_ratios/scripts/aggregator.py`

**Exit checks**

- Baseline artifacts are stored and reproducible from a documented command path.
- Extraction contract is documented and linked from the global plan.

---

## Workstream 2 - Duplicate Elimination Strategy

**Goal:** remove duplicate metrics generated across repeated tables and sections while preserving the best-quality row for each canonical label.

**Known duplicate sources (confirmed)**

- Mapper stage: no deduplication across tables in the same PDF. Multi-page or repeated-section filings produce N×table copies of the same label.
- Markdown export: the `export()` function in `main.py` iterates all items before deduplication, so duplicated labels appear multiple times per section (e.g., `revenue` appears 7 times in AAPL markdown).
- Aggregator: `_pick_best_duplicate()` resolves by score but statement-type weighting is too low, allowing semantically wrong rows to win (e.g., `iphone` classified as `balance_sheet`).

**Tasks**

1. Add a pre-export dedup pass inside the parser pipeline:
   - group by `normalized_label` + `statement_type` + period context.
   - score candidates using `parse_status`, current/prior value availability, label confidence, and statement-type preference.
2. Retain the original raw row reference as a provenance trace for the selected winner.
3. Ensure markdown export consumes the deduplicated item list, not the raw full list.
4. Tighten the aggregator duplicate resolver:
   - increase statement-type consistency weighting for core metrics.
   - avoid selecting semantically mismatched rows even when they have a higher magnitude value.
5. Emit a duplicate diagnostics block alongside each output:
   - labels with collision count
   - selected winner source label and statement type
   - rejected candidate summary

**Primary files**

- `pdf_parser/main.py`
- `pdf_parser/processors/mapper.py`
- `financial_ratios/scripts/aggregator.py`

**Exit checks**

- A duplicate collision report is generated alongside each benchmark run output.
- No repeated canonical metric appears in the compressed output for any benchmark filing.
- Markdown output sections do not repeat the same canonical label unless the rows are intentionally period-distinct and explicitly flagged.

---

## Workstream 3 - Statement-Type and Period Alignment Hardening

**Goal:** reduce misclassification of statement types and period-role assignment errors that contaminate downstream ratio inputs.

**Known issues (confirmed)**

- Segment and product breakdown tables (e.g., iPhone, Mac, Americas) fall through mapper rules and are classified as `balance_sheet` instead of being excluded or marked as supplemental.
- `_infer_period_column_roles()` in `mapper.py` uses complex heuristics on year tokens and header text; unusual headers produce silent wrong-period assignments.

**Tasks**

1. Audit and refine statement-type classification rules:
   - prioritize authoritative context markers (section headers, table titles).
   - add explicit guard rules for common false positives (segment/product tables misclassified as balance sheet).
2. Improve period-role inference diagnostics:
   - persist detected current/prior column mapping in item metadata.
   - emit a warning when header confidence is low or column assignment is ambiguous.
3. Introduce per-item confidence tags:
   - `statement_type_confidence` (`high` / `low` / `ambiguous`)
   - `period_alignment_confidence` (`high` / `low` / `ambiguous`)
4. Add fallback behavior for low-confidence items:
   - if confidence falls below threshold, mark item as `ambiguous` and exclude it from canonical winner selection for critical KPI anchor fields.

**Primary files**

- `pdf_parser/processors/mapper.py`
- `pdf_parser/processors/cleaners.py`

**Exit checks**

- Misclassified core anchors (`revenue`, `net_income`, `total_assets`) reduced to zero across the benchmark set.
- Period-mapping warnings are visible in the output report for any low-confidence rows.

---

## Workstream 4 - KPI Gate Enforcement

**Goal:** convert evaluation from passive diagnostic reporting into a mandatory release gate with explicit pass/fail semantics.

**Current state**

- `evaluation.py` computes three KPIs (statement detection accuracy, line-item mapping accuracy, numeric parse accuracy) but never enforces thresholds.
- The CLI exits with code 0 regardless of quality.
- Only AAPL has hardcoded expected cases; DUOL has no expected case definitions.

**Tasks**

1. Externalize KPI thresholds and numeric tolerance to config constants (or optional CLI arguments with safe defaults).
2. Extend the evaluation report structure with:
   - configured gate thresholds per KPI
   - measured KPI values per KPI
   - overall verdict: `pass` or `fail`
   - blocking reasons list when verdict is `fail`
3. Add non-zero exit code behavior when verdict is `fail`.
4. Build a summary runner script that executes extraction + evaluation across the full benchmark set and collects a KPI trend table.
5. Require evaluation artifact generation as a mandatory step for each benchmark filing.

**Primary files**

- `pdf_parser/evaluation/evaluation.py`
- `pdf_parser/main.py`

**Exit checks**

- A failing KPI evaluation exits with a non-zero code.
- A passing evaluation emits a clear `pass` verdict with measured metric values.
- The gate is runnable as a discrete release checklist step.

---

## Workstream 5 - Benchmark Expansion and Regression Pack

**Goal:** ensure extraction quality is not overfit to AAPL FY2025 and remains stable across different companies and report styles.

**Current state**

- AAPL: full expected case set (11 anchor cases hardcoded in `evaluation.py`).
- DUOL: statement artifacts exist but no expected case definitions and no evaluation artifact.
- No additional filings are covered.

**Tasks**

1. Add at least two new benchmark expected-case sets:
   - DUOL annual (create expected JSON with same anchor case structure)
   - one additional filing (annual or quarterly from a different company or period)
2. Ensure each benchmark entry has:
   - source PDF
   - expected case definitions JSON
   - generated statement artifact
   - generated evaluation artifact
3. Build regression matrix runner:
   - execute extraction + evaluation across all benchmark filings in one command.
   - produce a KPI trend table per filing (statement detection, label mapping, numeric parse).
4. Validate key anchor metrics for each benchmark:
   - `revenue`, `net_income`, `total_assets`, `total_liabilities`, `cash_and_cash_equivalents`

**Primary files**

- `data_raw/` (benchmark artifacts)
- `pdf_parser/evaluation/evaluation.py`

**Exit checks**

- At least three benchmark filings are covered by expected-case sets.
- Regression matrix runner produces a stable KPI pass trend across consecutive runs.

---

## Workstream 6 - Backward Compatibility and Handoff Readiness

**Goal:** guarantee that Stage A hardening does not break the financial ratio pipeline and produces a clean handoff package for Stage B schema work.

**Tasks**

1. Run aggregator and ratio computation against all updated benchmark outputs.
2. Verify ratio payload shape is unchanged for existing consumers.
3. Record known missing input fields explicitly as `missing_inputs` statuses rather than silent failures.
4. Write a Stage A handoff note capturing:
   - extraction contract guarantees going into Stage B
   - remaining known limitations
   - recommended Stage B schema integration points

**Primary files**

- `financial_ratios/main.py`
- `financial_ratios/scripts/ratio_calculation.py`
- `financial_ratios/scripts/field_resolver.py`

**Exit checks**

- Ratio pipeline runs successfully on all Stage A benchmark outputs.
- No schema-breaking changes were introduced for downstream modules.
- Handoff note is written before Stage B implementation starts.

---

## Sequencing and Dependencies

```
WS1 (baseline freeze)
  └─> WS2 (duplicate elimination)
        └─> WS4 (KPI gate)  ← also depends on WS3 outputs
  └─> WS3 (statement-type hardening)   ← runs parallel to late WS2
        └─> WS4
  WS4 + WS5 (benchmark expansion) ← WS5 can start once WS4 gate shape is fixed
        └─> WS6 (compatibility + handoff)
```

1. WS1 must complete first.
2. WS2 and WS3 run in parallel after WS1.
3. WS4 integrates outputs of WS2 and WS3 and is the enforcement gate.
4. WS5 starts after WS4 gate mechanics are in place.
5. WS6 is the final validation and handoff step.

---

## Verification Checklist (Stage A Exit)

Run these steps in order before calling Stage A done:

- [ ] Run extraction pipeline for each benchmark filing → produces statement JSON + markdown.
- [ ] Run evaluation for each benchmark filing → produces report with explicit pass/fail verdict.
- [ ] Confirm no duplicate canonical labels in compressed output for all benchmark filings.
- [ ] Confirm anchor metrics are assigned the correct statement type for all benchmarks.
- [ ] Run financial ratio pipeline on benchmark outputs → no contract break.
- [ ] Generate final Stage A summary report with:
  - KPI table per filing
  - duplicate diagnostics summary
  - compatibility status
  - go/no-go decision for Stage B

---

## Risks and Mitigations

| Risk                                                          | Mitigation                                                                             |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Aggressive dedup removes valid context rows                   | Keep duplicate diagnostics and provenance pointers for all rejected candidates         |
| Stricter statement-type gating reduces coverage               | Use confidence-based fallback to `unclassified` + warning instead of forced wrong type |
| Benchmark creation effort delays progress                     | Start with minimum anchor cases per filing and expand iteratively                      |
| KPI thresholds initially too strict for diverse filing styles | Run a calibration pass, document threshold rationale, then lock for gate               |

---

## Deliverables

1. Stable extraction contract specification (linked from `global_plan.md`).
2. Deduplicated export behavior with diagnostic output.
3. Enforced evaluation gate with pass/fail semantics and non-zero exit on failure.
4. Expanded benchmark set covering at least 3 filings with expected case definitions.
5. Regression matrix runner producing a KPI trend table across the benchmark set.
6. Compatibility validation confirming ratio pipeline is unaffected.
7. Stage B handoff package with contract guarantees and integration points.
