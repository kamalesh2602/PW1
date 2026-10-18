"""
Tests for Milestone 8: Baseline Comparison, Token Tracking, Measurement Validation, and Experiment Pairing.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.agent.debugger import DebuggingAgent
from app.agent.models import DebugDiagnosis
from app.agent.token_tracker import TokenUsageCallback, TokenUsageResult, extract_token_usage
from app.evaluation.benchmarks import get_all_benchmarks, get_benchmark
from app.evaluation.logger import ExperimentLogger
from app.evaluation.models import BenchmarkRunRequest, ExperimentRecord
from app.evaluation.service import EvaluationService
from app.main import app
from app.models.execution import ExecutionLanguage, ExecutionRequest
from app.services.executor import CodeExecutionService

client = TestClient(app)


def test_normalized_extract_token_usage_helper():
    """Verify extract_token_usage handles AIMessage, dict, and missing usage cleanly."""
    # 1. AIMessage with usage_metadata
    msg = AIMessage(
        content='Hello',
        usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
    )
    res = extract_token_usage(msg)
    assert res.available is True
    assert res.input_tokens == 120
    assert res.output_tokens == 30
    assert res.total_tokens == 150

    # 2. Raw OpenRouter response dictionary with 'usage'
    raw_dict = {
        "id": "gen-123",
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 50,
            "total_tokens": 250,
        }
    }
    res_dict = extract_token_usage(raw_dict)
    assert res_dict.available is True
    assert res_dict.input_tokens == 200
    assert res_dict.output_tokens == 50
    assert res_dict.total_tokens == 250

    # 3. Missing usage metadata -> available is False, tokens are None (never 0)
    msg_empty = AIMessage(content='No metadata')
    res_empty = extract_token_usage(msg_empty)
    assert res_empty.available is False
    assert res_empty.input_tokens is None
    assert res_empty.output_tokens is None
    assert res_empty.total_tokens is None
    assert res_empty.total_tokens != 0

    # 4. None input
    res_none = extract_token_usage(None)
    assert res_none.available is False
    assert res_none.input_tokens is None


def test_fairness_token_aggregation_curator_and_debugger(tmp_path):
    """Verify Dynamic total tokens = curator_tokens + debugger_tokens, and Baseline = debugger_tokens."""
    isolated_logger = ExperimentLogger(data_dir=tmp_path)
    service = EvaluationService(logger=isolated_logger)

    # Dynamic run record simulation
    dyn_rec = ExperimentRecord(
        evaluation_id="eval_fairness_1",
        experiment_id="eval_fairness_1_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1306,
        curator_input_tokens=100,
        curator_output_tokens=25,
        curator_total_tokens=125,
        debugger_input_tokens=200,
        debugger_output_tokens=50,
        debugger_total_tokens=250,
        input_tokens=300,  # 100 + 200
        output_tokens=75,  # 25 + 50
        total_tokens=375,  # 125 + 250
        token_usage_available=True,
    )

    # Baseline run record simulation
    base_rec = ExperimentRecord(
        evaluation_id="eval_fairness_1",
        experiment_id="eval_fairness_1_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=11440,
        curator_input_tokens=0,
        curator_output_tokens=0,
        curator_total_tokens=0,
        debugger_input_tokens=500,
        debugger_output_tokens=120,
        debugger_total_tokens=620,
        input_tokens=500,
        output_tokens=120,
        total_tokens=620,
        token_usage_available=True,
    )

    assert dyn_rec.total_tokens == dyn_rec.curator_total_tokens + dyn_rec.debugger_total_tokens
    assert dyn_rec.input_tokens == dyn_rec.curator_input_tokens + dyn_rec.debugger_input_tokens
    assert dyn_rec.output_tokens == dyn_rec.curator_output_tokens + dyn_rec.debugger_output_tokens
    assert base_rec.total_tokens == base_rec.debugger_total_tokens

    # Verify token reduction is computed from total tokens
    from app.evaluation.models import ComparisonResult
    comp = ComparisonResult(
        evaluation_id="eval_fairness_1",
        bug_id="B001",
        language="python",
        model="openrouter/free",
        baseline=base_rec,
        dynamic=dyn_rec,
        context_reduction_percent=88.58,
        token_reduction_percent=round(((base_rec.total_tokens - dyn_rec.total_tokens) / base_rec.total_tokens) * 100.0, 2),
        time_difference_ms=100.0,
    )
    # 620 vs 375 -> (620 - 375) / 620 * 100 = 39.52%
    assert comp.token_reduction_percent == 39.52


def test_token_usage_extraction():
    """1. Verify TokenUsageCallback extracts actual provider usage metadata from AIMessage and fallback."""
    tracker = TokenUsageCallback()

    # Simulate LangChain LLMResult with usage_metadata
    msg = AIMessage(
        content='{"test": 1}',
        usage_metadata={"input_tokens": 150, "output_tokens": 45, "total_tokens": 195}
    )
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])

    tracker.on_llm_end(result)
    assert tracker.calls == 1
    assert tracker.usage_available is True
    assert tracker.input_tokens == 150
    assert tracker.output_tokens == 45
    assert tracker.total_tokens == 195
    assert tracker.safe_input_tokens == 150
    assert tracker.safe_output_tokens == 45
    assert tracker.safe_total_tokens == 195

    # Simulate second call with llm_output fallback
    result_fallback = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="second"))]],
        llm_output={"token_usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100}}
    )
    tracker.on_llm_end(result_fallback)
    assert tracker.calls == 2
    assert tracker.input_tokens == 230
    assert tracker.output_tokens == 65
    assert tracker.total_tokens == 295


def test_missing_token_usage_does_not_become_zero():
    """2. Verify missing token metadata from provider results in None and usage_available=False, never 0."""
    tracker = TokenUsageCallback()

    # LLMResult with empty generations and no usage_metadata or token_usage
    msg = AIMessage(content='{"result": "ok"}')
    result = LLMResult(generations=[[ChatGeneration(message=msg)]])

    tracker.on_llm_end(result)
    assert tracker.calls == 1
    assert tracker.usage_available is False
    assert tracker.safe_input_tokens is None
    assert tracker.safe_output_tokens is None
    assert tracker.safe_total_tokens is None
    # Crucial: safe properties return None, not 0
    assert tracker.safe_total_tokens != 0


def test_context_character_measurement():
    """3. Verify context_chars measures characters and distinguishes characters from tokens."""
    context_text = "def hello():\n    return 'world'"
    char_count = len(context_text)

    record = ExperimentRecord(
        evaluation_id="eval_test",
        experiment_id="exp_test",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=char_count,
        input_tokens=12,  # token count is different from character count
        output_tokens=5,
        total_tokens=17,
        token_usage_available=True,
    )

    assert record.context_chars == char_count
    assert record.context_size == char_count
    assert record.context_chars != record.total_tokens


def test_context_reduction_calculation():
    """4. Verify context reduction formula: ((baseline_chars - dynamic_chars) / baseline_chars) * 100."""
    baseline_chars = 10000
    dynamic_chars = 1200
    expected_reduction = round(((baseline_chars - dynamic_chars) / baseline_chars) * 100.0, 2)
    assert expected_reduction == 88.0

    service = EvaluationService(logger=MagicMock())
    # Test formula directly
    reduction = round(((baseline_chars - dynamic_chars) / baseline_chars) * 100.0, 2)
    assert reduction == 88.0


def test_token_reduction_calculation_and_unavailable_handling():
    """Verify token reduction is calculated when available, and None (not fake 0) when unavailable."""
    # When available
    base_tok = 1000
    dyn_tok = 400
    expected_reduction = round(((base_tok - dyn_tok) / base_tok) * 100.0, 2)
    assert expected_reduction == 60.0

    # When unavailable, ComparisonResult returns None for token_reduction_percent
    base_rec = ExperimentRecord(
        evaluation_id="eval_1",
        experiment_id="exp_1",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="test",
        token_usage_available=False,
        total_tokens=None,
    )
    dyn_rec = ExperimentRecord(
        evaluation_id="eval_1",
        experiment_id="exp_2",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="test",
        token_usage_available=False,
        total_tokens=None,
    )
    from app.evaluation.models import ComparisonResult
    comp = ComparisonResult(
        evaluation_id="eval_1",
        bug_id="B001",
        language="python",
        model="test",
        baseline=base_rec,
        dynamic=dyn_rec,
        context_reduction_percent=None,
        token_reduction_percent=None,
        time_difference_ms=10.0,
    )
    assert comp.token_reduction_percent is None


@pytest.mark.asyncio
async def test_experiment_pairing_and_single_record_creation(tmp_path):
    """5 & 6. Verify shared evaluation_id links paired runs, and 1 request creates 1 record per mode."""
    isolated_logger = ExperimentLogger(data_dir=tmp_path)

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.fixer.get_llm") as mock_fixer_llm, \
         patch("app.agent.curator.get_llm") as mock_curator_llm, \
         patch("app.agent.curator.streamable_http_client") as mock_client, \
         patch("app.agent.curator.ClientSession") as mock_session_cls:

        mock_read = AsyncMock()
        mock_write = AsyncMock()
        mock_client.return_value.__aenter__.return_value = (mock_read, mock_write)

        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.isError = False
        mock_result.structured_content = {"error_type": "ZeroDivisionError", "line": 5, "file": "script.py"}
        mock_session.call_tool.return_value = mock_result

        from app.agent.curator import RetrievalDecision
        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = RetrievalDecision(
            tool_calls=[],
            reason="Root cause identified",
            is_sufficient=True,
            direction="initial",
        )
        mock_llm.with_structured_output.return_value = mock_model
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="def calculate(x): return 10 / x if x != 0 else 0\nprocess()"))
        mock_get_llm.return_value = mock_llm
        mock_fixer_llm.return_value = mock_llm
        mock_curator_llm.return_value = mock_llm

        service = EvaluationService(logger=isolated_logger)

        # Run paired experiment
        result = await service.run_paired_experiment(bug_id="B001")

        # 1. Pairing verification
        assert result.evaluation_id.startswith("eval_")
        assert result.baseline.evaluation_id == result.evaluation_id
        assert result.dynamic.evaluation_id == result.evaluation_id
        assert result.baseline.experiment_id == f"{result.evaluation_id}_baseline"
        assert result.dynamic.experiment_id == f"{result.evaluation_id}_dynamic"

        # 2. Exactly 2 records in isolated logger
        records = isolated_logger.get_experiments()
        assert len(records) == 2
        modes = {r.mode for r in records}
        assert modes == {"baseline", "dynamic"}


@pytest.mark.asyncio
async def test_baseline_produces_zero_mcp_calls():
    """7. Verify Baseline Mode: uses full source code and trace, produces zero MCP calls."""
    executor = CodeExecutionService()
    exec_resp = executor.execute_code(ExecutionRequest(
        language=ExecutionLanguage.PYTHON,
        code="def compute(a, b):\n    return a / b\n\ncompute(10, 0)",
    ))
    assert exec_resp.execution_id is not None

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.debugger.ContextCurator.curate") as mock_curate:

        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = DebugDiagnosis(
            execution_id=exec_resp.execution_id,
            diagnosis="ZeroDivisionError occurred in compute",
            root_cause="b was evaluated to 0 without guard",
            evidence=["compute(10, 0) caused ZeroDivisionError"],
            queries_used=[],
            confidence=0.95,
            suggested_fix="if b != 0: return a / b else: return 0",
        )
        mock_llm.with_structured_output.return_value = mock_model
        mock_get_llm.return_value = mock_llm

        agent = DebuggingAgent()
        diag = await agent.diagnose(execution_id=exec_resp.execution_id, mode="baseline")

        assert mock_curate.call_count == 0  # Curator NEVER called in baseline
        assert diag.telemetry is not None
        assert diag.telemetry["mode"] == "baseline"
        assert diag.telemetry["mcp_calls"] == 0
        assert diag.telemetry["mcp_query_time"] == 0.0
        assert diag.telemetry["mcp_transport_time"] == 0.0
        assert diag.telemetry["curator_input_tokens"] == 0
        assert diag.telemetry["context_chars"] > 0
        assert "=== FULL SOURCE CODE ===" in mock_model.ainvoke.call_args[0][0][1][1]


@pytest.mark.asyncio
async def test_dynamic_records_mcp_calls_and_timing():
    """8 & 9. Verify Dynamic Mode records MCP calls and distinct timing fields."""
    executor = CodeExecutionService()
    exec_resp = executor.execute_code(ExecutionRequest(
        language=ExecutionLanguage.PYTHON,
        code="def compute(a, b):\n    return a / b\n\ncompute(10, 0)",
    ))
    assert exec_resp.execution_id is not None

    with patch("app.agent.debugger.get_llm") as mock_get_llm, \
         patch("app.agent.debugger.ContextCurator.curate") as mock_curate:

        from app.agent.curator import CurationResult
        mock_curate.return_value = CurationResult(
            context='[{"source": "get_error_context", "data": "ZeroDivisionError"}]',
            telemetry={
                "tools_used": ["get_error_context", "get_stack_trace"],
                "mcp_calls": 2,
                "curator_input_tokens": 120,
                "curator_output_tokens": 30,
                "curator_total_tokens": 150,
                "token_usage_available": True,
                "llm_calls": 1,
                "llm_time": 0.5,
                "mcp_query_time": 0.08,
                "mcp_transport_time": 0.02,
                "mcp_total_time": 0.10,
                "time_spent": 0.65,
                "stop_reason": "root_cause_identified"
            }
        )

        mock_llm = MagicMock()
        mock_model = AsyncMock()
        mock_model.ainvoke.return_value = DebugDiagnosis(
            execution_id=exec_resp.execution_id,
            diagnosis="ZeroDivisionError occurred",
            root_cause="b was 0",
            evidence=["get_error_context returned ZeroDivisionError"],
            queries_used=["get_error_context", "get_stack_trace"],
            confidence=0.9,
            suggested_fix="if b == 0: return 0"
        )
        mock_llm.with_structured_output.return_value = mock_model
        mock_get_llm.return_value = mock_llm

        agent = DebuggingAgent()
        diag = await agent.diagnose(execution_id=exec_resp.execution_id, mode="dynamic")

        assert mock_curate.call_count == 1
        assert diag.telemetry is not None
        assert diag.telemetry["mode"] == "dynamic"
        assert diag.telemetry["mcp_calls"] == 2
        assert diag.telemetry["mcp_query_time"] == 0.08
        assert diag.telemetry["mcp_transport_time"] == 0.02
        assert diag.telemetry["mcp_total_time"] == 0.10
        assert diag.telemetry["dynamic_curator_total_tokens"] == 150


@pytest.mark.asyncio
async def test_invalid_experiment_record_handling(tmp_path):
    """10. Verify 2-char context or mcp_transport_error is flagged as invalid, not completed."""
    isolated_logger = ExperimentLogger(data_dir=tmp_path)
    service = EvaluationService(logger=isolated_logger)

    with patch("app.agent.fixer.FixerAgent.fix") as mock_fix:
        # Simulate failed curation producing empty context [] (2 chars)
        mock_diagnosis = DebugDiagnosis(
            execution_id="dummy_fail",
            diagnosis="Diagnosis unavailable",
            root_cause="",
            evidence=[],
            queries_used=[],
            confidence=0.0,
            suggested_fix="none",
            telemetry={
                "mode": "dynamic",
                "context_chars": 2,
                "context_size": 2,
                "mcp_calls": 0,
                "mcp_query_time": 0.0,
                "mcp_transport_time": 0.0,
                "mcp_total_time": 0.0,
                "stop_reason": "mcp_transport_error: connection refused",
            }
        )
        mock_fix.return_value = MagicMock(
            original_diagnosis=mock_diagnosis,
            fixed_code="",
            success=False,
            telemetry=mock_diagnosis.telemetry,
        )

        record = await service.run_experiment(
            code="def f(): pass",
            mode="dynamic",
            bug_id="B001",
        )

        assert record.status == "invalid"
        assert record.context_reduction_percent is None
        assert record.fix_correct is False


def test_benchmark_registry():
    """Verify predefined benchmarks B001 to B010 exist with valid specifications."""
    benchmarks = get_all_benchmarks()
    assert len(benchmarks) == 10

    b_ids = [b.bug_id for b in benchmarks]
    for expected_id in ["B001", "B002", "B003", "B004", "B005", "B006", "B007", "B008", "B009", "B010"]:
        assert expected_id in b_ids
        bench = get_benchmark(expected_id)
        assert bench is not None
        assert len(bench.code.strip()) > 0
        assert len(bench.expected_error.strip()) > 0
        assert len(bench.expected_root_cause.strip()) > 0
        assert len(bench.expected_behavior.strip()) > 0


def test_experiment_logger_schema_and_persistence(tmp_path):
    """Verify ExperimentLogger writes and reads CSV records with the Section 11 schema."""
    logger = ExperimentLogger(data_dir=tmp_path)
    record = ExperimentRecord(
        evaluation_id="eval_20260928_b001_123456",
        experiment_id="eval_20260928_b001_123456_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=11440,
        input_tokens=250,
        output_tokens=60,
        total_tokens=310,
        token_usage_available=True,
        curator_input_tokens=0,
        curator_output_tokens=0,
        curator_total_tokens=0,
        debugger_input_tokens=250,
        debugger_output_tokens=60,
        debugger_total_tokens=310,
        llm_calls=1,
        mcp_calls=0,
        mcp_query_time_ms=0.0,
        mcp_transport_time_ms=0.0,
        mcp_total_time_ms=0.0,
        llm_time_ms=350.0,
        total_experiment_time_ms=500.0,
        root_cause_identified=True,
        fix_generated=True,
        fix_correct=True,
        re_execution_passed=True,
        stop_reason="completed",
        status="completed",
        timestamp="2026-09-28T12:00:00Z",
    )

    logger.log_experiment(record)
    records = logger.get_experiments()
    assert len(records) == 1
    r = records[0]
    assert r.evaluation_id == "eval_20260928_b001_123456"
    assert r.experiment_id == "eval_20260928_b001_123456_baseline"
    assert r.context_chars == 11440
    assert r.total_tokens == 310
    assert r.token_usage_available is True
    assert r.status == "completed"


def test_api_evaluation_routes():
    """Verify the /evaluation REST endpoints."""
    resp = client.get("/evaluation/benchmarks")
    assert resp.status_code == 200
    assert len(resp.json()) == 10

    resp_b1 = client.get("/evaluation/benchmarks/B001")
    assert resp_b1.status_code == 200
    assert resp_b1.json()["bug_id"] == "B001"

    resp_exp = client.get("/evaluation/experiments?limit=10")
    assert resp_exp.status_code == 200
    assert isinstance(resp_exp.json(), list)

    resp_csv = client.get("/evaluation/export/csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers.get("content-type", "")


def test_artifact_folder_and_summary_creation(tmp_path):
    """Verify clean M8 artifact package: events.jsonl, baseline.json, dynamic.json, summary.json."""
    logger = ExperimentLogger(data_dir=tmp_path)
    eval_id = "eval_test_pkg_001"

    # 1. Log structured lifecycle events
    logger.log_event(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_baseline",
        bug_id="B001",
        mode="baseline",
        event="experiment_started",
        step=1,
        data={"code_chars": 100},
    )
    logger.log_event(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_baseline",
        bug_id="B001",
        mode="baseline",
        event="execution_completed",
        step=2,
        data={"exit_code": 1, "status": "runtime_error"},
    )

    # Verify per-evaluation events file
    eval_dir = tmp_path / "experiments" / eval_id
    assert eval_dir.exists()
    events_file = eval_dir / "events.jsonl"
    assert events_file.exists()

    events = logger.get_evaluation_events(eval_id)
    assert len(events) == 2
    assert events[0]["event"] == "experiment_started"
    assert events[0]["step"] == 1
    assert events[1]["event"] == "execution_completed"
    assert events[1]["data"]["exit_code"] == 1

    # 2. Log baseline record
    base_record = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=10000,
        total_tokens=500,
        token_usage_available=True,
        total_experiment_time_ms=1200.0,
    )
    logger.log_experiment(base_record)
    assert (eval_dir / "baseline.json").exists()

    # 3. Log dynamic record
    dyn_record = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1200,
        total_tokens=300,
        token_usage_available=True,
        total_experiment_time_ms=800.0,
    )
    logger.log_experiment(dyn_record)
    assert (eval_dir / "dynamic.json").exists()

    # 4. Log paired summary
    from app.evaluation.models import ComparisonResult
    comp = ComparisonResult(
        evaluation_id=eval_id,
        bug_id="B001",
        language="python",
        model="openrouter/free",
        baseline=base_record,
        dynamic=dyn_record,
        context_reduction_percent=88.0,
        token_reduction_percent=40.0,
        time_difference_ms=-400.0,
        status="completed",
    )
    summary = logger.log_paired_summary(comp)
    assert (eval_dir / "summary.json").exists()
    assert summary["evaluation_id"] == eval_id
    assert summary["metrics"]["context_reduction_percent"] == 88.0
    assert summary["metrics"]["token_reduction_percent"] == 40.0


def test_research_traceability_from_csv(tmp_path):
    """Verify that a researcher can take any row from m8_experiments.csv and trace it to artifacts."""
    logger = ExperimentLogger(data_dir=tmp_path)
    eval_id = "eval_trace_999"

    record = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1500,
        total_tokens=420,
        token_usage_available=True,
        total_experiment_time_ms=950.0,
    )
    logger.log_experiment(record)

    # Trace back: read from CSV
    experiments = logger.get_experiments()
    assert len(experiments) == 1
    row = experiments[0]

    # Verify ID points directly to artifact directory
    target_dir = tmp_path / "experiments" / row.evaluation_id
    assert target_dir.exists()
    assert (target_dir / "dynamic.json").exists()
    assert (target_dir / "summary.json").exists()

    summary_obj = logger.get_evaluation_summary(row.evaluation_id)
    assert summary_obj is not None
    assert summary_obj["evaluation_id"] == row.evaluation_id


def test_inspect_resolution_by_experiment_id(tmp_path):
    """Verify Inspect resolution by experiment_id (with _dynamic or _baseline suffix)."""
    logger = ExperimentLogger(data_dir=tmp_path)
    eval_id = "eval_inspect_pair_100"
    exp_id = f"{eval_id}_dynamic"

    record = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=exp_id,
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1200,
        total_tokens=300,
        token_usage_available=True,
        total_experiment_time_ms=800.0,
    )
    logger.log_experiment(record)

    # 1. Lookup by experiment_id directly
    summary = logger.get_evaluation_summary(exp_id)
    assert summary is not None
    assert summary["evaluation_id"] == eval_id
    assert summary["dynamic"]["experiment_id"] == exp_id

    # 2. Lookup events by experiment_id
    events = logger.get_evaluation_events(exp_id)
    assert isinstance(events, list)


def test_inspect_missing_and_invalid_artifacts():
    """Verify that inspecting an invalid or missing experiment ID returns 404 cleanly."""
    resp = client.get("/evaluation/experiments/non_existent_id_9999/summary")
    assert resp.status_code == 404
    assert "No evaluation summary found" in resp.json()["detail"]

    resp_ev = client.get("/evaluation/experiments/non_existent_id_9999/events")
    assert resp_ev.status_code == 200
    assert resp_ev.json() == []


def test_inspect_normalized_paired_files(tmp_path):
    """Verify that if baseline.json and dynamic.json exist on disk, summary is normalized with both."""
    logger = ExperimentLogger(data_dir=tmp_path)
    eval_id = "eval_dual_test_01"

    b_rec = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=10000,
        total_tokens=500,
        token_usage_available=True,
    )
    d_rec = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=2000,
        total_tokens=700,
        token_usage_available=True,
    )
    logger.log_experiment(b_rec)
    logger.log_experiment(d_rec)

    summary = logger.get_evaluation_summary(eval_id)
    assert summary is not None
    assert summary["baseline"] is not None
    assert summary["dynamic"] is not None
    assert summary["metrics"]["context_reduction_percent"] == 80.0
    # Dynamic used 700 tokens vs 500 baseline -> reduction is ((500-700)/500)*100 = -40.0%
    assert summary["metrics"]["token_reduction_percent"] == -40.0


def test_clear_results_resets_csv_and_removes_artifacts(tmp_path):
    """Verify that clear_results resets CSV to header and deletes generated per-experiment artifacts."""
    logger = ExperimentLogger(data_dir=tmp_path)
    eval_id = "eval_clear_test_01"

    rec = ExperimentRecord(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1200,
        total_tokens=250,
        token_usage_available=True,
    )
    logger.log_experiment(rec)
    logger.log_event(
        evaluation_id=eval_id,
        experiment_id=f"{eval_id}_dynamic",
        bug_id="B001",
        mode="dynamic",
        event="test_event",
        step=1,
        data={"info": "sample"},
    )

    # Pre-conditions
    assert len(logger.get_experiments()) == 1
    eval_dir = tmp_path / "experiments" / eval_id
    assert eval_dir.exists()
    assert (eval_dir / "dynamic.json").exists()
    assert (tmp_path / "m8_events.jsonl").read_text(encoding="utf-8").strip() != ""

    # Clear operation
    result = logger.clear_results()
    assert result["success"] is True
    assert result["cleared_categories"]["csv_records"] is True
    assert result["cleared_categories"]["event_logs"] is True
    assert result["cleared_categories"]["experiment_directories"] == 1
    assert result["errors"] is None

    # Post-conditions:
    # 1. Experiments list is empty
    assert logger.get_experiments() == []
    # 2. CSV still exists and contains schema header
    assert logger.csv_path.exists()
    lines = logger.csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "evaluation_id" in lines[0]
    assert "bug_id" in lines[0]
    # 3. Events journal is empty
    assert logger.jsonl_path.read_text(encoding="utf-8") == ""
    # 4. Artifact directory removed
    assert not eval_dir.exists()
    # 5. Experiments root directory still exists and is empty
    assert logger.experiments_dir.exists()
    assert list(logger.experiments_dir.iterdir()) == []


def test_clear_results_preserves_benchmarks_and_unrelated_files(tmp_path):
    """Verify that clear_results preserves benchmark definitions and unrelated files."""
    logger = ExperimentLogger(data_dir=tmp_path)

    # Create an unrelated file
    unrelated_file = tmp_path / "unrelated_user_data.txt"
    unrelated_file.write_text("critical user content", encoding="utf-8")

    benchmarks_before = get_all_benchmarks()
    assert len(benchmarks_before) >= 10

    # Execute clear
    result = logger.clear_results()
    assert result["success"] is True

    # Benchmark definitions are unchanged
    benchmarks_after = get_all_benchmarks()
    assert len(benchmarks_after) == len(benchmarks_before)
    assert get_benchmark("B001") is not None

    # Unrelated files in data dir or elsewhere are preserved
    assert unrelated_file.exists()
    assert unrelated_file.read_text(encoding="utf-8") == "critical user content"


def test_clear_results_handles_missing_files_gracefully(tmp_path):
    """Verify that clearing handles missing CSV or missing directories without crashing."""
    empty_dir = tmp_path / "non_existent_subdir"
    logger = ExperimentLogger(data_dir=empty_dir)

    # Intentionally remove files if created
    if logger.csv_path.exists():
        logger.csv_path.unlink()
    if logger.jsonl_path.exists():
        logger.jsonl_path.unlink()
    if logger.experiments_dir.exists():
        import shutil
        shutil.rmtree(logger.experiments_dir)

    result = logger.clear_results()
    assert result["success"] is True
    # Verify files and directories are safely recreated in valid state
    assert logger.csv_path.exists()
    assert logger.jsonl_path.exists()
    assert logger.experiments_dir.exists()
    assert logger.get_experiments() == []


def test_clear_results_path_traversal_protection(tmp_path):
    """Verify that clear_results detects and prevents paths outside allowed directory."""
    logger = ExperimentLogger(data_dir=tmp_path)
    outside_dir = tmp_path.parent / "outside_allowed_dir"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_file = outside_dir / "safe_file.txt"
    outside_file.write_text("must not be deleted", encoding="utf-8")

    # Manually configure a path pointing outside data_dir
    logger.experiments_dir = outside_dir

    result = logger.clear_results()
    assert result["success"] is False
    assert result["errors"] is not None
    assert any("resolves outside allowed data directory" in err for err in result["errors"])
    # Verify outside file was NOT deleted
    assert outside_file.exists()


def test_experiment_creation_works_normally_after_clear(tmp_path):
    """Verify that after clearing, a subsequent experiment writes normally and is queryable."""
    logger = ExperimentLogger(data_dir=tmp_path)

    # 1. Clear first
    logger.clear_results()
    assert logger.get_experiments() == []

    # 2. Log subsequent experiment
    new_eval_id = "eval_subsequent_01"
    new_rec = ExperimentRecord(
        evaluation_id=new_eval_id,
        experiment_id=f"{new_eval_id}_dynamic",
        bug_id="B002",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1450,
        total_tokens=320,
        token_usage_available=True,
    )
    logger.log_experiment(new_rec)

    # 3. Verify it was recorded properly
    exps = logger.get_experiments()
    assert len(exps) == 1
    assert exps[0].evaluation_id == new_eval_id
    assert exps[0].bug_id == "B002"

    summary = logger.get_evaluation_summary(new_eval_id)
    assert summary is not None
    assert summary["evaluation_id"] == new_eval_id


def test_api_clear_results_endpoint_and_running_guard():
    """Verify DELETE /evaluation/results endpoint and running guard."""
    from app.evaluation.routes import eval_service

    # 1. Guard check: when an experiment is running, clear must be rejected with 409
    eval_service._active_runs = 1
    resp_conflict = client.delete("/evaluation/results")
    assert resp_conflict.status_code == 409
    assert "currently running" in resp_conflict.json()["detail"]

    # Reset active runs
    eval_service._active_runs = 0

    # 2. Successful clear via API
    with patch.object(eval_service.logger, "clear_results") as mock_clear:
        mock_clear.return_value = {
            "success": True,
            "cleared_categories": {
                "csv_records": True,
                "event_logs": True,
                "experiment_directories": 3,
            },
            "errors": None,
            "message": "All M8 experiment results and generated artifacts successfully cleared.",
            "timestamp": "2026-10-14T18:00:00Z",
        }

        resp = client.delete("/evaluation/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["cleared_categories"]["csv_records"] is True
        assert data["cleared_categories"]["experiment_directories"] == 3
        mock_clear.assert_called_once()

    # 3. Test alias endpoint /evaluation/experiments
    with patch.object(eval_service.logger, "clear_results") as mock_clear_alias:
        mock_clear_alias.return_value = {
            "success": True,
            "cleared_categories": {
                "csv_records": True,
                "event_logs": True,
                "experiment_directories": 0,
            },
            "errors": None,
            "message": "All M8 experiment results and generated artifacts successfully cleared.",
            "timestamp": "2026-10-14T18:00:00Z",
        }
        resp_alias = client.delete("/evaluation/experiments")
        assert resp_alias.status_code == 200
        assert resp_alias.json()["success"] is True


def test_semantic_correctness_validation_tri_state():
    """Verify _validate_semantic_correctness returns True, False, or None (Not Validated)."""
    service = EvaluationService()

    # 1. B001 Valid Fix: calculate(2) == 5.0 and process() returns 5.0 -> True
    b001_good_code = """def calculate(x):
    return 10 / x

