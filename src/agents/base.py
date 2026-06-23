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
                "Episodic memory (prior steps in this run):\n"
                + "\n".join(record.content for record in ctx.episodic)
            )
        tool_records = ctx.recent_tool_calls()
        if tool_records:
            trace_lines = []
            for record in tool_records:
                payload = json.loads(record.content)
                trace_lines.append(
                    f"- {payload['tool_name']}({json.dumps(payload['arguments'], ensure_ascii=False)})"
                    f" -> {payload['status']}"
                )
            parts.append("Short-term memory (recent tool calls):\n" + "\n".join(trace_lines))
        return "\n\n".join(parts)

    @abstractmethod
    def run(self, task: Task, ctx: RunContext) -> AgentResult:
        pass
