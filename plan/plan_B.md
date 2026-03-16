# Stage B - Canonical Enriched Data Model

## Objective

Define a single versioned schema that all pipeline stages write to and read from. Stage B turns the current informal flat dict output into a structured, self-describing record that carries company context, filing metadata, statement metrics, placeholders for market data, ratio results, and provenance in one consistent shape.

This schema becomes the shared contract between Stage A (extraction), Stage C (market enrichment), Stage D (extended ratios), Stage E (persistence), and Stage F (LLM analysis).

## Scope

**Included**
- Canonical top-level section definitions and field-level contracts.
- Schema versioning mechanism.
- Improvements to `AggregatedMetric` to carry necessary provenance.
- Null/missing semantics and status tag conventions standardized across all sections.
- Validation rules for unit consistency, required field presence, and type safety.
- Backward compatibility with existing ratio and aggregation consumers.

**Excluded**
- Market data ingestion implementation (Stage C).
- New ratio definitions (Stage D).
- Persistence layer writes (Stage E).
- LLM analysis outputs (Stage F).
- UI integration (Phase 4).

## Hard Quality Gates for Stage B Exit

1. A versioned schema class or spec document exists and is used by at least the aggregator and ratio pipeline.
2. Compressed output for benchmark filings conforms to the canonical top-level structure.
3. All existing ratio outputs remain structurally unchanged for downstream consumers.
4. Null/missing semantics are explicitly documented and consistently applied.
5. Schema validation can be run programmatically and catches malformed records.

---

## Current State Analysis

**`FinancialStatement` / `FinancialLineItem`** (`pdf_parser/models/schemas.py`)
- Good per-item coverage: label, normalized_label, statement_type, value, unit, scale, parse_status, period labels/columns.
- Missing: run_id, engine version, extraction timestamps, confidence tags (planned in Stage A WS3).
- `summary_vector` placeholder exists but is unused.

**`AggregatedMetric`** (`financial_ratios/models/models.py`)
- Only 6 fields: normalized_label, value, priorValue, unit, source_label, statement_type.
- No provenance, no status tag, no schema version.
- Returned as a plain dataclass and serialized to a flat dict.

**Compressed output format** (`data_compressed/*.json`)
- Top level is a flat dict of `normalized_label -> AggregatedMetric` fields, plus a `"ratios"` key.
- No `company_context` or `filing_context` section — ticker and period are only in the filename.
- No `market_metrics` section.
- No `provenance` section.

**Ratio output format** (already well-structured — must be preserved exactly)
```json
{
  "gross_margin": {
    "value": 0.469,
    "unit": "ratio",
    "description": "...",
    "inputs": { "gross_profit": 195201.0, "revenue": 416161.0 },
    "status": "ok",
    "missing_fields": [],
    "error": null
  }
}
```

---

## Workstream 1 - Define Canonical Top-Level Sections

**Goal:** establish the structural envelope of every enriched company record.

**Target top-level shape**

```json
{
  "schema_version": "1.0",
  "company_context": { ... },
  "filing_context":  { ... },
  "statement_metrics": { "normalized_label": { ...AggregatedMetric }, ... },
  "market_metrics":  { ... },
  "ratios": { "ratio_name": { ...RatioResult }, ... },
  "provenance": { ... }
}
```

**Section definitions**

`company_context`
- `ticker` (string, required)
- `company_name` (string, required)
- `currency` (string, default `"USD"`)

`filing_context`
- `report_type` (string, required — `10-K` or `10-Q`)
- `period_ending` (string ISO date, required)
- `fiscal_year` (integer, derived from period_ending)
- `fiscal_period` (string — `annual` or `Q1` / `Q2` / `Q3`)
- `source_pdf` (string filename, optional)

`statement_metrics`
- Flat dict of `normalized_label -> AggregatedMetric`, same keys as current but now wrapped in its own section.
- Each entry carries the expanded `AggregatedMetric` defined in Workstream 2.

`market_metrics`
- Empty placeholder object `{}` in Stage B.
- Field stubs with `source_status: "not_fetched"` emitted per planned field so Stage C can fill them without schema changes.
- Full field definitions live in `plan_C.md`.

`ratios`
- Dict of `ratio_name -> RatioResult` — current shape preserved without changes.

`provenance`
- Defined in Workstream 3.

**Tasks**
1. Define the top-level structure as a Python dataclass or Pydantic model in `financial_ratios/models/models.py`.
2. Update `financial_ratios/main.py` to wrap the current flat output in the new envelope.
3. Keep the existing ratio shape nested under `"ratios"` key without changes.

**Primary files**
- `financial_ratios/models/models.py`
- `financial_ratios/main.py`

**Exit checks**
- Benchmark compressed outputs conform to the new top-level structure.
- Existing ratio consumers can still access `output["ratios"]` without code changes.

---

## Workstream 2 - Expand AggregatedMetric

**Goal:** give each statement metric enough context for downstream stages to use it without referring back to the raw statement artifact.

**Current `AggregatedMetric` fields**
```
normalized_label, value, priorValue, unit, source_label, statement_type
```

