"""
Experiment logging and research artifact management module for M8.
Logically separates:
- Master tabular evaluation dataset: data/m8/m8_experiments.csv (and legacy data/m8_experiments.csv)
- Global event log: data/m8/m8_events.jsonl
- Per-evaluation artifacts: data/m8/experiments/<evaluation_id>/
    - events.jsonl
    - summary.json
    - baseline.json
    - dynamic.json
- Application / operational logs: logs/application/m8_app.log
"""

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from app.evaluation.models import ComparisonResult, ExperimentRecord
from app.logging_config import get_app_logger

app_logger = get_app_logger("evaluation.logger")

# Paths relative to backend root
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = BACKEND_ROOT / "data"
DEFAULT_M8_DATA_DIR = DEFAULT_DATA_DIR / "m8"
DEFAULT_EXPERIMENTS_DIR = DEFAULT_M8_DATA_DIR / "experiments"
DEFAULT_LOGS_DIR = BACKEND_ROOT / "logs"

CSV_FILENAME = "m8_experiments.csv"
JSONL_FILENAME = "m8_events.jsonl"

_log_lock = Lock()

CSV_FIELDNAMES = [
    "evaluation_id",
    "experiment_id",
    "bug_id",
    "mode",
    "language",
    "model",
    "context_chars",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "token_usage_available",
    "curator_input_tokens",
    "curator_output_tokens",
    "curator_total_tokens",
    "debugger_input_tokens",
    "debugger_output_tokens",
    "debugger_total_tokens",
    "llm_calls",
    "mcp_calls",
    "mcp_query_time_ms",
    "mcp_transport_time_ms",
    "mcp_total_time_ms",
    "llm_time_ms",
    "total_experiment_time_ms",
    "root_cause_identified",
    "fix_generated",
    "fix_correct",
    "re_execution_passed",
    "stop_reason",
    "status",
    "timestamp",
]


