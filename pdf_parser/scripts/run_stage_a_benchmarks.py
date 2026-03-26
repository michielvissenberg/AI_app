"""Run Stage A benchmark extraction + evaluation with mandatory gate artifacts.

This script executes the parser pipeline and evaluation gate for each configured filing,
writes one evaluation artifact per filing, and outputs a KPI trend summary table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PDF_PARSER_ROOT = PROJECT_ROOT / "pdf_parser"
if str(PDF_PARSER_ROOT) not in sys.path:
    sys.path.insert(0, str(PDF_PARSER_ROOT))

from main import run_pipeline  # noqa: E402
from evaluation.evaluation import (  # noqa: E402
    DEFAULT_GATE_THRESHOLDS,
    DEFAULT_NUMERIC_TOLERANCE,
    _load_json,
    build_evaluation_report,
    load_expected_cases,
)


STAGE_A_TARGET_BENCHMARK_COUNT = 3

DEFAULT_BENCHMARKS: List[Dict[str, Any]] = [
    {
        "name": "AAPL_2025_10K",
        "pdf": "data_raw/AAPL.pdf",
        "company": "Apple Inc.",
        "ticker": "AAPL",
        "report_type": "10-K",
        "period_ending": "2025-09-27",
        "expected": "data_raw/AAPL_expected.json",
        "use_default_expected": False,
    },
    {
        "name": "DUOL_2025_10K",
        "pdf": "data_raw/DUOL.pdf",
        "company": "Duolingo, Inc.",
        "ticker": "DUOL",
        "report_type": "10-K",
        "period_ending": "2025-12-31",
        "expected": "data_raw/DUOL_expected.json",
        "use_default_expected": False,
    },
]


def _resolve_path(relative_or_abs: Optional[str]) -> Optional[Path]:
    """Resolves a possibly-relative path against project root."""
    if not relative_or_abs:
        return None

    candidate = Path(relative_or_abs)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def _load_benchmarks(config_path: Optional[str]) -> List[Dict[str, Any]]:
    """Loads benchmark config JSON or falls back to default benchmark set."""
    if not config_path:
        return DEFAULT_BENCHMARKS

    resolved = _resolve_path(config_path)
    if resolved is None or not resolved.exists():
        raise FileNotFoundError(f"Benchmark config file not found: {config_path}")

    payload = _load_json(resolved)
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, list) or not benchmarks:
        raise ValueError("Benchmark config must contain a non-empty 'benchmarks' list.")
    return benchmarks


def _build_thresholds(args: argparse.Namespace) -> Dict[str, float]:
    """Builds KPI threshold dictionary from CLI arguments."""
    return {
        "statement_detection_accuracy": float(args.statement_threshold),
        "line_item_mapping_accuracy": float(args.mapping_threshold),
        "numeric_parse_accuracy": float(args.numeric_threshold),
    }


def _load_expected_for_benchmark(benchmark: Dict[str, Any]) -> tuple[List[Dict[str, Any]], bool]:
    """Loads expected cases for a benchmark and flags missing expected definitions."""
    expected_path = _resolve_path(benchmark.get("expected"))
    use_default_expected = bool(benchmark.get("use_default_expected", False))

    if expected_path is not None:
        if expected_path.exists():
            return load_expected_cases(expected_path), False
        return [], True

    if use_default_expected:
        return load_expected_cases(None), False

    return [], True


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Writes JSON payload to disk with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def run(args: argparse.Namespace) -> int:
    """Runs extraction + evaluation across benchmark set and writes summary artifacts."""
    thresholds = _build_thresholds(args)
    tolerance = float(args.tolerance)
    output_dir = _resolve_path(args.output_dir)
    if output_dir is None:
        raise ValueError("Output directory must be provided.")

    benchmarks = _load_benchmarks(args.benchmarks_config)
    trend_rows: List[Dict[str, Any]] = []
    any_failures = False

    for benchmark in benchmarks:
        name = benchmark.get("name") or benchmark.get("ticker") or "unknown"
        ticker = benchmark.get("ticker") or "TBD"
        pdf_path = _resolve_path(benchmark.get("pdf"))
        if pdf_path is None or not pdf_path.exists():
            any_failures = True
            trend_rows.append(
                {
                    "benchmark": name,
                    "ticker": ticker,
                    "verdict": "fail",
                    "reason": f"Missing source PDF: {benchmark.get('pdf')}",
                }
            )
            continue

        existing_statement_path = output_dir / f"{pdf_path.stem}_statement.json"
        if bool(args.reuse_existing_statements) and existing_statement_path.exists():
            json_path = existing_statement_path
            print(f"Reusing existing statement artifact: {json_path}")
        else:
            json_path, _markdown_path, _diagnostics_path = run_pipeline(
                pdf_path=pdf_path,
                engine=str(args.engine),
                company_name=str(benchmark.get("company") or ticker),
                ticker=ticker,
                report_type=str(benchmark.get("report_type") or "10-K"),
                period_ending=str(benchmark.get("period_ending") or "1970-01-01"),
                output_dir=output_dir,
                docling_device=str(args.docling_device),
                docling_chunk_size=max(1, int(args.docling_chunk_size)),
                docling_num_threads=max(1, int(args.docling_num_threads)),
            )

        extracted_statement = _load_json(json_path)
        expected_cases, expected_cases_missing = _load_expected_for_benchmark(benchmark)
        report = build_evaluation_report(
            extracted_statement=extracted_statement,
            expected_cases=expected_cases,
            tolerance=tolerance,
            thresholds=thresholds,
            expected_cases_missing=expected_cases_missing,
        )

        evaluation_path = output_dir / f"{Path(json_path).stem.replace('_statement', '')}_evaluation.json"
        _write_json(evaluation_path, report)

        verdict = report["gate"]["verdict"]
        if verdict != "pass":
            any_failures = True

        measured = report["kpis"]["measured"]
        trend_rows.append(
            {
                "benchmark": name,
                "ticker": ticker,
                "statement_json": str(json_path),
                "evaluation_json": str(evaluation_path),
                "verdict": verdict,
                "statement_detection_accuracy": measured["statement_detection_accuracy"],
                "line_item_mapping_accuracy": measured["line_item_mapping_accuracy"],
                "numeric_parse_accuracy": measured["numeric_parse_accuracy"],
                "coverage_rate": report["coverage"]["coverage_rate"],
                "blocking_reasons": report["gate"]["blocking_reasons"],
            }
        )

    summary_payload = {
        "evaluation_config": {
            "numeric_tolerance": tolerance,
            "gate_thresholds": thresholds,
        },
        "benchmark_progress": {
            "configured_benchmarks": len(benchmarks),
            "target_benchmarks": STAGE_A_TARGET_BENCHMARK_COUNT,
            "target_met": len(benchmarks) >= STAGE_A_TARGET_BENCHMARK_COUNT,
        },
        "trend": trend_rows,
    }

    summary_path = output_dir / "stage_a_benchmark_summary.json"
    _write_json(summary_path, summary_payload)

    print("Stage A benchmark run complete")
    print(f"Summary artifact: {summary_path}")
    print(
        "Benchmark target progress: "
        f"{len(benchmarks)}/{STAGE_A_TARGET_BENCHMARK_COUNT} configured"
    )
    for row in trend_rows:
        print(
            f"- {row.get('benchmark')} ({row.get('ticker')}): verdict={row.get('verdict')} "
            f"statement={row.get('statement_detection_accuracy', 'n/a')} "
            f"mapping={row.get('line_item_mapping_accuracy', 'n/a')} "
            f"numeric={row.get('numeric_parse_accuracy', 'n/a')}"
        )

    return 1 if any_failures else 0


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds CLI parser for benchmark matrix execution."""
    parser = argparse.ArgumentParser(description="Run extraction + evaluation across Stage A benchmark filings.")
    parser.add_argument("--benchmarks-config", default=None, help="Optional JSON file with benchmark list.")
    parser.add_argument("--engine", choices=["docling"], default="docling")
    parser.add_argument("--output-dir", default="data_raw", help="Directory for statement/evaluation outputs.")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_NUMERIC_TOLERANCE)
    parser.add_argument(
        "--statement-threshold",
        type=float,
        default=DEFAULT_GATE_THRESHOLDS["statement_detection_accuracy"],
    )
    parser.add_argument(
        "--mapping-threshold",
        type=float,
        default=DEFAULT_GATE_THRESHOLDS["line_item_mapping_accuracy"],
    )
    parser.add_argument(
        "--numeric-threshold",
        type=float,
        default=DEFAULT_GATE_THRESHOLDS["numeric_parse_accuracy"],
    )
    parser.add_argument("--docling-device", choices=["auto", "cpu", "cuda", "mps", "xpu"], default="auto")
    parser.add_argument("--docling-chunk-size", type=int, default=8)
    parser.add_argument("--docling-num-threads", type=int, default=4)
    parser.add_argument(
        "--reuse-existing-statements",
        action="store_true",
        help="Skip extraction when <pdf_stem>_statement.json already exists in output dir.",
    )
    return parser


def main() -> int:
    """CLI entrypoint for Stage A benchmark matrix runner."""
    parser = build_arg_parser()
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
