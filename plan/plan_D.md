# Stage D - Extended Ratio Computation

## Objective

Stage D expands the ratio engine from statement-only metrics to market-aware valuation and quality metrics, using the Stage B canonical schema and Stage C market enrichment outputs. The implementation must preserve the existing ratio result shape, remain deterministic, and make missing inputs explicit.

## Scope

**Included**
- Add market-aware ratio definitions and calculation logic.
- Extend field resolution to support statement + market sources.
- Keep strict output contract (`value`, `unit`, `description`, `inputs`, `status`, `missing_fields`, `error`).
- Add formula safeguards (zero division, sign sanity, stale market flags).
- Build tests for success, missing-input, and edge-case behavior.

**Excluded**
- Market data fetching and provider behavior (Stage C).
- Persistence/indexing concerns (Stage E).
- LLM analysis generation (Stage F).
- UI work (Phase 4).

## Hard Quality Gates for Stage D Exit

1. All new ratios return deterministic outputs for fixed inputs.
2. Existing ratios remain unchanged in values and shape on benchmark records.
3. Missing required inputs always yield `status: missing_inputs` with field list.
4. Any denominator = 0 case is handled safely (no crash, no inf/NaN output).
5. Ratio output remains backward-compatible with current consumers.

## Workstream 0: Ratio Engine Readiness and Bootstrap

**Goal**
Ensure Stage D can proceed even if ratio module files have moved or are temporarily missing.

**Tasks**
1. Confirm active module entrypoints for:
   - ratio definitions,
   - field resolver,
   - ratio computation,
   - payload enricher.
2. If modules are missing, restore minimal ratio scaffold:
   - ratio definition map,
   - computation dispatcher,
   - missing-input error path,
   - integration hook into enriched output.
3. Add compatibility shim for both:
   - old flat payloads,
   - Stage B envelope (`statement_metrics`, `market_metrics`, `ratios`).

**Exit checks**
1. A callable ratio engine exists for Stage B/C outputs.
2. Existing baseline ratios run end-to-end on benchmark payload.

## Workstream 1: Ratio Catalog and Formula Specification

**Goal**
Define the exact Stage D ratio set, formulas, units, and input requirements.

**Initial market-aware ratio catalog (MVP)**
1. `price_to_earnings` (P/E)
   - Formula: `share_price / diluted_eps`
2. `price_to_sales` (P/S)
   - Formula: `market_cap / revenue`
3. `price_to_book` (P/B)
   - Formula: `market_cap / total_shareholders_equity`
4. `enterprise_value_to_sales` (EV/Sales)
   - Formula: `enterprise_value / revenue`
5. `enterprise_value_to_ebit` (EV/EBIT)
   - Formula: `enterprise_value / operating_income`
6. `free_cash_flow_yield` (optional if FCF available)
   - Formula: `free_cash_flow / market_cap`

**Optional follow-up ratios (Phase D.2)**
1. `earnings_yield` = `net_income / market_cap`
2. `ev_to_ebitda` if EBITDA field exists or derivation is well-defined.
3. `net_debt_to_ebit` = `(total_debt - cash_and_cash_equivalents_market) / operating_income`

**Tasks**
1. Add formula definitions with required fields and textual descriptions.
2. Define unit and interpretation metadata per ratio.
3. Tag each ratio as `market_required` or `statement_only`.

**Exit checks**
1. Catalog is complete and documented in code.
2. Each ratio has required field list, formula, and unit semantics.

## Workstream 2: Field Resolution Across Statement and Market Sections

**Goal**
Resolve required inputs from Stage B/C canonical payload without ambiguity.

**Resolution order policy**
1. Primary for accounting fields: `statement_metrics`.
2. Primary for market fields: `market_metrics`.
3. Backward compatibility fallback: legacy top-level flat fields (if present).
4. No inferred fallback from unrelated labels.

**Key mapping rules**
1. `diluted_eps` from statement metrics.
2. `enterprise_value` from market metrics (or precomputed Stage C derived field).
3. `cash_and_cash_equivalents_market` used only for market-context formulas.
4. `revenue`, `operating_income`, `total_shareholders_equity` from statement metrics.

**Tasks**
1. Extend resolver to accept canonical envelope input.
2. Return structured missing-field diagnostics:
   - missing key names,
   - source section expected,
   - observed status.
3. Preserve strict mode toggle for development/testing.

**Exit checks**
1. Resolver correctly handles mixed statement+market input requirements.
2. Missing-input diagnostics are clear and complete.

## Workstream 3: Safe Formula Engine and Edge-Case Rules

**Goal**
Prevent mathematically invalid outputs and enforce predictable behavior.

**Safety rules**
1. If numerator or denominator is null -> `value = null`, `status = missing_inputs`.
2. If denominator == 0 -> `value = null`, `status = invalid_denominator`, include error.
3. If denominator < 0 for ratios where negative denominator invalidates interpretation:
   - policy per ratio:
     - allow with warning for some (for example P/E with negative EPS often not meaningful),
     - otherwise return null with `invalid_denominator`.
4. Never return `inf`, `-inf`, or `nan` in JSON output.

**Staleness and quality flags**
1. If any market input has `source_status = stale`:
   - keep computation if mathematically valid,
   - add `warnings` list with stale-input note.
