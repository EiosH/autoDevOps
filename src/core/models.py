from enum import Enum
from time import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AgentRole(str, Enum):
    PLANNER = "planner"
    ARCHITECT = "architect"
    DEV = "dev"
    TEST = "test"
    REVIEW = "review"
    DEBUG = "debug"
    OPS = "ops"
    EVAL = "eval"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryType(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


class Task(BaseModel):
    task_id: str
    goal: str
    agent_role: AgentRole
    priority: int = Field(default=3, ge=1, le=5)
    dependencies: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)


# class TaskGraph(BaseModel):
#     graph_id: str
#     root_goal: str
#     tasks: List[Task] = Field(default_factory=list)


class AgentCard(BaseModel):
    name: str
    role: AgentRole
    capabilities: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    model_preference: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    status: TaskStatus = TaskStatus.PENDING
    started_at: float = Field(default_factory=time)
    finished_at: Optional[float] = None
    error: Optional[str] = None


class AgentResult(BaseModel):
    agent_name: str
    task_id: str
    status: TaskStatus
    output: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    token_cost: int = 0
    error: Optional[str] = None


class MemoryRecord(BaseModel):
    memory_id: str
    memory_type: MemoryType
    content: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time)


class EvaluationScore(BaseModel):
    task_id: str
    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    code_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: int = 0
    notes: List[str] = Field(default_factory=list)


class StepSnapshot(BaseModel):
    step_id: str
    run_id: str
    task: Task
    agent_card: AgentCard
    result: AgentResult
    # evaluation: Optional[EvaluationScore] = None
    # state_delta: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time)


class RunContext(BaseModel):
    run_id: str
    user_goal: str = ""
    snapshots: List[StepSnapshot] = Field(default_factory=list)
    tool_trace: List[ToolCallRecord] = Field(default_factory=list)
    episodic: List[MemoryRecord] = Field(default_factory=list)
    workspace_state: Dict[str, Any] = Field(default_factory=dict)

    def get_upstream(self, task: Task) -> Dict[str, Any]:
        upstream: Dict[str, Any] = {}
        for dep_id in task.dependencies:
            for snap in reversed(self.snapshots):
                if (
                    snap.task.task_id == dep_id
                    and snap.result.status == TaskStatus.SUCCESS
                ):
                    upstream[dep_id] = snap.result.output
                    break
        return upstream


class ExecutionReport(BaseModel):
    run_id: str
    total_tasks: int
    success_tasks: int
    failed_tasks: int
    executed_task_ids: List[str]
    agent_names: List[str]
    total_token_cost: int
    unique_tasks: int
    final_success_tasks: int
    final_failed_tasks: int
    retry_count: int


class ToolSpec(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class SkillSpec(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
