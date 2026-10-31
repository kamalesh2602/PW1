"""
Tests for incorporating experiment CSV logs into PW1 M8 evaluation system.
Verifies historical log preservation, schema integrity (31 columns), idempotency,
paired baseline-vs-dynamic comparisons, and artifact traceability.
"""

import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.evaluation.logger import (
    CSV_FIELDNAMES,
    HISTORICAL_BASELINE_COUNT,
    ExperimentLogger,
    logger,
)
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data" / "m8"
CSV_PATH = DATA_DIR / "m8_experiments.csv"
LEGACY_CSV_PATH = BACKEND_DIR / "data" / "m8_experiments.csv"


@pytest.fixture
def test_client():
    return TestClient(app)


def test_historical_records_preserved():
    """Verify that all historical records up to HISTORICAL_BASELINE_COUNT remain intact."""
    assert CSV_PATH.exists(), "Master CSV does not exist"
    with open(CSV_PATH, mode="r", newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) >= HISTORICAL_BASELINE_COUNT, (
        f"Expected at least {HISTORICAL_BASELINE_COUNT} records, found {len(reader)}"
    )

    # First record check (earliest historical log)
    assert reader[0]["evaluation_id"] == "eval_20261016_040934_b002_e0b94c"
    # Row 60 check (boundary of historical log before new incorporation)
    assert reader[60]["evaluation_id"] == "eval_20261030_085559_b004_76a1ac"