2. If market input status is `provider_error` or `missing_from_provider`:
   - mark missing inputs path.

**Tasks**
1. Add guarded divide helper and validation utilities.
2. Add per-ratio denominator policy map.
3. Extend output payload with optional `warnings` list (without breaking existing keys).

**Exit checks**
1. No invalid numeric outputs in any ratio result.
2. Edge-case behavior is consistent across all ratios.

## Workstream 4: Output Contract Preservation

**Goal**
Guarantee the result structure remains compatible with existing consumers while adding richer diagnostics.

**Required output shape per ratio**
- `value`
- `unit`
- `description`
- `inputs`
- `status`
- `missing_fields` (when applicable)
- `error` (when applicable)

**Allowed additive fields**
- `warnings` (optional)
- `quality_flags` (optional)
- `input_statuses` (optional)

**Tasks**
1. Keep existing keys and semantics unchanged.
2. Add optional diagnostics only as additive fields.
3. Validate JSON serialization of all ratio outputs.

**Exit checks**
1. Existing integrations parsing old keys continue to work.
2. New diagnostics do not alter legacy behavior.

## Workstream 5: Ratio Integration into Enrichment Pipeline

**Goal**
Integrate extended ratios into the Stage B/C envelope cleanly.

**Tasks**
1. Ensure ratio computation runs after market enrichment step.
2. Merge results into `ratios` section without mutating statement or market sections.
3. Add ratio-run metadata to provenance:
   - `ratio_engine_version`,
   - `ratios_computed_count`,
   - `ratios_missing_count`.
4. Add optional CLI flag to toggle extended-ratio set on/off for controlled rollout.

**Exit checks**
1. Pipeline emits both base and extended ratios in a single ratios section.
2. Provenance includes ratio-run summary fields.

## Workstream 6: Validation and Test Matrix

**Goal**
Prove correctness, stability, and backward compatibility before Stage E.

**Unit tests**
1. Formula tests for each new ratio.
2. Denominator-zero and null-input tests.
3. Negative-denominator policy tests.
4. Stale market input warning tests.

**Integration tests**
1. AAPL enriched payload with full market fields -> all Stage D ratios computed where applicable.
2. DUOL enriched payload with partial fields -> missing-input behavior validated.

**Regression tests**
1. Existing statement-only ratios must match pre-Stage-D outputs on benchmark fixtures.
2. Snapshot tests for ratio JSON output schema and key ordering (if deterministic writer used).

**Exit checks**
1. All Stage D tests pass.
2. Regression confirms no drift in existing ratio values.

## Workstream 7: Stage E Handoff Package

**Goal**
Provide persistence layer with stable ratio schema and operational metadata.

**Tasks**
1. Publish ratio schema reference for storage indexing:
   - ratio name,
   - value type,
   - status conventions,
   - warnings semantics.
2. Define indexing hints for Stage E:
   - searchable ratio keys,
   - status filters (for example missing vs valid),
   - timestamp/provenance links.
3. Provide three sample enriched payloads:
   - full-data success case,
   - partial-input case,
   - stale-market warning case.

**Exit checks**
1. Stage E can ingest ratio outputs without transformation.
2. Handoff artifacts cover full and failure scenarios.

## Sequencing and Dependencies

1. Step 1: Workstream 0 readiness/bootstrap.
2. Step 2: Workstream 1 catalog/spec and Workstream 2 resolver extension (parallel).
3. Step 3: Workstream 3 safety engine (depends on 1 and 2).
4. Step 4: Workstream 4 output contract preservation (parallel with late 3).
5. Step 5: Workstream 5 pipeline integration (depends on 2-4).
6. Step 6: Workstream 6 validation/regression (depends on 5).
7. Step 7: Workstream 7 Stage E handoff package.

## Verification Checklist for Stage D Completion

1. Confirm extended ratio catalog is implemented with documented formulas.
2. Confirm all new ratios follow required output contract.
3. Confirm missing inputs produce `missing_inputs` and field list.
4. Confirm denominator errors are handled without crashes or NaN/inf outputs.
5. Confirm stale market inputs surface warnings.
6. Confirm existing ratio values are unchanged versus baseline snapshots.
7. Confirm enriched payload includes ratio-run provenance summary.
8. Confirm Stage E handoff package is complete.

## Risks and Mitigations

1. Risk: inconsistent market field availability causes noisy missing ratios.
   - Mitigation: clear missing-input semantics and strict/lenient modes.
2. Risk: negative earnings make valuation ratios misleading.
   - Mitigation: per-ratio denominator policy with warnings or null results.
3. Risk: schema drift between Stage C and Stage D sections.
   - Mitigation: resolver contract tests against Stage B/C fixture payloads.
4. Risk: current repo state missing ratio modules blocks implementation.
   - Mitigation: Workstream 0 bootstrap track and compatibility shim.
5. Risk: extended diagnostics break existing consumers.
   - Mitigation: additive-only fields, preserve core contract keys.

## Deliverables

1. Stage D ratio catalog with formulas and required fields.
2. Extended field resolver supporting statement + market sources.
3. Safe formula engine with denominator/sign/staleness rules.
4. Backward-compatible ratio output contract implementation.
5. Integration into enriched pipeline with ratio provenance summary.
6. Full unit/integration/regression test pack.
7. Stage E handoff package with schema and sample payloads.
