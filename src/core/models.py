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
    tools: List[str] = Field(default_factory=list)
    model_preference: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW


# class ToolCallRecord(BaseModel):
#     tool_name: str
#     arguments: Dict[str, Any] = Field(default_factory=dict)
#     result: Optional[Dict[str, Any]] = None
#     status: TaskStatus = TaskStatus.PENDING
#     started_at: float = Field(default_factory=time)
#     finished_at: Optional[float] = None
#     error: Optional[str] = None


class AgentResult(BaseModel):
    agent_name: str
    task_id: str
    status: TaskStatus
    output: Dict[str, Any] = Field(default_factory=dict)
    # tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    token_cost: int = 0
    error: Optional[str] = None


# class MemoryRecord(BaseModel):
#     memory_id: str
#     memory_type: MemoryType
#     content: str
#     source: str
#     importance: float = Field(default=0.5, ge=0.0, le=1.0)
#     metadata: Dict[str, Any] = Field(default_factory=dict)
#     created_at: float = Field(default_factory=time)


class EvaluationScore(BaseModel):
    task_id: str
    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    code_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    latency_ms: int = 0
    notes: List[str] = Field(default_factory=list)


# class ExecutionContext(BaseModel):
#     run_id: str
#     user_goal: str
#     task_graph: Optional[TaskGraph] = None
#     memories: List[MemoryRecord] = Field(default_factory=list)
#     global_state: Dict[str, Any] = Field(default_factory=dict)
#     total_token_cost: int = 0
#     started_at: float = Field(default_factory=time)


class StepSnapshot(BaseModel):
    step_id: str
    run_id: str
    task: Task
    agent_card: AgentCard
    result: AgentResult
    # evaluation: Optional[EvaluationScore] = None
    # state_delta: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time)