**Additional fields to add**

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `status` | string | `"ok"` | `"ok"` \| `"missing"` \| `"ambiguous"` — mirrors ratio output conventions |
| `yoy_change` | float \| None | `None` | Year-over-year delta forwarded from parser |
| `yoy_unit` | string \| None | `None` | `"USD"` or `"%"` matching yoy_change |
| `scale` | string \| None | `None` | `"millions"` \| `"thousands"` \| `"units"` forwarded from parser |
| `statement_type_confidence` | string \| None | `None` | `"high"` \| `"low"` \| `"ambiguous"` from Stage A WS3 |
| `source_raw_label` | string \| None | `None` | Alias of source_label for downstream clarity |

**Tasks**
1. Extend the `AggregatedMetric` dataclass in `financial_ratios/models/models.py` with the fields above.
2. Update `aggregator.py` to populate new fields from the raw statement items during resolution.
3. Forward `yoy_change`, `yoy_unit`, and `scale` from `FinancialLineItem` into `AggregatedMetric`.
4. All new fields must be optional with `None` defaults so existing callers are not broken.
5. Update `_to_jsonable()` in `financial_ratios/main.py` to include new fields in serialized output.

**Primary files**
- `financial_ratios/models/models.py`
- `financial_ratios/scripts/aggregator.py`
- `financial_ratios/main.py`

**Exit checks**
- Existing ratio resolution in `field_resolver.py` continues to work unchanged.
- `AggregatedMetric` serialized output includes new fields for benchmark filings.
- `yoy_change` is populated for fields where the parser produced it.

---

## Workstream 3 - Provenance Section

**Goal:** make every output record self-describing and reproducible without having to re-run the pipeline or inspect logs.

**Provenance fields**

```json
{
  "provenance": {
    "run_id": "<uuid4>",
    "pipeline_version": "0.1.0",
    "extraction_engine": "docling | azure | unknown",
    "extracted_at": "<ISO 8601>",
    "aggregated_at": "<ISO 8601>",
    "source_pdf": "AAPL_statement.pdf",
    "statement_detection_accuracy": 97.5,
    "line_item_mapping_accuracy": 98.2,
    "numeric_parse_accuracy": 99.1,
    "evaluation_verdict": "pass | fail | not_run",
    "duplicate_collisions_resolved": 4
  }
}
```

**Notes**
- `run_id` is generated once per aggregation run (UUID4).
- `pipeline_version` is a hardcoded constant for now; can be made dynamic later.
- KPI accuracy fields are `null` when no evaluation artifact is provided.
- `duplicate_collisions_resolved` comes from the dedup diagnostics built in Stage A WS2.
- `extracted_at` and `extraction_engine` are carried forward from the raw statement payload if present.

**Tasks**
1. Add a `Provenance` dataclass in `financial_ratios/models/models.py`.
2. Generate `run_id` (UUID4) and `aggregated_at` timestamp in `financial_ratios/main.py` at the start of each run.
3. Accept an optional `--evaluation` CLI argument in `financial_ratios/main.py` and populate KPI fields from it when provided.
4. Read `extracted_at` and `extraction_engine` from the raw statement payload top-level fields if present.

**Primary files**
- `financial_ratios/models/models.py`
- `financial_ratios/main.py`

**Exit checks**
- Every compressed output contains a populated `provenance` section.
- `run_id` is unique across consecutive runs on the same filing.
- KPI fields are `null` (not absent) when no evaluation artifact is passed.

---

## Workstream 4 - Null and Missing Semantics

**Goal:** standardize how every section communicates unavailable, unresolved, or ambiguous data so all downstream stages behave consistently.

**Conventions**

| Situation | Convention |
|-----------|------------|
| Field not present in source data | `null` value + `status: "missing"` |
| Field present but parse failed | `null` value + `status: "parse_error"` |
| Field resolved but statement type is ambiguous | value present + `status: "ambiguous"` |
| Field resolved cleanly | value present + `status: "ok"` |
| Ratio input missing | existing `status: "missing_inputs"` + `missing_fields` list |
| Market field not yet fetched | `null` value + `source_status: "not_fetched"` |

**Tasks**
1. Apply `status` field to all `AggregatedMetric` entries (handled by Workstream 2).
2. Emit `market_metrics` section with per-field stubs using `source_status: "not_fetched"` rather than a bare empty dict, covering the fields Stage C will populate:
   - `share_price`, `shares_outstanding`, `market_cap`, `total_debt`, `enterprise_value`
3. Add a validation helper that checks status tag values are within the defined allowed set.

**Primary files**
- `financial_ratios/models/models.py`
- `financial_ratios/main.py`

**Exit checks**
- No `AggregatedMetric` entry in benchmark output is missing the `status` field.
- `market_metrics` section in Stage B outputs contains `"not_fetched"` stubs for Stage C fields.

---

## Workstream 5 - Schema Versioning and Validation

**Goal:** allow future schema evolution without silent breakage in downstream consumers.

