from fastapi import APIRouter, HTTPException

from app.agent.debugger import DebuggingAgent
from app.agent.models import DebugRequest, DebugDiagnosis


router = APIRouter(
    prefix="/debug",
    tags=["debugging-agent"],
)


agent = DebuggingAgent()


@router.post(
    "/diagnose",
    response_model=DebugDiagnosis,
)
async def diagnose(
    request: DebugRequest,
) -> DebugDiagnosis:

    try:

        result = await agent.diagnose(
    execution_id=request.execution_id,
    initial_context=request.initial_context,
)

        return result

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Debugging agent failed: {str(exc)}",
        )