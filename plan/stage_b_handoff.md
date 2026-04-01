# Stage B Handoff Note

## Scope

This handoff summarizes Stage B implementation status after completing WS1 through WS6 in the canonical enriched data model migration.

## Stage B Guarantees

1. Canonical envelope is emitted for each compressed filing output with stable top-level keys:
   - `schema_version`
   - `company_context`
   - `filing_context`
   - `statement_metrics`
   - `market_metrics`
   - `ratios`
   - `provenance`
2. Existing ratio consumer access path remains stable at `output["ratios"]`.
3. `AggregatedMetric` entries are enriched with status and provenance-ready fields.
4. Provenance is populated per run with unique `run_id`, timestamps, and optional KPI evaluation data.
5. Market placeholders are pre-seeded for Stage C (`not_fetched` contract).
6. Schema validation is available and executed in warning-only mode in Stage B.

## Workstream Completion

1. WS1: Top-level canonical sections implemented in pipeline output assembly.
2. WS2: `AggregatedMetric` expanded and populated from selected parser rows.
3. WS3: `Provenance` dataclass added and populated from runtime + optional evaluation artifact.
4. WS4: Null/missing semantics standardized with status tags and market source-status validation.
5. WS5: `validate_enriched_record()` implemented in `financial_ratios/models/validation.py` and invoked in `main.py`.
6. WS6: Backward compatibility shims implemented for resolver/enricher input shape handling and verified.

## Retained Earnings Root-Cause Resolution

Issue observed:

- AAPL baseline parity drift for `retained_earnings_to_assets` due retained earnings resolving where baseline had missing input.

Root cause traced to Plan A:

- In parser normalization maps, `accumulated_deficit` was being mapped directly to `retained_earnings`.

Fixes applied:

1. Removed `accumulated_deficit -> retained_earnings` mapping in `pdf_parser/models/normalization_maps.py`.
2. Added semantic guard in `financial_ratios/scripts/field_resolver.py` so retained earnings resolution rejects pure "Accumulated deficit" sources unless retained-earnings wording is explicitly present.
3. Removed broad `accumulated_deficit` retained-earnings alias in resolver alias table.

Result:

- Baseline parity for ratio values on AAPL and DUOL restored (`PASS`).

## Validation Evidence

1. Schema validator on benchmark outputs: PASS (0 violations for AAPL/DUOL/MO).
2. Ratio contract checks: PASS.
3. WS6 baseline numeric comparison against `baselines/stage_a_ws1` for AAPL and DUOL: PASS.
4. Provenance checks:
   - KPI fields null when `--evaluation` omitted.
   - KPI fields populated when `--evaluation` provided.
   - `run_id` unique across consecutive runs.

## Files Updated In Stage B

- `financial_ratios/main.py`
- `financial_ratios/models/models.py`
- `financial_ratios/models/validation.py`
- `financial_ratios/scripts/aggregator.py`
- `financial_ratios/scripts/field_resolver.py`
- `financial_ratios/scripts/ratio_enricher.py`
- `pdf_parser/models/normalization_maps.py`
- `plan/plan_B.md`

## Remaining Risks and Follow-ups

1. Parser normalization fix affects newly generated statement artifacts; existing historical artifacts may still carry old canonical labels unless regenerated.
2. Stage E should switch validator behavior from warning-only to hard-fail at write time, as planned.
3. Stage C can now safely consume market stubs without schema changes.

## Handoff Recommendation

Stage B can be considered implementation-complete for WS1-WS6 and is ready to hand off to Stage C and Stage E integration work.