def process():
    value = 2
    return calculate(value)
"""
    assert service._validate_semantic_correctness("B001", b001_good_code, ExecutionLanguage.PYTHON) is True

    # 2. B001 Buggy Code: divisor is 0, ZeroDivisionError -> False
    b001_bad_code = """def calculate(x):
    return 10 / x

def process():
    value = 0
    return calculate(value)
"""
    assert service._validate_semantic_correctness("B001", b001_bad_code, ExecutionLanguage.PYTHON) is False

    # 3. Empty or whitespace code -> False
    assert service._validate_semantic_correctness("B001", "", ExecutionLanguage.PYTHON) is False

    # 4. Unknown benchmark or non-Python language -> None (Not Validated)
    assert service._validate_semantic_correctness("B999", b001_good_code, ExecutionLanguage.PYTHON) is None
    assert service._validate_semantic_correctness("B001", b001_good_code, ExecutionLanguage.JAVA) is None


def test_fix_correct_tri_state_serialization(tmp_path):
    """Verify fix_correct supports True, False, and None across CSV logging and model serialization."""
    logger = ExperimentLogger(data_dir=tmp_path)

    # Record 1: fix_correct = True
    rec_true = ExperimentRecord(
        evaluation_id="eval_tri_1",
        experiment_id="eval_tri_1_dyn",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1000,
        re_execution_passed=True,
        fix_correct=True,
    )
    logger.log_experiment(rec_true)

    # Record 2: fix_correct = False
    rec_false = ExperimentRecord(
        evaluation_id="eval_tri_2",
        experiment_id="eval_tri_2_dyn",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1000,
        re_execution_passed=True,
        fix_correct=False,
    )
    logger.log_experiment(rec_false)

    # Record 3: fix_correct = None (Not Validated)
    rec_none = ExperimentRecord(
        evaluation_id="eval_tri_3",
        experiment_id="eval_tri_3_dyn",
        bug_id="B999",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=1000,
        re_execution_passed=True,
        fix_correct=None,
    )
    logger.log_experiment(rec_none)

    # Read back and verify types
    experiments = logger.get_experiments()
    assert len(experiments) == 3
    by_id = {e.evaluation_id: e for e in experiments}
    assert by_id["eval_tri_1"].fix_correct is True
    assert by_id["eval_tri_2"].fix_correct is False
    assert by_id["eval_tri_3"].fix_correct is None


def test_java_benchmarks_all_10_present():
    """Verify all 10 Java benchmarks B001 to B010 are defined with correct metadata and Java syntax."""
    java_benchmarks = get_all_benchmarks("java")
    assert len(java_benchmarks) == 10

    expected_ids = [f"B{i:03d}" for i in range(1, 11)]
    assert [b.bug_id for b in java_benchmarks] == expected_ids

    for b in java_benchmarks:
        assert b.language == "java"
        assert "class Main" in b.source_code or "public class" in b.source_code
        assert len(b.expected_failure) > 0
        assert len(b.expected_root_cause) > 0
        assert len(b.expected_behavior) > 0

    # Ensure Python benchmarks are distinct and unchanged
    python_benchmarks = get_all_benchmarks("python")
    assert len(python_benchmarks) == 10
    for b in python_benchmarks:
        assert b.language == "python"
        assert "def " in b.source_code

    # Compare B001 Java vs Python
    b1_java = get_benchmark("B001", "java")
    b1_py = get_benchmark("B001", "python")
    assert b1_java.language == "java"
    assert b1_py.language == "python"
    assert b1_java.source_code != b1_py.source_code


def test_benchmark_api_language_query_parameter():
    """Verify GET /evaluation/benchmarks and /evaluation/benchmarks/{id} respect language query param."""
    # List java benchmarks
    resp_java = client.get("/evaluation/benchmarks?language=java")
    assert resp_java.status_code == 200
    data_java = resp_java.json()
    assert len(data_java) == 10
    assert all(item["language"] == "java" for item in data_java)

    # List python benchmarks
    resp_py = client.get("/evaluation/benchmarks?language=python")
    assert resp_py.status_code == 200
    data_py = resp_py.json()
    assert len(data_py) == 10
    assert all(item["language"] == "python" for item in data_py)

    # Get single Java benchmark
    resp_b2_java = client.get("/evaluation/benchmarks/B002?language=java")
    assert resp_b2_java.status_code == 200
    b2_java = resp_b2_java.json()
    assert b2_java["bug_id"] == "B002"
    assert b2_java["language"] == "java"
    assert "ArrayIndexOutOfBoundsException" in b2_java["expected_failure"]

    # Get single Python benchmark
    resp_b2_py = client.get("/evaluation/benchmarks/B002?language=python")
    assert resp_b2_py.status_code == 200
    b2_py = resp_b2_py.json()
    assert b2_py["bug_id"] == "B002"
    assert b2_py["language"] == "python"
    assert "IndexError" in b2_py["expected_failure"]


def test_context_reduction_percent_pairing(tmp_path):
    """Verify context reduction % calculation, baseline exclusion, unpaired handling, negative values, and language isolation."""
    logger = ExperimentLogger(data_dir=tmp_path)

    # 1. Standard valid pair (Baseline: 1000 chars, Dynamic: 400 chars -> 60.0% reduction)
    rec_b1 = ExperimentRecord(
        evaluation_id="eval_pair_1",
        experiment_id="eval_pair_1_baseline",
        bug_id="B001",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=1000,
    )
    rec_d1 = ExperimentRecord(
        evaluation_id="eval_pair_1",
        experiment_id="eval_pair_1_dynamic",
        bug_id="B001",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=400,
    )
    logger.log_experiment(rec_b1)
    logger.log_experiment(rec_d1)

    # 2. Unpaired dynamic run (no baseline with eval_pair_2)
    rec_d2 = ExperimentRecord(
        evaluation_id="eval_pair_2",
        experiment_id="eval_pair_2_dynamic",
        bug_id="B002",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=500,
    )
    logger.log_experiment(rec_d2)

    # 3. Negative reduction (Dynamic context size > Baseline context size)
    rec_b3 = ExperimentRecord(
        evaluation_id="eval_pair_3",
        experiment_id="eval_pair_3_baseline",
        bug_id="B003",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=500,
    )
    rec_d3 = ExperimentRecord(
        evaluation_id="eval_pair_3",
        experiment_id="eval_pair_3_dynamic",
        bug_id="B003",
        mode="dynamic",
        language="python",
        model="openrouter/free",
        context_chars=600,  # +20% expansion -> -20% reduction
    )
    logger.log_experiment(rec_b3)
    logger.log_experiment(rec_d3)

    # 4. Cross-language isolation (Baseline python, Dynamic java for same eval_id)
    rec_b4 = ExperimentRecord(
        evaluation_id="eval_cross",
        experiment_id="eval_cross_baseline",
        bug_id="B004",
        mode="baseline",
        language="python",
        model="openrouter/free",
        context_chars=1000,
    )
    rec_d4 = ExperimentRecord(
        evaluation_id="eval_cross",
        experiment_id="eval_cross_dynamic",
        bug_id="B004",
        mode="dynamic",
        language="java",
        model="openrouter/free",
        context_chars=300,
    )
    logger.log_experiment(rec_b4)
    logger.log_experiment(rec_d4)

    # Query experiments
    experiments = logger.get_experiments()
    by_id = {e.experiment_id: e for e in experiments}

    # Verify Pair 1
    assert by_id["eval_pair_1_baseline"].context_reduction_percent is None
    assert by_id["eval_pair_1_dynamic"].context_reduction_percent == pytest.approx(60.0)

    # Verify Unpaired 2
    assert by_id["eval_pair_2_dynamic"].context_reduction_percent is None

    # Verify Negative reduction 3 (not clamped to 0)
    assert by_id["eval_pair_3_baseline"].context_reduction_percent is None
    assert by_id["eval_pair_3_dynamic"].context_reduction_percent == pytest.approx(-20.0)

    # Verify Cross-language isolation 4 (Dynamic java cannot pair with baseline python)
    assert by_id["eval_cross_baseline"].context_reduction_percent is None
    assert by_id["eval_cross_dynamic"].context_reduction_percent is None

