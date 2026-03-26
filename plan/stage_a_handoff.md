# Stage A Handoff Note

## Scope

This handoff summarizes Stage A implementation status after completing WS6 execution checks across AAPL, DUOL, and MO benchmark filings.

## Stage A Guarantees Going Into Stage B

1. Extraction outputs follow the documented contract in [plan/extraction_contract.md](plan/extraction_contract.md).
2. Statement export ordering is deterministic in parser outputs (stable key order for reproducible diffs).
3. KPI gate enforcement is active in [pdf_parser/evaluation/evaluation.py](pdf_parser/evaluation/evaluation.py):
   - configurable thresholds
   - measured KPI reporting
   - pass/fail verdict
   - non-zero exit on failure
4. Benchmark matrix execution is available in [pdf_parser/scripts/run_stage_a_benchmarks.py](pdf_parser/scripts/run_stage_a_benchmarks.py):
   - per-filing evaluation artifact generation
   - trend summary generation
   - optional reuse of existing statement artifacts
5. Ratio pipeline runs for all current benchmark statements:
   - [data_raw/AAPL_statement.json](data_raw/AAPL_statement.json)
   - [data_raw/DUOL_statement.json](data_raw/DUOL_statement.json)
   - [data_raw/MO_statement.json](data_raw/MO_statement.json)

## WS6 Validation Results

### 1) Ratio pipeline execution on benchmark set

Completed successfully for AAPL, DUOL, MO using [financial_ratios/main.py](financial_ratios/main.py).

Produced compressed outputs:
- [data_compressed/AAPL_statement.json](data_compressed/AAPL_statement.json)
- [data_compressed/DUOL_statement.json](data_compressed/DUOL_statement.json)
- [data_compressed/MO_statement.json](data_compressed/MO_statement.json)

### 2) Backward compatibility check (payload shape)

Baseline comparison against [baselines/stage_a_ws1/data_compressed/AAPL_statement.json](baselines/stage_a_ws1/data_compressed/AAPL_statement.json) and [baselines/stage_a_ws1/data_compressed/DUOL_statement.json](baselines/stage_a_ws1/data_compressed/DUOL_statement.json):

- Metric object schema is unchanged for consumers: each metric entry still exposes
  - normalized_label
  - value
  - priorValue
  - unit
  - source_label
  - statement_type
- DUOL top-level key set remained stable vs baseline.
- AAPL top-level key names changed materially (49 added, 49 removed) due label normalization drift in extracted metrics.

Compatibility implication:
- Consumers using the metric object structure remain compatible.
- Consumers hardcoding specific normalized-label keys may break on AAPL and require aliasing/canonical mapping guards.

### 3) Missing input behavior

Missing ratio inputs are explicitly emitted as status `missing_inputs` (not silent failure), with `missing_fields` and error context.

Observed counts:
- AAPL: 20 ratios, 19 `ok`, 1 `missing_inputs` (interest_expense)
- DUOL: 20 ratios, 19 `ok`, 1 `missing_inputs` (interest_expense)
- MO: 20 ratios, 12 `ok`, 8 `missing_inputs`

## Remaining Known Limitations

1. Critical anchor statement-type accuracy is not yet fully stable across benchmark set:
   - MO `net_income` currently resolves from `Net earnings` with `statement_type=cash_flow_statement`.
2. Period alignment confidence is frequently `ambiguous` for anchor rows in current outputs.
3. Critical duplicate collisions still exist in compressed diagnostics:
   - AAPL: revenue collision group present
   - DUOL: revenue collision group present
   - MO: revenue and net_income collision groups present
4. Current expected-case files can mask semantic mapping issues if expected statement types mirror imperfect extraction output.

## Recommended Stage B Schema Integration Points

1. Add schema-versioned canonical key registry and alias table:
   - preserve backward compatibility when normalized labels drift
   - support stable semantic keys independent of source phrasing
2. Persist confidence metadata in canonical model:
   - statement_type_confidence
   - period_alignment_confidence
   - period_alignment_warning
3. Add explicit anchor-quality block in output schema:
   - per-anchor statement_type expected/actual
   - confidence and ambiguity flags
4. Promote duplicate diagnostics into schema-level provenance section:
   - collision count
   - winner and rejected candidates
   - filtering decisions for critical anchors
5. Keep ratio status contract mandatory:
   - `ok` or `missing_inputs`
   - always include `missing_fields` when missing_inputs

## Plan A Exit Gate Status

From current benchmark artifacts:

1. Statement detection accuracy >= 97.0%: PASS
2. Canonical line-item mapping accuracy >= 97.0%: PASS
3. Numeric parse accuracy >= 99.0%: PASS
4. Zero critical duplicate collisions in curated benchmark outputs: FAIL
5. Explicit pass/fail evaluation artifacts for all benchmark runs: PASS

Overall Stage A status: **Partially complete; not yet ready for formal closure until critical duplicate collisions and anchor semantic misclassification issues are resolved.**