**Tasks**
1. Add `schema_version: "1.0"` as the first key written to every compressed output record.
2. Add a `validate_enriched_record(record: dict) -> list[str]` function in `financial_ratios/models/` that checks:
   - required top-level sections are present: `company_context`, `filing_context`, `statement_metrics`, `ratios`, `provenance`.
   - required fields within each section are non-null.
   - `unit` values are within the allowed set: `USD`, `%`, `ratio`, `shares`, `millions`, `thousands`, `units`.
   - `status` tag values are within the allowed set.
   - `schema_version` key exists.
3. Call the validator as the final step in `financial_ratios/main.py` and log any violations as warnings.
4. Validation failures produce warnings only in Stage B; hard failure is activated in Stage E at write time.

**Primary files**
- `financial_ratios/models/models.py` (or new `financial_ratios/models/validation.py`)
- `financial_ratios/main.py`

**Exit checks**
- Validator runs against benchmark compressed outputs without violations.
- Deliberately malformed test record triggers the expected violation list.

---

## Workstream 6 - Backward Compatibility Verification

**Goal:** prove the schema envelope change does not break any existing consumer of the compressed output.

**Consumers to verify**

| File | What it reads |
|------|---------------|
| `financial_ratios/scripts/field_resolver.py` | `aggregated_metrics` dict keyed by normalized_label |
| `financial_ratios/scripts/ratio_enricher.py` | `compressed_payload` dict + `aggregated_metrics` separately |
| `financial_ratios/scripts/ratio_calculation.py` | resolved field value dict from field_resolver |

**Tasks**
1. Update `field_resolver.py` to read from `statement_metrics` sub-dict of the new envelope (or add a thin compatibility shim).
2. Update `add_ratios_to_compressed_payload()` in `ratio_enricher.py` to write into the correct section of the new envelope.
3. Run ratio computation on Stage A benchmark outputs with the new schema and confirm values are numerically identical.
4. Confirm `output["ratios"]` is accessible at the same path as before.

**Primary files**
- `financial_ratios/scripts/field_resolver.py`
- `financial_ratios/scripts/ratio_enricher.py`

**Exit checks**
- Ratio pipeline produces numerically identical results before and after the schema migration on benchmark filings.
- No `KeyError` or `AttributeError` in any existing script after the schema change.

---

## Sequencing and Dependencies

```
WS1 (top-level sections)
  ├── WS2 (AggregatedMetric expansion)    ← parallel
  ├── WS3 (provenance section)            ← parallel
  └── WS4 (null/missing semantics)        ← parallel, feeds into WS2
WS1 + WS2 + WS3 + WS4
  └── WS5 (versioning + validation)
WS1–WS5
  └── WS6 (backward compatibility verification)
```

- WS1 must be defined first as the envelope all other workstreams populate.
- WS2, WS3, and WS4 proceed in parallel once WS1 structure is agreed.
- WS5 requires WS1–WS4 content to be meaningful.
- WS6 is the final integration check run against assembled Stage A benchmark outputs.

---

## Verification Checklist (Stage B Exit)

- [ ] `schema_version: "1.0"` present in all compressed benchmark outputs.
- [ ] `company_context` and `filing_context` sections populated from pipeline metadata.
- [ ] `statement_metrics` entries include `status`, `yoy_change`, and `scale`.
- [ ] `market_metrics` section present with `"not_fetched"` stubs for Stage C fields.
- [ ] `ratios` section shape unchanged and values numerically identical on benchmark filings.
- [ ] `provenance` section includes `run_id`, `aggregated_at`, and `pipeline_version`.
- [ ] Schema validator passes on benchmark outputs without violations.
- [ ] `field_resolver`, `ratio_enricher`, and `ratio_calculation` all run without modification or with minimal adapter updates.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Wrapping flat dict in envelope breaks `field_resolver` key access | Update `field_resolver` to resolve from `statement_metrics` sub-dict; thin compatibility shim as fallback |
| `AggregatedMetric` expansion causes dataclass serialization regressions | All new fields optional with `None` defaults; diff `_to_jsonable` output before and after |
| Schema versioning adds maintenance overhead with no immediate benefit | Keep versioning a single string key; enforcement only activates at Stage E write time |
| Provenance KPI fields require evaluation artifact before aggregation | KPI fields are optional and `null` when evaluation artifact is not supplied |

---

## Deliverables

1. Updated `AggregatedMetric` dataclass with `status`, `yoy_change`, `yoy_unit`, `scale`, `statement_type_confidence`, `source_raw_label`.
2. New `Provenance` dataclass populated in `financial_ratios/main.py`.
3. `CompanyRecord` (or equivalent) top-level model wrapping all six canonical sections.
4. Null/missing semantics documented and applied consistently across all sections.
5. `validate_enriched_record()` validation helper with warning-only behavior.
6. `schema_version: "1.0"` applied to all compressed outputs.
7. Backward compatibility confirmed — numerically identical ratio results on benchmark filings.
8. Handoff note for Stage C: `market_metrics` placeholder contract and field stubs.
