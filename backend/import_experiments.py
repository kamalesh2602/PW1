#!/usr/bin/env python3
"""
CLI Script for incorporating Python and Java experiment CSV datasets into M8.
Preserves historical records, avoids duplicate imports, and ensures full artifact generation.
"""

import argparse
import shutil
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.evaluation.logger import (
    CSV_FILENAME,
    DEFAULT_DATA_DIR,
    DEFAULT_M8_DATA_DIR,
    logger,
)


def find_csv_file(name: str, candidate_dirs: list[Path]) -> Path:
    """Locate a CSV file by name across candidate directories."""
    for d in candidate_dirs:
        p = d / name
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not find '{name}' in any candidate directory: {[str(d) for d in candidate_dirs]}")


def run_import(python_path: Path | None = None, java_path: Path | None = None, sync_legacy: bool = True) -> int:
    workspace_root = BACKEND_DIR.parent
    candidate_dirs = [workspace_root, BACKEND_DIR / "data", BACKEND_DIR]

    py_name = "Python_Complete_results_PW1(1).csv"
    ja_name = "java csv pw1 - m8_experiments(1).csv"

    py_file = python_path if python_path else find_csv_file(py_name, candidate_dirs)
    ja_file = java_path if java_path else find_csv_file(ja_name, candidate_dirs)

    print("=" * 70)
    print("PW1 M8 Experiment Log Importer")
    print("=" * 70)
    print(f"Target Master CSV:   {logger.csv_path}")
    print(f"Python Source File:  {py_file}")
    print(f"Java Source File:    {ja_file}")

    initial_records = len(logger.get_experiments(limit=500))
    print(f"\nInitial records in master dataset: {initial_records}")

    # 1. Import Python records
    print("\n--- Importing Python Experiments ---")
    py_res = logger.import_csv_file(py_file, generate_artifacts=True)
    print(f"Status: {py_res['message']}")
    print(f"  Rows read:            {py_res['total_rows']}")
    print(f"  Rows imported:        {py_res['imported']}")
    print(f"  Duplicates skipped:   {py_res['duplicates_skipped']}")

    # 2. Import Java records
    print("\n--- Importing Java Experiments ---")
    ja_res = logger.import_csv_file(ja_file, generate_artifacts=True)
    print(f"Status: {ja_res['message']}")
    print(f"  Rows read:            {ja_res['total_rows']}")
    print(f"  Rows imported:        {ja_res['imported']}")
    print(f"  Duplicates skipped:   {ja_res['duplicates_skipped']}")

    # 3. Synchronize legacy root CSV if requested
    if sync_legacy and logger.data_dir == DEFAULT_M8_DATA_DIR:
        legacy_csv = DEFAULT_DATA_DIR / CSV_FILENAME
        try:
            shutil.copy2(logger.csv_path, legacy_csv)
            print(f"\nSynchronized legacy root CSV: {legacy_csv}")
        except Exception as e:
            print(f"Warning: Failed to sync legacy CSV: {e}")

    # 4. Verify total records and comparisons
    all_records = logger.get_experiments(limit=500)
    print(f"\nTotal records in dataset now: {len(all_records)}")

    # Sample from the latest 40 incorporated records
    latest_40 = all_records[:40]
    by_lang_bug: dict[tuple[str, str], dict[str, float]] = {}
    for r in latest_40:
        key = ((r.language or "").lower(), (r.bug_id or "").upper())
        if key not in by_lang_bug:
            by_lang_bug[key] = {}
        if r.mode == "baseline":
            by_lang_bug[key]["baseline_chars"] = r.context_chars
        elif r.mode == "dynamic":
            by_lang_bug[key]["dynamic_chars"] = r.context_chars
            if r.context_reduction_percent is not None:
                by_lang_bug[key]["reduction"] = r.context_reduction_percent

    print("\n" + "=" * 70)
    print("Baseline vs. Dynamic Comparison Summary (Latest Incorporated)")
    print("=" * 70)
    print(f"{'Lang':<8} {'Bug':<6} {'Baseline Ctx':<14} {'Dynamic Ctx':<14} {'Reduction %':<12}")
    print("-" * 70)

    for lang in ["python", "java"]:
        for i in range(1, 11):
            bug_id = f"B{i:03d}"
            info = by_lang_bug.get((lang, bug_id), {})
            b_ctx = info.get("baseline_chars", "-")
            d_ctx = info.get("dynamic_chars", "-")
            red = info.get("reduction", "-")
            print(f"{lang:<8} {bug_id:<6} {str(b_ctx):<14} {str(d_ctx):<14} {str(red):<12}")

    print("=" * 70)
    print("Import verification completed successfully!")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Incorporate M8 PW1 experiment logs into the master dataset.")
    parser.add_argument("--python-csv", type=Path, default=None, help="Path to Python experiments CSV")
    parser.add_argument("--java-csv", type=Path, default=None, help="Path to Java experiments CSV")
    parser.add_argument("--no-sync-legacy", action="store_true", help="Do not sync legacy backend/data/m8_experiments.csv")
    args = parser.parse_args()

    return run_import(
        python_path=args.python_csv,
        java_path=args.java_csv,
        sync_legacy=not args.no_sync_legacy,
    )


if __name__ == "__main__":
    sys.exit(main())
