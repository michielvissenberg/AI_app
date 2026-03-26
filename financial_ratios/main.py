import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from scripts.aggregator import aggregate_statement_items_with_diagnostics
from scripts.ratio_enricher import add_ratios_to_compressed_payload


def _to_jsonable(data):
	"""Recursively converts dataclasses and nested structures to JSON-serializable format."""
	if is_dataclass(data):
		return asdict(data)
	if isinstance(data, dict):
		return {str(key): _to_jsonable(value) for key, value in data.items()}
	if isinstance(data, list):
		return [_to_jsonable(item) for item in data]
	return data


def parse_args() -> argparse.Namespace:
	"""Parses CLI arguments for the statement aggregation and ratio computation pipeline."""
	parser = argparse.ArgumentParser(description="Aggregate statement JSON into compressed JSON.")
	parser.add_argument("input_path", help="Path to the input statement JSON file.")
	return parser.parse_args()


def main() -> int:
	"""Aggregates statement items, computes financial ratios, and exports compressed payload with diagnostics."""
	args = parse_args()
	input_path = Path(args.input_path)
	raw_statement_payload = json.loads(input_path.read_text(encoding="utf-8"))

	aggregated, duplicate_diagnostics = aggregate_statement_items_with_diagnostics(input_path)
	compressed_payload = _to_jsonable(aggregated)
	output_payload = add_ratios_to_compressed_payload(
		compressed_payload=compressed_payload,
		aggregated_metrics=aggregated,
		raw_statement_payload=raw_statement_payload,
	)

	output_dir = Path(__file__).resolve().parents[1] / "data_compressed"
	output_dir.mkdir(parents=True, exist_ok=True)
	output_path = output_dir / f"{input_path.stem}.json"
	diagnostics_path = output_dir / f"{input_path.stem}_duplicate_diagnostics.json"

	with open(output_path, "w", encoding="utf-8") as handle:
		json.dump(output_payload, handle, indent=2)

	with open(diagnostics_path, "w", encoding="utf-8") as handle:
		json.dump(_to_jsonable(duplicate_diagnostics), handle, indent=2)

	return 0


if __name__ == "__main__":
	raise SystemExit(main())

