from fastapi import APIRouter, Depends

from app.db import get_connection
from app.models import DashboardStats
from app.security import limiter, verify_api_key
from fastapi import Request

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(verify_api_key)])


@router.get("/stats", response_model=DashboardStats)
@limiter.limit("60/minute")
def get_stats(request: Request) -> DashboardStats:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
    completed = conn.execute("SELECT COUNT(*) c FROM runs WHERE status='completed'").fetchone()["c"]
    escalated = conn.execute("SELECT COUNT(*) c FROM runs WHERE status='escalated'").fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) c FROM runs WHERE status='failed'").fetchone()["c"]
    awaiting = conn.execute("SELECT COUNT(*) c FROM runs WHERE status='awaiting_approval'").fetchone()["c"]
    in_progress = conn.execute("SELECT COUNT(*) c FROM runs WHERE status='in_progress'").fetchone()["c"]

    avg_latency_row = conn.execute("SELECT AVG(latency_ms) a FROM runs WHERE latency_ms IS NOT NULL").fetchone()
    total_cost_row = conn.execute("SELECT SUM(cost_estimate) s FROM runs WHERE cost_estimate IS NOT NULL").fetchone()

    # "Success" = the agent reached a resolved, non-error state without needing a human to rescue it.
    resolved = completed + awaiting
    denom = resolved + escalated + failed
    success_rate = (resolved / denom) if denom else 0.0

    if in_progress > 0:
        agent_status = "working"
    elif awaiting > 0:
        agent_status = "awaiting_approval"
    else:
        agent_status = "idle"

    return DashboardStats(
        total_runs=total,
        completed=completed,
        escalated=escalated,
        failed=failed,
        awaiting_approval=awaiting,
        success_rate=round(success_rate, 4),
        avg_latency_ms=round(avg_latency_row["a"] or 0.0, 1),
        total_cost_estimate=round(total_cost_row["s"] or 0.0, 4),
        agent_status=agent_status,
    )
