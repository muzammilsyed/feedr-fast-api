"""Pixer API - FastAPI application."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import engine
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("[Backend] Database: OK")
    except Exception as e:
        print("[Backend] WARNING: Database connection failed:", e)
        print("[Backend] Ensure PostgreSQL is running (e.g. docker compose up -d postgres)")
    print("[Backend] Running - use http://localhost:8000 from this computer")
    print("[Backend] For device testing: http://YOUR_IP:8000 (run with --host 0.0.0.0)")
    print("[Backend] API: /api/v1 | Docs: /docs | Health: /health | Ready (DB): /ready")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")

# Serve uploaded media files (mapped to users: uploads/users/{user_id}/...)
uploads_dir = Path(settings.UPLOAD_DIR).resolve()
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/")
async def root():
    return {
        "name": "Pixer API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Health check including DB - use to verify backend is fully operational."""
    from fastapi.responses import JSONResponse
    from app.db.session import engine
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": str(e)},
        )