def test_incorporated_record_counts():
    """Verify that exactly 40 records (20 Java + 20 Python) were appended, totaling 101."""
    with open(CSV_PATH, mode="r", newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 101, f"Expected 101 total records, found {len(reader)}"

    # Check legacy CSV mirror
    assert LEGACY_CSV_PATH.exists(), "Legacy CSV does not exist"
    with open(LEGACY_CSV_PATH, mode="r", newline="", encoding="utf-8") as f:
        legacy_reader = list(csv.DictReader(f))
    assert len(legacy_reader) == 101, f"Expected 101 records in legacy CSV, found {len(legacy_reader)}"

    # Appended rows (rows 61..100)
    appended_rows = reader[HISTORICAL_BASELINE_COUNT:]
    assert len(appended_rows) == 40

    py_rows = [r for r in appended_rows if r["language"] == "python"]
    ja_rows = [r for r in appended_rows if r["language"] == "java"]

    assert len(py_rows) == 20, f"Expected 20 Python records, found {len(py_rows)}"
    assert len(ja_rows) == 20, f"Expected 20 Java records, found {len(ja_rows)}"

    # 10 baseline + 10 dynamic for Python
    assert len([r for r in py_rows if r["mode"] == "baseline"]) == 10
    assert len([r for r in py_rows if r["mode"] == "dynamic"]) == 10

    # 10 baseline + 10 dynamic for Java
    assert len([r for r in ja_rows if r["mode"] == "baseline"]) == 10
    assert len([r for r in ja_rows if r["mode"] == "dynamic"]) == 10


def test_all_31_columns_preserved():
    """Verify that all 31 columns are preserved and correctly typed in newly appended records."""
    assert len(CSV_FIELDNAMES) == 31, f"Expected 31 columns, found {len(CSV_FIELDNAMES)}"

    with open(CSV_PATH, mode="r", newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    appended = reader[HISTORICAL_BASELINE_COUNT:]
    for i, row in enumerate(appended):
        # All 31 columns present in row dictionary
        for col in CSV_FIELDNAMES:
            assert col in row, f"Missing column {col} in appended row {i}"

        # Verify key identifiers and modes
        assert row["evaluation_id"], f"Empty evaluation_id in row {i}"
        assert row["experiment_id"], f"Empty experiment_id in row {i}"
        assert row["bug_id"] in [f"B{n:03d}" for n in range(1, 11)]
        assert row["mode"] in ("baseline", "dynamic")
        assert row["language"] in ("python", "java")

        # Verify token metrics
        assert int(row["context_chars"]) > 0
        assert int(row["total_tokens"]) > 0
        assert row["token_usage_available"] in ("True", "TRUE", "true")

        # Verify execution and verification fields
        assert float(row["total_experiment_time_ms"]) > 0
        assert row["status"] == "completed"
        assert row["root_cause_identified"] in ("True", "False", "TRUE", "FALSE")
        assert row["fix_generated"] in ("True", "False", "TRUE", "FALSE")
        assert row["re_execution_passed"] in ("True", "False", "TRUE", "FALSE")


def test_idempotency_prevents_duplicate_imports():
    """Verify that importing the CSV files again skips all duplicates without growing the dataset."""
    py_csv = WORKSPACE_DIR / "Python_Complete_results_PW1(1).csv"
    ja_csv = WORKSPACE_DIR / "java csv pw1 - m8_experiments(1).csv"

    # Re-import Python CSV
    res_py = logger.import_csv_file(py_csv, generate_artifacts=False)
    assert res_py["imported"] == 0
    assert res_py["duplicates_skipped"] == 20

    # Re-import Java CSV
    res_ja = logger.import_csv_file(ja_csv, generate_artifacts=False)
    assert res_ja["imported"] == 0
    assert res_ja["duplicates_skipped"] == 20

    # Total records remains 101
    records = logger.get_experiments(limit=500)
    assert len(records) == 101


def test_baseline_versus_dynamic_comparisons():
    """Verify paired baseline vs dynamic comparisons across all 10 Java and 10 Python bugs."""
    records = logger.get_experiments(limit=100)
    latest_40 = records[:40]

    by_lang_bug: dict[tuple[str, str], dict[str, any]] = {}
    for r in latest_40:
        key = (r.language.lower(), r.bug_id.upper())
        by_lang_bug.setdefault(key, {})
        if r.mode == "baseline":
            by_lang_bug[key]["baseline"] = r
        elif r.mode == "dynamic":
            by_lang_bug[key]["dynamic"] = r

    # Validate Python bugs B001 to B010
    for i in range(1, 11):
        bug_id = f"B{i:03d}"
        pair = by_lang_bug.get(("python", bug_id))
        assert pair is not None, f"Missing Python pair for {bug_id}"
        assert "baseline" in pair and "dynamic" in pair, f"Incomplete pair for Python {bug_id}"

        b_rec = pair["baseline"]
        d_rec = pair["dynamic"]
        assert b_rec.context_chars > d_rec.context_chars, (
            f"Python {bug_id}: baseline context ({b_rec.context_chars}) should exceed dynamic ({d_rec.context_chars})"
        )
        assert d_rec.context_reduction_percent is not None
        assert d_rec.context_reduction_percent > 0.0

    # Validate Java bugs B001 to B010
    for i in range(1, 11):
        bug_id = f"B{i:03d}"
        pair = by_lang_bug.get(("java", bug_id))
        assert pair is not None, f"Missing Java pair for {bug_id}"
        assert "baseline" in pair and "dynamic" in pair, f"Incomplete pair for Java {bug_id}"

        b_rec = pair["baseline"]
        d_rec = pair["dynamic"]
        assert b_rec.context_chars > d_rec.context_chars, (
            f"Java {bug_id}: baseline context ({b_rec.context_chars}) should exceed dynamic ({d_rec.context_chars})"
        )
        assert d_rec.context_reduction_percent is not None
        assert d_rec.context_reduction_percent > 0.0


def test_artifact_traceability():
    """Verify that evaluation summaries and events can be retrieved for newly imported evaluations."""
    # Java B001 evaluation summary
    ja_summary = logger.get_evaluation_summary("eval_20261030_110720_b001_3d3f27")
    assert ja_summary is not None
    assert ja_summary["bug_id"] == "B001"
    assert ja_summary["language"] == "java"
    assert ja_summary["metrics"]["context_reduction_percent"] == 42.63

    # Java B001 events
    ja_events = logger.get_evaluation_events("eval_20261030_110720_b001_3d3f27")
    assert len(ja_events) > 0

    # Python B001 evaluation summary
    py_summary = logger.get_evaluation_summary("eval_20261018_070016_b001_ae6e8e")
    assert py_summary is not None
    assert py_summary["bug_id"] == "B001"
    assert py_summary["language"] == "python"
    assert py_summary["metrics"]["context_reduction_percent"] == 88.58

    # Python B001 events
    py_events = logger.get_evaluation_events("eval_20261018_070016_b001_ae6e8e")
    assert len(py_events) > 0


def test_api_experiments_order_and_limit(test_client):
    """Verify API endpoint GET /evaluation/experiments returns latest records first."""
    resp = test_client.get("/evaluation/experiments?limit=100")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 100
    # Latest 20 are Java runs (most recent timestamps)
    assert data[0]["language"] == "java"
    assert data[0]["bug_id"] == "B010"

    # API summary endpoint
    sum_resp = test_client.get("/evaluation/experiments/eval_20261030_110720_b001_3d3f27/summary")
    assert sum_resp.status_code == 200
    assert sum_resp.json()["bug_id"] == "B001"

    # API import endpoint idempotency
    import_resp = test_client.post("/evaluation/import")
    assert import_resp.status_code == 200
    import_data = import_resp.json()
    assert import_data["status"] == "success"
    # All files skipped since already imported
    for item in import_data["imported_files"]:
        assert item["imported"] == 0
        assert item["duplicates_skipped"] == 20

