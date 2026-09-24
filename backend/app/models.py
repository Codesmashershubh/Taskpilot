from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TaskType = Literal["meeting_request", "invoice", "support_question", "other"]
RunStatus = Literal["pending", "in_progress", "awaiting_approval", "completed", "escalated", "failed"]
ActionStatus = Literal["proposed", "approved", "rejected", "completed"]


class EmailMessage(BaseModel):
    """Normalized email shape, regardless of whether it came from Gmail or the mock source."""

    id: str
    thread_id: str
    sender: str
    reply_to: str  # bare email address, extracted before `sender` is sanitized for display
    subject: str
    body: str
    received_at: str


class ClassificationResult(BaseModel):
    task_type: TaskType
    sender_intent: str
    key_dates: list[str] = Field(default_factory=list)
    amount: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class ReflectResult(BaseModel):
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str


class RunOut(BaseModel):
    id: int
    created_at: str
    source_email_id: str
    subject: Optional[str]
    sender: Optional[str]
    snippet: Optional[str]
    task_type: Optional[str]
    status: RunStatus
    confidence: Optional[float]
    latency_ms: Optional[float]
    cost_estimate: Optional[float]
    error_reason: Optional[str]


class RunStepOut(BaseModel):
    id: int
    run_id: int
    step_name: str
    detail: Any
    created_at: str


class ActionOut(BaseModel):
    id: int
    run_id: int
    tool_name: str
    input: Any
    output: Any
    status: ActionStatus
    created_at: str
    decided_at: Optional[str]


class RunDetailOut(RunOut):
    steps: list[RunStepOut]
    actions: list[ActionOut]


class DashboardStats(BaseModel):
    total_runs: int
    completed: int
    escalated: int
    failed: int
    awaiting_approval: int
    success_rate: float
    avg_latency_ms: float
    total_cost_estimate: float
    agent_status: Literal["idle", "working", "awaiting_approval"]


class ApprovalDecision(BaseModel):
    reason: Optional[str] = None
