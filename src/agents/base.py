import json
from abc import ABC, abstractmethod

from core.models import AgentCard, AgentResult, RunContext, Task


class BaseAgent(ABC):
    card: AgentCard

    def __init__(self, card) -> None:
        self.card = card

    def can_handle(self, task: Task) -> bool:
        return task.agent_role == self.card.role

    def build_user_message(self, task: Task, ctx: RunContext) -> str:
        parts = []
        if ctx.user_goal:
            parts.append(f"Original user goal: {ctx.user_goal}")
        parts.append(f"Task goal: {task.goal}")

        upstream = ctx.get_upstream(task)
        if upstream:
            parts.append(
                "Upstream task outputs:\n"
                + json.dumps(upstream, ensure_ascii=False, indent=2)
            )
        if ctx.episodic:
            parts.append(
                "Prior steps in this run:\n"
                + "\n".join(record.content for record in ctx.episodic)
            )
        if ctx.tool_trace:
            trace_lines = [
                f"- {r.tool_name}({json.dumps(r.arguments, ensure_ascii=False)})"
                f" -> {r.status.value}"
                for r in ctx.tool_trace[-20:]
            ]
            parts.append("Prior tool calls:\n" + "\n".join(trace_lines))
        return "\n\n".join(parts)

    @abstractmethod
    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        pass
