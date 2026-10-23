import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.logging_config import setup_logging, get_app_logger
from app.routes.execution import router as execution_router
from app.routes.traces import router as traces_router
from app.routes.debug import router as debug_router
from app.routes.fix import router as fix_router
from app.evaluation.routes import router as evaluation_router
from app.mcp.server import mcp

load_dotenv()
setup_logging()
app_logger = get_app_logger("main")

# Initialise MCP's Streamable HTTP session manager within FastAPI's lifespan.
mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.WARNING)
    app_logger.info("PW1 API application starting up...")
    async with mcp.session_manager.run():
        app_logger.info("MCP session manager initialized on /mcp")
        yield
    app_logger.info("PW1 API application shutting down...")


app = FastAPI(
    title="PW1 API",
    description="PW1 Secure Code Execution Playground Backend for Research Project Module 1",
    version="1.0.0",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    app_logger.error("Unhandled exception processing %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )

# CORS configuration
raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,https://pw-1-two.vercel.app")
default_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "https://pw-1-two.vercel.app"]
env_origins = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
origins = list(dict.fromkeys(default_origins + env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include execution routes
app.include_router(execution_router)
app.include_router(traces_router)
app.include_router(debug_router)
app.include_router(fix_router)
app.include_router(evaluation_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "PW1 Execution Service"}

# Mount after FastAPI's REST routes so it only handles the MCP protocol path.
# It shares this process's in-memory Trace Store with the execution routes.
app.mount("", mcp_app)

# Module 6 automatic bug fixer route loaded

