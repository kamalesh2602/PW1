from fastapi import APIRouter, HTTPException, status
from app.models.execution import ExecutionRequest, ExecutionResponse
from app.services.executor import CodeExecutionService

router = APIRouter(tags=["execution"])
execution_service = CodeExecutionService()


@router.post(
    "/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute user code securely in Docker",
    description="Accepts Python or Java code, executes it inside isolated Docker container, and returns standard execution results."
)
async def execute_code(payload: ExecutionRequest) -> ExecutionResponse:
    try:
        response = execution_service.execute_code(payload)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution service failed: {str(e)}"
        )
