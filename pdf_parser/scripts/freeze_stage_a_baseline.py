"""Freeze Stage A Workstream 1 baseline artifacts for AAPL and DUOL.

This script snapshots current extraction and compression artifacts into a
versioned baseline directory and writes a manifest with SHA256 checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


REQUIRED_BASELINE_FILES = [
    "data_raw/AAPL_statement.json",
    "data_raw/AAPL_statement.md",
    "data_raw/AAPL_evaluation.json",
    "data_raw/DUOL_statement.json",
    "data_raw/DUOL_statement.md",
    "data_compressed/AAPL_statement.json",
    "data_compressed/DUOL_statement.json",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_required_files(project_root: Path, output_dir: Path) -> List[Dict[str, str]]:
    copied_files: List[Dict[str, str]] = []

    for relative_file in REQUIRED_BASELINE_FILES:
        source_path = project_root / relative_file
        if not source_path.exists():
            raise FileNotFoundError(f"Missing required baseline file: {source_path}")

        target_path = output_dir / relative_file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

        copied_files.append(
            {
                "path": relative_file,
                "sha256": _sha256(target_path),
            }
        )

    return copied_files


def run(output_dir: Path) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_files = _copy_required_files(project_root=project_root, output_dir=output_dir)

    manifest = {
        "baseline_name": "stage_a_ws1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(project_root),
        "files": copied_files,
    }

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return manifest_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze Stage A Workstream 1 baseline artifacts.")
    parser.add_argument(
        "--output-dir",
        default="baselines/stage_a_ws1",
        help="Target baseline directory (relative to project root by default).",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    manifest_path = run(output_dir=output_dir)
    print(f"Baseline frozen successfully. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
