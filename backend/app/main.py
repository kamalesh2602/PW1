import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes.execution import router as execution_router
from app.routes.traces import router as traces_router
from app.mcp.server import mcp

load_dotenv()

# Initialise MCP's Streamable HTTP session manager within FastAPI's lifespan.
mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="PW1 API",
    description="PW1 Secure Code Execution Playground Backend for Research Project Module 1",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
origins = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://pw-1-two.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include execution routes
app.include_router(execution_router)
app.include_router(traces_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "PW1 Execution Service"}

# Mount after FastAPI's REST routes so it only handles the MCP protocol path.
# It shares this process's in-memory Trace Store with the execution routes.
app.mount("", mcp_app)
