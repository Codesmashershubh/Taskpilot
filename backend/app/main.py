from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db import init_db
from app.logging_config import configure_logging
from app.routers import agent, approvals, auth, dashboard
from app.scheduler import start_scheduler, stop_scheduler
from app.security import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="TaskPilot API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(agent.router)
app.include_router(approvals.router)
app.include_router(dashboard.router)
app.include_router(auth.router)


@app.get("/api/health")
def health() -> dict:
    """Unauthenticated liveness check only — reveals no data, safe to expose to uptime monitors."""
    return {"status": "ok"}
