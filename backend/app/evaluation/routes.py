"""
FastAPI router for Milestone 8 evaluation endpoints.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.evaluation.benchmarks import get_all_benchmarks, get_benchmark
from app.evaluation.logger import logger
from app.evaluation.models import (
    BenchmarkCase,
    BenchmarkRunRequest,
    ClearResultsResponse,
    ComparisonResult,
    ExperimentRecord,
    PairedBenchmarkRunRequest,
)
from app.evaluation.service import EvaluationService
from app.logging_config import get_app_logger

app_logger = get_app_logger("evaluation.routes")

router = APIRouter(
    prefix="/evaluation",
    tags=["evaluation"],
)

eval_service = EvaluationService()


@router.get(
    "/benchmarks",
    response_model=list[BenchmarkCase],
)
async def list_benchmarks(language: Optional[str] = Query(default=None)) -> list[BenchmarkCase]:
    """Retrieve all fixed debugging benchmark tasks (B001 - B010) for the specified language."""
    return get_all_benchmarks(language=language or "python")


@router.get(
    "/benchmarks/{bug_id}",
    response_model=BenchmarkCase,
)
async def get_benchmark_by_id(bug_id: str, language: Optional[str] = Query(default=None)) -> BenchmarkCase:
    """Retrieve a single benchmark by its bug_id (e.g., B001) for the specified language."""
    bench = get_benchmark(bug_id, language=language or "python")
    if not bench:
        raise HTTPException(
            status_code=404,
            detail=f"Benchmark '{bug_id}' not found for language '{language or 'python'}'.",
        )
    return bench


@router.post(
    "/run",
    response_model=ExperimentRecord,
)
async def run_single_experiment(request: BenchmarkRunRequest) -> ExperimentRecord:
    """Run an individual experiment in 'baseline' or 'dynamic' mode."""
    code = request.code
    language = request.language or "python"
    stdin = request.stdin or ""
    bug_id = request.bug_id or "CUSTOM"

    if request.bug_id and not code:
        bench = get_benchmark(request.bug_id, language=language)
        if not bench:
            raise HTTPException(
                status_code=404,
                detail=f"Benchmark '{request.bug_id}' not found for language '{language}'.",
            )
        code = bench.code
        language = bench.language
        stdin = bench.stdin
        bug_id = bench.bug_id

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Either code or a valid bug_id must be provided.",
        )

    try:
        record = await eval_service.run_experiment(
            code=code,
            language=language,
            stdin=stdin,
            mode=request.mode,
            bug_id=bug_id,
            evaluation_id=request.evaluation_id,
        )
        return record
    except Exception as exc:
        app_logger.error("Experiment execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="AI service is currently unavailable. Please try again later.",
        )


@router.post(
    "/run-paired",
    response_model=ComparisonResult,
)
async def run_paired_evaluation(request: PairedBenchmarkRunRequest) -> ComparisonResult:
    """Run both Baseline (Full Context) and Dynamic (Curated Context) for controlled paired comparison."""
    try:
        result = await eval_service.run_paired_experiment(
            bug_id=request.bug_id,
            code=request.code,
            language=request.language or "python",
            stdin=request.stdin or "",
            evaluation_id=request.evaluation_id,
        )
        return result
    except ValueError as exc:
        app_logger.warning("Invalid paired evaluation request: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Invalid evaluation benchmark task.",
        )
    except Exception as exc:
        app_logger.error("Paired evaluation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="AI service is currently unavailable. Please try again later.",
        )


@router.get(
    "/experiments",
    response_model=list[ExperimentRecord],
)
async def get_recent_experiments(limit: int = Query(default=100, ge=1, le=500)) -> list[ExperimentRecord]:
    """Retrieve logged experiment records from m8_experiments.csv."""
    return logger.get_experiments(limit=limit)


@router.post(
    "/import",
    response_model=dict,
)
async def import_experiments_dataset(
    file_path: Optional[str] = Query(default=None, description="Optional path to CSV file to import"),
) -> dict:
    """Import experiment records from a CSV file into the master dataset with deduplication."""
    try:
        from pathlib import Path
        backend_root = Path(__file__).resolve().parent.parent.parent
        workspace_root = backend_root.parent

        if file_path:
            target_path = Path(file_path)
            if not target_path.is_absolute():
                target_path = (workspace_root / target_path).resolve()
            if not target_path.exists():
                raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
            return logger.import_csv_file(target_path)

        # Default import of both CSV files if no path specified
        results = []
        default_files = [
            workspace_root / "Python_Complete_results_PW1(1).csv",
            workspace_root / "java csv pw1 - m8_experiments(1).csv",
            backend_root / "data" / "Python_Complete_results_PW1(1).csv",
            backend_root / "data" / "java csv pw1 - m8_experiments(1).csv",
        ]
        imported_files = set()
        for f in default_files:
            if f.exists() and f.name not in imported_files:
                res = logger.import_csv_file(f)
                results.append(res)
                imported_files.add(f.name)

        if not results:
            raise HTTPException(status_code=404, detail="No default experiment CSV files found to import.")

        return {
            "status": "success",
            "imported_files": results,
            "total_records": len(logger.get_experiments(limit=500)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        app_logger.error("Failed to import experiments CSV: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to import experiments: {str(exc)}")


@router.get(
    "/experiments/{evaluation_id}/summary",
)
async def get_experiment_summary(evaluation_id: str) -> dict:
    """Retrieve human-readable summary artifact for a specific evaluation_id."""
    summary = logger.get_evaluation_summary(evaluation_id)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation summary found for '{evaluation_id}'",
        )
    return summary


@router.get(
    "/experiments/{evaluation_id}/events",
)
async def get_experiment_events(evaluation_id: str) -> list[dict]:
    """Retrieve structured lifecycle events for a specific evaluation_id."""
    return logger.get_evaluation_events(evaluation_id)


@router.get(
    "/export/csv",
)
async def export_csv_dataset():
    """Download the master m8_experiments.csv dataset."""
    csv_file = logger.export_csv_path()
    if not csv_file.exists():
        raise HTTPException(status_code=404, detail="No experiment dataset available to export.")
    return FileResponse(
        path=str(csv_file),
        media_type="text/csv",
        filename="m8_experiments.csv",
    )


@router.delete(
    "/results",
    response_model=ClearResultsResponse,
)
async def clear_m8_results() -> ClearResultsResponse:
    """
    Safely clear all generated M8 experiment results, telemetry logs, and evaluation artifacts.
    Resets the master CSV dataset to its initial header/schema.
    Refuses operation if an experiment is actively running.
    """
    if eval_service.is_running:
        app_logger.warning("Clear operation rejected: an evaluation experiment is currently running.")
        raise HTTPException(
            status_code=409,
            detail="Cannot clear results while an experiment is currently running. Please wait for it to complete.",
        )

    eval_service.set_clearing(True)
    try:
        result = eval_service.logger.clear_results()
        if not result.get("success"):
            app_logger.warning("M8 clear results completed with errors: %s", result.get("errors"))
        return ClearResultsResponse(**result)
    except HTTPException:
        raise
    except Exception as exc:
        app_logger.error("Failed to clear M8 results: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to clear experiment results due to an internal error.",
        )
    finally:
        eval_service.set_clearing(False)


@router.delete(
    "/experiments",
    response_model=ClearResultsResponse,
    include_in_schema=False,
)
async def clear_m8_experiments_alias() -> ClearResultsResponse:
    """Alias for DELETE /evaluation/results."""
    return await clear_m8_results()

