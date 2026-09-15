import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agent.fixer import FixerAgent
from app.services.executor import CodeExecutionService
from app.models.execution import ExecutionRequest, ExecutionLanguage

client = TestClient(app)


@pytest.mark.asyncio
async def test_fixer_agent_zerodivisionerror():

    executor = CodeExecutionService()
    # 1. Execute buggy Python code producing ZeroDivisionError
    exec_response = executor.execute_code(ExecutionRequest(
        language=ExecutionLanguage.PYTHON,
        code="def compute(a, b):\n    return a / b\n\nprint(compute(10, 0))"
    ))
    assert exec_response.execution_id is not None
    assert exec_response.status.value == "runtime_error"

    # 2. Run automatic bug fixer agent
    agent = FixerAgent()
    result = await agent.fix(exec_response.execution_id)

    # 3. Assert repair outcome
    assert result.execution_id == exec_response.execution_id
    assert result.success is True
    assert result.attempts >= 1
    assert result.fixed_code is not None
    assert result.final_execution_id is not None
    assert result.original_diagnosis is not None
    assert result.original_diagnosis.diagnosis != ""


def test_fix_endpoint_zerodivisionerror():
    executor = CodeExecutionService()
    exec_response = executor.execute_code(ExecutionRequest(
        language=ExecutionLanguage.PYTHON,
        code="a = 5\nb = 0\nprint(a / b)"
    ))
    assert exec_response.execution_id is not None

    response = client.post("/debug/fix", json={"execution_id": exec_response.execution_id})
    assert response.status_code == 200
    data = response.json()
    assert data["execution_id"] == exec_response.execution_id
    assert data["success"] is True
    assert data["attempts"] >= 1
    assert data["fixed_code"] is not None
    assert data["final_execution_id"] is not None


def test_fix_endpoint_non_existent_execution():
    response = client.post("/debug/fix", json={"execution_id": "non-existent-id-12345"})
    assert response.status_code == 404


if __name__ == "__main__":
    import asyncio
    print("--- Running test_fixer_agent_zerodivisionerror ---")
    asyncio.run(test_fixer_agent_zerodivisionerror())
    print("PASSED test_fixer_agent_zerodivisionerror")

    print("--- Running test_fix_endpoint_zerodivisionerror ---")
    test_fix_endpoint_zerodivisionerror()
    print("PASSED test_fix_endpoint_zerodivisionerror")

    print("--- Running test_fix_endpoint_non_existent_execution ---")
    test_fix_endpoint_non_existent_execution()
    print("PASSED test_fix_endpoint_non_existent_execution")

    print("\nALL MODULE 6 FIXER TESTS PASSED SUCCESSFULLY!")