class ExperimentLogger:
    """
    Thread-safe logger and research artifact manager for M8 evaluation.
    Maintains clean separation between tabular dataset (CSV), raw telemetry (JSONL),
    and per-run artifact packages (summary.json, baseline.json, dynamic.json, events.jsonl).
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        if data_dir:
            self.data_dir = Path(data_dir)
            self.m8_data_dir = self.data_dir
            self.experiments_dir = self.data_dir / "experiments"
        else:
            self.data_dir = DEFAULT_M8_DATA_DIR
            self.m8_data_dir = DEFAULT_M8_DATA_DIR
            self.experiments_dir = DEFAULT_EXPERIMENTS_DIR

        self.csv_path = self.data_dir / CSV_FILENAME
        self.jsonl_path = self.data_dir / JSONL_FILENAME
        self._ensure_files()

    def _ensure_files(self) -> None:
        """Create directories and CSV header if not present."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

        # Master CSV in data/m8/
        if not self.csv_path.exists():
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writeheader()

    def _print_console_event(
        self,
        event: str,
        evaluation_id: str,
        mode: str,
        step: int,
        data: dict[str, Any],
    ) -> None:
        """Format and print clear, uncluttered console event sequence."""
        if event == "experiment_started":
            print(f"[{event}] eval_id={evaluation_id} mode={mode} bug_id={data.get('bug_id', '')} lang={data.get('language', '')}", flush=True)
        elif event == "execution_completed":
            print(f"[{event}] execution_id={data.get('execution_id', '')} exit_code={data.get('exit_code')} status={data.get('status')}", flush=True)
        elif event == "mcp_retrieval":
            print(f"[{event}] step={step} tool={data.get('mcp_tool')} duration_ms={data.get('duration_ms')} success={data.get('success')}", flush=True)
        elif event == "llm_decision":
            print(f"[{event}] step={step} direction={data.get('direction')} is_sufficient={data.get('is_sufficient')}", flush=True)
        elif event == "curation_completed":
            print(f"[{event}] curated_chars={data.get('curated_context_chars')} mcp_calls={data.get('mcp_calls')} stop_reason={data.get('stop_reason')}", flush=True)
        elif event == "context_prepared":
            print(f"[{event}] baseline_chars={data.get('baseline_context_chars')}", flush=True)
        elif event == "fix_generated":
            print(f"[{event}] fix_generated={data.get('fix_generated')}", flush=True)
        elif event == "re_execution_completed":
            print(f"[{event}] re_execution_passed={data.get('re_execution_passed')} fix_correct={data.get('fix_correct')}", flush=True)
        elif event == "experiment_completed":
            print(f"[{event}] status={data.get('status')} stop_reason={data.get('stop_reason')} total_time_ms={data.get('total_experiment_time_ms')}", flush=True)
        elif event == "evaluation_started":
            print(f"[{event}] evaluation_id={evaluation_id} bug_id={data.get('bug_id', '')}", flush=True)
        elif event == "evaluation_completed":
            print(f"[{event}] status={data.get('status')} time_diff_ms={data.get('time_difference_ms')}", flush=True)
        else:
            details = " ".join(f"{k}={v}" for k, v in data.items() if not isinstance(v, (dict, list)))
            print(f"[{event}] step={step} {details}".strip(), flush=True)

    def log_event(
        self,
        evaluation_id: str,
        experiment_id: str,
        bug_id: str,
        mode: str,
        event: str,
        step: int,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Record a structured lifecycle event both to the global JSONL log
        and to the per-evaluation events.jsonl artifact.
        """
        with _log_lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            clean_eval_id = evaluation_id or "unassigned"
            payload_data = data or {}

            event_entry = {
                "timestamp": now_iso,
                "evaluation_id": clean_eval_id,
                "experiment_id": experiment_id,
                "bug_id": bug_id,
                "mode": mode,
                "event": event,
                "step": step,
                "data": payload_data,
            }

            # 1. Output clean console sequence line
            self._print_console_event(event, clean_eval_id, mode, step, payload_data)

            # 2. Global event log
            try:
                with open(self.jsonl_path, mode="a", encoding="utf-8") as f:
                    f.write(json.dumps(event_entry) + "\n")
            except Exception:
                pass

            # 3. Per-evaluation event log
            try:
                eval_dir = self.experiments_dir / clean_eval_id
                eval_dir.mkdir(parents=True, exist_ok=True)
                with open(eval_dir / "events.jsonl", mode="a", encoding="utf-8") as f:
                    f.write(json.dumps(event_entry) + "\n")
            except Exception:
                pass

            return event_entry

    def log_experiment(self, record: ExperimentRecord, detailed_events: list[dict[str, Any]] | None = None) -> None:
        """
        Record a completed experiment run:
        1. Appends row to master m8_experiments.csv.
        2. Saves baseline.json or dynamic.json artifact in data/m8/experiments/<evaluation_id>/.
        3. Generates/updates summary.json.
        """
        with _log_lock:
            # 1. Format row for CSV
            raw_dict = record.model_dump()
            csv_row: dict[str, Any] = {}
            for field in CSV_FIELDNAMES:
                val = raw_dict.get(field)
                if val is None:
                    csv_row[field] = ""
                elif isinstance(val, bool):
                    csv_row[field] = "True" if val else "False"
                else:
                    csv_row[field] = str(val)

            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                writer.writerow(csv_row)

            # 2. Save individual experiment JSON artifact
            clean_eval_id = record.evaluation_id or "unassigned"
            eval_dir = self.experiments_dir / clean_eval_id
            eval_dir.mkdir(parents=True, exist_ok=True)

            mode_file = "baseline.json" if record.mode == "baseline" else "dynamic.json"
            with open(eval_dir / mode_file, mode="w", encoding="utf-8") as f:
                json.dump(raw_dict, f, indent=2)

            # 3. Create or update summary.json
            summary_file = eval_dir / "summary.json"
            baseline_file = eval_dir / "baseline.json"
            dynamic_file = eval_dir / "dynamic.json"

            existing_summary = None
            if summary_file.exists():
                try:
                    with open(summary_file, mode="r", encoding="utf-8") as sf:
                        existing_summary = json.load(sf)
                except Exception:
                    existing_summary = None

            # If existing summary has paired structure, preserve and update it
            if existing_summary and ("baseline" in existing_summary or "dynamic" in existing_summary):
                if record.mode == "baseline":
                    existing_summary["baseline"] = raw_dict
                else:
                    existing_summary["dynamic"] = raw_dict

                if existing_summary.get("baseline") and existing_summary.get("dynamic"):
                    b_chars = existing_summary["baseline"].get("context_chars", 0)
                    d_chars = existing_summary["dynamic"].get("context_chars", 0)
                    if b_chars > 0 and existing_summary["dynamic"].get("status") == "completed":
                        existing_summary.setdefault("metrics", {})["context_reduction_percent"] = round(
                            ((b_chars - d_chars) / b_chars) * 100.0, 2
                        )
                with open(summary_file, mode="w", encoding="utf-8") as f:
                    json.dump(existing_summary, f, indent=2)
            else:
                # Check if the companion mode file already exists in eval_dir to produce a paired summary
                other_mode_file = dynamic_file if record.mode == "baseline" else baseline_file
                if other_mode_file.exists():
                    try:
                        with open(other_mode_file, mode="r", encoding="utf-8") as omf:
                            other_data = json.load(omf)
                        base_rec = raw_dict if record.mode == "baseline" else other_data
                        dyn_rec = other_data if record.mode == "baseline" else raw_dict
                        b_chars = base_rec.get("context_chars", 0)
                        d_chars = dyn_rec.get("context_chars", 0)
                        ctx_reduct = (
                            round(((b_chars - d_chars) / b_chars) * 100.0, 2)
                            if b_chars > 0 and dyn_rec.get("status") == "completed"
                            else None
                        )

                        b_tok = base_rec.get("total_tokens")
                        d_tok = dyn_rec.get("total_tokens")
                        if (
                            base_rec.get("token_usage_available")
                            and dyn_rec.get("token_usage_available")
                            and b_tok is not None
                            and b_tok > 0
                            and d_tok is not None
                        ):
                            tok_reduct = round(((b_tok - d_tok) / b_tok) * 100.0, 2)
                        else:
                            tok_reduct = None

                        b_time = base_rec.get("total_experiment_time_ms", 0.0)
                        d_time = dyn_rec.get("total_experiment_time_ms", 0.0)

                        paired_payload = {
                            "evaluation_id": record.evaluation_id,
                            "bug_id": record.bug_id,
                            "language": record.language,
                            "model": record.model,
                            "status": record.status,
                            "timestamp": record.timestamp,
                            "metrics": {
                                "context_reduction_percent": ctx_reduct,
                                "token_reduction_percent": tok_reduct,
                                "time_difference_ms": round(d_time - b_time, 2),
                            },
                            "baseline": base_rec,
                            "dynamic": dyn_rec,
                            "traceability": {
                                "evaluation_dir": str(eval_dir),
                                "events_file": str(eval_dir / "events.jsonl"),
                                "summary_file": str(summary_file),
                                "baseline_file": str(baseline_file),
                                "dynamic_file": str(dynamic_file),
                                "csv_dataset": str(self.csv_path),
                            },
                        }
                        with open(summary_file, mode="w", encoding="utf-8") as f:
                            json.dump(paired_payload, f, indent=2)
                    except Exception:
                        pass
                else:
                    # Single mode summary
                    summary_data = {
                        "evaluation_id": record.evaluation_id,
                        "experiment_id": record.experiment_id,
                        "bug_id": record.bug_id,
                        "mode": record.mode,
                        "language": record.language,
                        "model": record.model,
                        "status": record.status,
                        "stop_reason": record.stop_reason,
                        "timestamp": record.timestamp,
                        "context_chars": record.context_chars,
                        "tokens": {
                            "input_tokens": record.input_tokens,
                            "output_tokens": record.output_tokens,
                            "total_tokens": record.total_tokens,
                            "token_usage_available": record.token_usage_available,
                            "curator_total_tokens": record.curator_total_tokens,
                            "debugger_total_tokens": record.debugger_total_tokens,
                        },
                        "timing_ms": {
                            "llm_time_ms": record.llm_time_ms,
                            "mcp_query_time_ms": record.mcp_query_time_ms,
                            "mcp_transport_time_ms": record.mcp_transport_time_ms,
                            "mcp_total_time_ms": record.mcp_total_time_ms,
                            "total_experiment_time_ms": record.total_experiment_time_ms,
                        },
                        "effectiveness": {
                            "root_cause_identified": record.root_cause_identified,
                            "fix_generated": record.fix_generated,
                            "fix_correct": record.fix_correct,
                            "re_execution_passed": record.re_execution_passed,
                        },
                        "traceability": {
                            "evaluation_dir": str(eval_dir),
                            "events_file": str(eval_dir / "events.jsonl"),
                            "record_file": str(eval_dir / mode_file),
                            "csv_dataset": str(self.csv_path),
                        },
                    }
                    with open(summary_file, mode="w", encoding="utf-8") as f:
                        json.dump(summary_data, f, indent=2)

    def log_paired_summary(self, comparison: ComparisonResult) -> dict[str, Any]:
        """
        Record a comprehensive human-readable summary artifact for a paired evaluation.
        Stored at data/m8/experiments/<evaluation_id>/summary.json.
        """
        with _log_lock:
            clean_eval_id = comparison.evaluation_id
            eval_dir = self.experiments_dir / clean_eval_id
            eval_dir.mkdir(parents=True, exist_ok=True)

            summary_payload = {
                "evaluation_id": comparison.evaluation_id,
                "bug_id": comparison.bug_id,
                "language": comparison.language,
                "model": comparison.model,
                "status": comparison.status,
                "timestamp": comparison.baseline.timestamp or comparison.dynamic.timestamp,
                "metrics": {
                    "context_reduction_percent": comparison.context_reduction_percent,
                    "token_reduction_percent": comparison.token_reduction_percent,
                    "time_difference_ms": comparison.time_difference_ms,
                },
                "baseline": comparison.baseline.model_dump(),
                "dynamic": comparison.dynamic.model_dump(),
                "traceability": {
                    "evaluation_dir": str(eval_dir),
                    "events_file": str(eval_dir / "events.jsonl"),
                    "summary_file": str(eval_dir / "summary.json"),
                    "baseline_file": str(eval_dir / "baseline.json"),
                    "dynamic_file": str(eval_dir / "dynamic.json"),
                    "csv_dataset": str(self.csv_path),
                },
            }

            with open(eval_dir / "summary.json", mode="w", encoding="utf-8") as f:
                json.dump(summary_payload, f, indent=2)

            return summary_payload

    def get_experiments(self, limit: int = 50) -> list[ExperimentRecord]:
        """
        Read recent experiment records from CSV.
        """
        if not self.csv_path.exists():
            return []

        records: list[ExperimentRecord] = []
        with _log_lock:
            try:
                with open(self.csv_path, mode="r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        def parse_opt_int(val: Any) -> Optional[int]:
                            if val is not None and str(val).strip() != "":
                                try:
                                    return int(val)
                                except ValueError:
                                    return None
                            return None

                        def parse_opt_float(val: Any, default: float = 0.0) -> float:
                            if val is not None and str(val).strip() != "":
                                try:
                                    return float(val)
                                except ValueError:
                                    return default
                            return default

                        ctx_chars = int(row.get("context_chars") or row.get("context_size") or 0)
                        usage_avail = str(row.get("token_usage_available", "")).lower() == "true"
                        mcp_tot_time = parse_opt_float(row.get("mcp_total_time_ms") or row.get("mcp_time_ms"))
                        exp_tot_time = parse_opt_float(row.get("total_experiment_time_ms") or row.get("total_time_ms"))

                        converted = {
                            "evaluation_id": row.get("evaluation_id", ""),
                            "experiment_id": row.get("experiment_id", ""),
                            "bug_id": row.get("bug_id", ""),
                            "mode": row.get("mode", ""),
                            "language": row.get("language", ""),
                            "model": row.get("model", ""),
                            "context_chars": ctx_chars,
                            "context_size": ctx_chars,
                            "input_tokens": parse_opt_int(row.get("input_tokens")),
                            "output_tokens": parse_opt_int(row.get("output_tokens")),
                            "total_tokens": parse_opt_int(row.get("total_tokens")),
                            "token_usage_available": usage_avail,
                            "curator_input_tokens": parse_opt_int(row.get("curator_input_tokens")),
                            "curator_output_tokens": parse_opt_int(row.get("curator_output_tokens")),
                            "curator_total_tokens": parse_opt_int(row.get("curator_total_tokens")),
                            "debugger_input_tokens": parse_opt_int(row.get("debugger_input_tokens")),
                            "debugger_output_tokens": parse_opt_int(row.get("debugger_output_tokens")),
                            "debugger_total_tokens": parse_opt_int(row.get("debugger_total_tokens")),
                            "llm_calls": int(row.get("llm_calls") or 0),
                            "mcp_calls": int(row.get("mcp_calls") or 0),
                            "context_reduction_percent": None,
                            "llm_time_ms": parse_opt_float(row.get("llm_time_ms")),
                            "mcp_query_time_ms": parse_opt_float(row.get("mcp_query_time_ms")),
                            "mcp_transport_time_ms": parse_opt_float(row.get("mcp_transport_time_ms")),
                            "mcp_total_time_ms": mcp_tot_time,
                            "mcp_time_ms": mcp_tot_time,
                            "total_curation_time_ms": parse_opt_float(row.get("total_curation_time_ms")),
                            "total_debugging_time_ms": parse_opt_float(row.get("total_debugging_time_ms")),
                            "total_experiment_time_ms": exp_tot_time,
                            "total_time_ms": exp_tot_time,
                            "root_cause_identified": str(row.get("root_cause_identified", "")).lower() == "true",
                            "fix_generated": str(row.get("fix_generated", "")).lower() == "true",
                            "fix_correct": (
                                True if str(row.get("fix_correct", "")).strip().lower() in ("true", "1")
                                else False if str(row.get("fix_correct", "")).strip().lower() in ("false", "0")
                                else None
                            ),
                            "re_execution_passed": str(row.get("re_execution_passed", "")).lower() == "true",
                            "stop_reason": row.get("stop_reason", ""),
                            "status": row.get("status", "completed"),
                            "timestamp": row.get("timestamp", ""),
                        }
                        records.append(ExperimentRecord(**converted))
            except Exception:
                return []

        return list(reversed(records))[:limit]

    def _resolve_evaluation_dir(self, identifier: str) -> tuple[str, Optional[Path]]:
        """
        Resolve either an evaluation_id or experiment_id to (evaluation_id, eval_dir).
        """
        if not identifier:
            return "", None

        clean_id = identifier.strip()

        # 1. Direct directory match in data/m8/experiments/<clean_id>/
        direct_dir = self.experiments_dir / clean_id
        if direct_dir.exists() and direct_dir.is_dir():
            return clean_id, direct_dir

        # Check if swapping prefix exp_ <-> eval_ finds a directory
        if clean_id.startswith("exp_"):
            alt_id = "eval_" + clean_id[4:]
            alt_dir = self.experiments_dir / alt_id
            if alt_dir.exists() and alt_dir.is_dir():
                return alt_id, alt_dir
        elif clean_id.startswith("eval_"):
            alt_id = "exp_" + clean_id[5:]
            alt_dir = self.experiments_dir / alt_id
            if alt_dir.exists() and alt_dir.is_dir():
                return alt_id, alt_dir

        # 2. Check CSV records for matching evaluation_id or experiment_id
        for r in self.get_experiments(limit=500):
            if r.experiment_id == clean_id or r.evaluation_id == clean_id:
                target_eval_id = r.evaluation_id or clean_id
                target_dir = self.experiments_dir / target_eval_id
                return target_eval_id, target_dir

        # 3. Check if clean_id has _baseline, _dynamic, or _paired suffix
        for suffix in ("_baseline", "_dynamic", "_paired"):
            if clean_id.endswith(suffix):
                candidate_id = clean_id[:-len(suffix)]
                candidates = [candidate_id]
                if candidate_id.startswith("exp_"):
                    candidates.append("eval_" + candidate_id[4:])
                elif candidate_id.startswith("eval_"):
                    candidates.append("exp_" + candidate_id[5:])
                for cid in candidates:
                    candidate_dir = self.experiments_dir / cid
                    if candidate_dir.exists() and candidate_dir.is_dir():
                        return cid, candidate_dir

        return clean_id, self.experiments_dir / clean_id

    def get_evaluation_summary(self, evaluation_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve summary artifact for a given evaluation_id or experiment_id.
        Standardizes output so that 'baseline' and 'dynamic' records are populated
        from summary.json, individual mode files, or logged CSV records.
        """
        target_eval_id, eval_dir = self._resolve_evaluation_dir(evaluation_id)
        if not target_eval_id:
            return None

        summary_data: Optional[dict[str, Any]] = None
        eval_summary_path = eval_dir / "summary.json" if eval_dir else None

        if eval_summary_path and eval_summary_path.exists():
            try:
                with open(eval_summary_path, mode="r", encoding="utf-8") as f:
                    summary_data = json.load(f)
            except Exception:
                summary_data = None

        # Check for mode-specific JSON artifacts in the evaluation directory
        baseline_file = eval_dir / "baseline.json" if eval_dir else None
        dynamic_file = eval_dir / "dynamic.json" if eval_dir else None

        file_baseline: Optional[dict[str, Any]] = None
        file_dynamic: Optional[dict[str, Any]] = None

        if baseline_file and baseline_file.exists():
            try:
                with open(baseline_file, mode="r", encoding="utf-8") as bf:
                    file_baseline = json.load(bf)
            except Exception:
                pass

        if dynamic_file and dynamic_file.exists():
            try:
                with open(dynamic_file, mode="r", encoding="utf-8") as df:
                    file_dynamic = json.load(df)
            except Exception:
                pass

        # Check CSV records
        matching = [
            r for r in self.get_experiments(limit=500)
            if r.evaluation_id == target_eval_id or r.experiment_id == evaluation_id or r.evaluation_id == evaluation_id
        ]
        csv_baseline = next((r.model_dump() for r in matching if r.mode == "baseline"), None)
        csv_dynamic = next((r.model_dump() for r in matching if r.mode == "dynamic"), None)

        baseline_record = (
            (summary_data.get("baseline") if isinstance(summary_data, dict) and summary_data.get("baseline") else None)
            or file_baseline
            or csv_baseline
        )
        dynamic_record = (
            (summary_data.get("dynamic") if isinstance(summary_data, dict) and summary_data.get("dynamic") else None)
            or file_dynamic
            or csv_dynamic
        )

        # If summary_data was a single-run summary, assign to corresponding mode if missing
        if isinstance(summary_data, dict) and not summary_data.get("baseline") and not summary_data.get("dynamic"):
            mode = summary_data.get("mode")
            if mode == "baseline" and not baseline_record:
                baseline_record = summary_data
            elif mode == "dynamic" and not dynamic_record:
                dynamic_record = summary_data

        # If neither summary.json nor mode records exist, cannot produce summary
        if not summary_data and not baseline_record and not dynamic_record:
            return None

        primary = dynamic_record or baseline_record or (summary_data if isinstance(summary_data, dict) else {})
        bug_id = primary.get("bug_id", "")
        language = primary.get("language", "")
        model = primary.get("model", "")
        status = primary.get("status", "completed")
        timestamp = primary.get("timestamp", "")

        # Compute reduction metrics if both exist
        ctx_reduct = None
        tok_reduct = None
        time_diff = None

        if baseline_record and dynamic_record:
            b_chars = baseline_record.get("context_chars") or baseline_record.get("context_size") or 0
            d_chars = dynamic_record.get("context_chars") or dynamic_record.get("context_size") or 0
            if b_chars > 0 and dynamic_record.get("status") == "completed":
                ctx_reduct = round(((b_chars - d_chars) / b_chars) * 100.0, 2)

            b_tok = baseline_record.get("total_tokens")
            d_tok = dynamic_record.get("total_tokens")
            b_avail = baseline_record.get("token_usage_available", False)
            d_avail = dynamic_record.get("token_usage_available", False)
            if b_avail and d_avail and b_tok is not None and b_tok > 0 and d_tok is not None:
                tok_reduct = round(((b_tok - d_tok) / b_tok) * 100.0, 2)

            b_time = baseline_record.get("total_experiment_time_ms") or baseline_record.get("total_time_ms") or 0.0
            d_time = dynamic_record.get("total_experiment_time_ms") or dynamic_record.get("total_time_ms") or 0.0
            time_diff = round(d_time - b_time, 2)
        elif isinstance(summary_data, dict) and "metrics" in summary_data:
            metrics_dict = summary_data.get("metrics") or {}
            ctx_reduct = metrics_dict.get("context_reduction_percent")
            tok_reduct = metrics_dict.get("token_reduction_percent")
            time_diff = metrics_dict.get("time_difference_ms")

        return {
            "evaluation_id": target_eval_id,
            "bug_id": bug_id,
            "language": language,
            "model": model,
            "status": status,
            "timestamp": timestamp,
            "metrics": {
                "context_reduction_percent": ctx_reduct,
                "token_reduction_percent": tok_reduct,
                "time_difference_ms": time_diff,
            },
            "baseline": baseline_record,
            "dynamic": dynamic_record,
            "traceability": {
                "evaluation_dir": str(eval_dir) if eval_dir else "",
                "events_file": str(eval_dir / "events.jsonl") if eval_dir else "",
                "summary_file": str(eval_summary_path) if eval_summary_path else "",
                "csv_dataset": str(self.csv_path),
            },
        }

    def get_evaluation_events(self, evaluation_id: str) -> list[dict[str, Any]]:
        """
        Retrieve structured lifecycle events for a given evaluation_id or experiment_id.
        """
        target_eval_id, eval_dir = self._resolve_evaluation_dir(evaluation_id)
        clean_target = target_eval_id or evaluation_id

        if eval_dir and (eval_dir / "events.jsonl").exists():
            events = []
            try:
                with open(eval_dir / "events.jsonl", mode="r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            events.append(json.loads(line))
                if events:
                    return events
            except Exception:
                pass

        # Fallback: check global jsonl
        if self.jsonl_path.exists():
            matched = []
            try:
                with open(self.jsonl_path, mode="r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            obj = json.loads(line)
                            if (
                                obj.get("evaluation_id") == clean_target
                                or obj.get("evaluation_id") == evaluation_id
                                or obj.get("experiment_id") == evaluation_id
                            ):
                                matched.append(obj)
                return matched
            except Exception:
                pass

        return []

    def get_latest_baseline(self, bug_id: str) -> Optional[ExperimentRecord]:
        """
        Find the most recent valid baseline run for a specific bug_id.
        """
        for record in self.get_experiments(limit=100):
            if (
                record.bug_id.upper() == bug_id.upper()
                and record.mode == "baseline"
                and record.status == "completed"
                and record.context_chars > 0
            ):
                return record
        return None

    def export_csv_path(self) -> Path:
        """Return the filesystem path to the master CSV dataset."""
        return self.csv_path

    def clear_results(self) -> dict[str, Any]:
        """
        Safely clear all generated M8 evaluation results, reset CSV dataset to header,
        truncate the events journal, and remove per-experiment artifact directories.

        Preserves benchmark definitions, configuration, code, and non-M8 logs.
        Strictly enforces path containment within self.data_dir to prevent path traversal.
        """
        errors: list[str] = []
        cleared_dirs_count = 0
        csv_cleared = False
        events_cleared = False

        with _log_lock:
            base_dir = self.data_dir.resolve()

            # 1. Reset master CSV dataset to header
            try:
                # Verify path containment
                if self.csv_path.resolve() == base_dir / CSV_FILENAME or self.csv_path.resolve().is_relative_to(base_dir):
                    self.data_dir.mkdir(parents=True, exist_ok=True)
                    with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                        writer.writeheader()
                    csv_cleared = True
                else:
                    errors.append("CSV path resolves outside allowed data directory.")
            except Exception as e:
                errors.append(f"Failed to reset CSV dataset: {type(e).__name__}")

            # Reset legacy CSV if it exists and we are in default data dir
            if self.data_dir == DEFAULT_M8_DATA_DIR:
                legacy_csv = DEFAULT_DATA_DIR / CSV_FILENAME
                try:
                    if legacy_csv.exists() and legacy_csv.resolve().is_relative_to(DEFAULT_DATA_DIR.resolve()):
                        with open(legacy_csv, mode="w", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                            writer.writeheader()
                except Exception:
                    pass

            # 2. Reset events journal
            try:
                if self.jsonl_path.resolve() == base_dir / JSONL_FILENAME or self.jsonl_path.resolve().is_relative_to(base_dir):
                    self.data_dir.mkdir(parents=True, exist_ok=True)
                    self.jsonl_path.write_text("", encoding="utf-8")
                    events_cleared = True
                else:
                    errors.append("Events log path resolves outside allowed data directory.")
            except Exception as e:
                errors.append(f"Failed to reset event log: {type(e).__name__}")

            # Reset legacy events log if in default dir
            if self.data_dir == DEFAULT_M8_DATA_DIR:
                legacy_jsonl = DEFAULT_DATA_DIR / JSONL_FILENAME
                try:
                    if legacy_jsonl.exists() and legacy_jsonl.resolve().is_relative_to(DEFAULT_DATA_DIR.resolve()):
                        legacy_jsonl.write_text("", encoding="utf-8")
                except Exception:
                    pass

            # 3. Clear per-experiment artifact directories
            try:
                if self.experiments_dir.exists():
                    exp_dir_resolved = self.experiments_dir.resolve()
                    if not exp_dir_resolved.is_relative_to(base_dir):
                        errors.append("Experiments directory resolves outside allowed data directory.")
                    else:
                        for child in self.experiments_dir.iterdir():
                            try:
                                if not child.resolve().is_relative_to(exp_dir_resolved):
                                    errors.append(f"Skipping child outside allowed directory: {child.name}")
                                    continue
                                if child.is_dir():
                                    shutil.rmtree(child)
                                    cleared_dirs_count += 1
                                elif child.is_file():
                                    child.unlink()
                            except Exception as child_err:
                                errors.append(f"Failed to delete artifact item: {type(child_err).__name__}")
                # Ensure directory remains available for future runs
                self.experiments_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Failed while clearing experiments directory: {type(e).__name__}")

            success = len(errors) == 0 and csv_cleared and events_cleared
            timestamp = datetime.now(timezone.utc).isoformat()

            app_logger.info(
                "M8 experiment clearing executed. success=%s, dirs_cleared=%d, errors=%s",
                success,
                cleared_dirs_count,
                errors,
            )

            return {
                "success": success,
                "cleared_categories": {
                    "csv_records": csv_cleared,
                    "event_logs": events_cleared,
                    "experiment_directories": cleared_dirs_count,
                },
                "errors": errors if errors else None,
                "message": (
                    "All M8 experiment results and generated artifacts successfully cleared."
                    if success
                    else "Encountered an issue clearing some M8 artifacts."
                ),
                "timestamp": timestamp,
            }


# Default shared logger instance
logger = ExperimentLogger()
