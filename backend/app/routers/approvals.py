from fastapi import APIRouter, Depends, HTTPException, Request

from app.db import from_json, get_connection, now_iso
from app.models import ActionOut, ApprovalDecision
from app.security import limiter, verify_api_key

router = APIRouter(prefix="/api/approvals", tags=["approvals"], dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[ActionOut])
@limiter.limit("60/minute")
def list_pending(request: Request) -> list[ActionOut]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM actions WHERE status = 'proposed' ORDER BY id DESC"
    ).fetchall()
    return [ActionOut(**{**dict(r), "input": from_json(r["input"]), "output": from_json(r["output"])}) for r in rows]


@router.post("/{action_id}/approve", response_model=ActionOut)
@limiter.limit("30/minute")
def approve(request: Request, action_id: int, decision: ApprovalDecision | None = None) -> ActionOut:
    return _decide(action_id, "approved", run_status="completed", reason=decision.reason if decision else None)


@router.post("/{action_id}/reject", response_model=ActionOut)
@limiter.limit("30/minute")
def reject(request: Request, action_id: int, decision: ApprovalDecision | None = None) -> ActionOut:
    reason = (decision.reason if decision else None) or "Rejected by user"
    return _decide(action_id, "rejected", run_status="escalated", reason=reason)


def _decide(action_id: int, new_status: str, run_status: str, reason: str | None) -> ActionOut:
    conn = get_connection()
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action not found")
    if row["status"] != "proposed":
        raise HTTPException(status_code=409, detail=f"Action already decided ({row['status']})")

    ts = now_iso()
    conn.execute(
        "UPDATE actions SET status = ?, decided_at = ? WHERE id = ?",
        (new_status, ts, action_id),
    )
    if new_status == "rejected":
        conn.execute(
            "UPDATE runs SET status = ?, error_reason = ? WHERE id = ?",
            (run_status, reason, row["run_id"]),
        )
    else:
        conn.execute("UPDATE runs SET status = ? WHERE id = ?", (run_status, row["run_id"]))
    conn.commit()

    updated = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    return ActionOut(**{**dict(updated), "input": from_json(updated["input"]), "output": from_json(updated["output"])})
