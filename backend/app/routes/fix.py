from fastapi import APIRouter, HTTPException
from app.agent.fixer import FixerAgent
from app.agent.models import FixRequest, FixResult

router = APIRouter(
    prefix="/debug",
    tags=["fixer-agent"],
)

agent = FixerAgent()


@router.post(
    "/fix",
    response_model=FixResult,
)
async def fix_bug(
    request: FixRequest,
) -> FixResult:
    try:
        result = await agent.fix(
            execution_id=request.execution_id,
            max_attempts=request.max_attempts,
        )
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Fixer agent failed: {str(exc)}",
        )
