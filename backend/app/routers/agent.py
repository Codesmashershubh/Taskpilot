from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.orchestrator import Orchestrator
from app.config import get_settings
from app.db import from_json, get_connection
from app.email_source.factory import get_email_source
from app.llm.factory import get_llm_provider
from app.models import ActionOut, RunDetailOut, RunOut, RunStepOut
from app.security import limiter, verify_api_key

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(verify_api_key)])


@router.post("/poll")
@limiter.limit("10/minute")
async def trigger_poll(request: Request) -> dict:
    """Manually trigger a check of the watched label — this is what the
    scheduler also calls on a timer, and what the dashboard's 'Check now'
    button hits."""
    settings = get_settings()
    orchestrator = Orchestrator(llm=get_llm_provider(), email_source=get_email_source())
    run_ids = await orchestrator.poll_and_process(settings.gmail_watch_label)
    return {"processed": len(run_ids), "run_ids": run_ids}


@router.get("/runs", response_model=list[RunOut])
@limiter.limit("60/minute")
def list_runs(request: Request, status: str | None = None, limit: int = 50) -> list[RunOut]:
    conn = get_connection()
    limit = max(1, min(limit, 200))
    if status:
        rows = conn.execute(
            "SELECT * FROM runs WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [RunOut(**dict(r)) for r in rows]


@router.get("/runs/{run_id}", response_model=RunDetailOut)
@limiter.limit("60/minute")
def get_run(request: Request, run_id: int) -> RunDetailOut:
    conn = get_connection()
    run_row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not run_row:
        raise HTTPException(status_code=404, detail="Run not found")

    step_rows = conn.execute("SELECT * FROM run_steps WHERE run_id = ? ORDER BY id ASC", (run_id,)).fetchall()
    action_rows = conn.execute("SELECT * FROM actions WHERE run_id = ? ORDER BY id ASC", (run_id,)).fetchall()

    steps = [RunStepOut(**{**dict(r), "detail": from_json(r["detail"])}) for r in step_rows]
    actions = [
        ActionOut(**{**dict(r), "input": from_json(r["input"]), "output": from_json(r["output"])})
        for r in action_rows
    ]
    return RunDetailOut(**dict(run_row), steps=steps, actions=actions)
