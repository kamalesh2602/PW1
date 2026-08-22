import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes.execution import router as execution_router

load_dotenv()

app = FastAPI(
    title="PW1 API",
    description="PW1 Secure Code Execution Playground Backend for Research Project Module 1",
    version="1.0.0"
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


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": "PW1 Execution Service"}
