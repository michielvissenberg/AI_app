# Stage A Extraction Contract

## Purpose

Define the stable extraction output contract that Stage A Workstream 1 freezes and all downstream stages must preserve.

## Baseline Freeze Command Path

Run from repository root:

```powershell
python pdf_parser/scripts/freeze_stage_a_baseline.py --output-dir baselines/stage_a_ws1
```

Expected baseline snapshot includes:

- data_raw/AAPL_statement.json
- data_raw/AAPL_statement.md
- data_raw/AAPL_evaluation.json
- data_raw/DUOL_statement.json
- data_raw/DUOL_statement.md
- data_compressed/AAPL_statement.json
- data_compressed/DUOL_statement.json
- baselines/stage_a_ws1/manifest.json

## Top-Level Statement Payload Contract

Required fields for every parser statement JSON:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| company_name | string | yes | Human-readable issuer name |
| ticker | string | yes | Uppercase ticker symbol |
| report_type | string | yes | Expected values: 10-K, 10-Q |
| period_ending | string | yes | ISO date text (YYYY-MM-DD) |
| extracted_at | string | yes | ISO datetime |
| items | list[FinancialLineItem] | yes | Canonical extracted metrics |

Optional field:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| summary_vector | list[number] | no | Optional embedding vector |

## FinancialLineItem Contract

Required item fields:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| label | string | yes | Raw source row label |
| unit | string | yes | Expected semantic domain; default USD |
| scale | string | yes | Expected value granularity; default millions |

Optional item fields:

- normalized_label: string or null
- statement_type: string or null
- value: number or null
- column_values: list[number or null] or null
- column_units: list[string] or null
- column_scales: list[string] or null
- column_parse_statuses: list[string] or null
- parse_status: string or null
- yoy_change: number or null
- yoy_unit: string or null
- current_period_value: number or null
- prior_period_value: number or null
- current_period_label: string or null
- prior_period_label: string or null
- current_period_column: integer or null
- prior_period_column: integer or null
- supplemental_metrics: map[string, list[number or null]] or null

## Status and Nullability Rules

- Null means unknown or unavailable; never fabricate values.
- parse_status should be explicit when parse attempts occur.
- Recommended parse_status vocabulary for Stage A onward: ok, parse_error, ambiguous, missing.
- Consumers must treat absent current_period_value/prior_period_value as non-fatal and fallback to value when available.

## Unit Semantics

- USD: monetary values.
- %: percentage-based values.
- ratio: dimensionless ratio values.
- shares: share-count values.

If a line item has mixed units in source columns, preserve per-column units in column_units and avoid forced conversion at extraction stage.

## Deterministic Ordering Rules for Exports

Exports must use a stable item order for both JSON and markdown outputs:

1. statement_type order: income_statement, balance_sheet, cash_flow_statement, equity_statement, unclassified
2. normalized_label (case-insensitive)
3. raw label (case-insensitive)
4. current_period_label, prior_period_label
5. current_period_column, prior_period_column
6. parse_status

These rules guarantee reproducible diffs for benchmark artifacts.

## Downstream Compatibility Matrix

| Consumer | File | Required fields from statement output | Compatibility requirement |
| --- | --- | --- | --- |
| Statement aggregator | financial_ratios/scripts/aggregator.py | items[].normalized_label, items[].current_period_value, items[].prior_period_value, items[].value, items[].unit, items[].label, items[].statement_type, items[].parse_status | Keep item-level keys and meanings stable; optional fields may be null |
| Field resolver | financial_ratios/scripts/field_resolver.py | Aggregated metric keys emitted from normalized_label map | normalized_label normalization remains stable for anchor metrics |
| Ratio calculator | financial_ratios/scripts/ratio_calculation.py | Aggregated current/prior values and units | Missing values must surface as missing_inputs downstream, not crashes |
| Ratio enricher | financial_ratios/scripts/ratio_enricher.py | Base compressed payload + aggregated metrics | Statement-derived metric naming remains backward-compatible |

## Stage A WS1 Exit Artifacts

- Frozen baseline bundle under baselines/stage_a_ws1
- Manifest with checksums for reproducibility
- Stable JSON and markdown ordering behavior in parser exports
- This contract document referenced by plan/global_plan.md and plan/plan_A.md
