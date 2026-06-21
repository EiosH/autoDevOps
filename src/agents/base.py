import json
from abc import ABC, abstractmethod

from core.models import AgentCard, AgentResult, Task


class BaseAgent(ABC):
    card: AgentCard

    def __init__(self, card) -> None:
        self.card = card

    def can_handle(self, task: Task) -> bool:
        return task.agent_role == self.card.role

    def build_user_message(self, task: Task) -> str:
        # Command line execution working directory: {cwd}.
        parts = [
            f"""Goal: {task.goal}
        """
        ]

        upstream = task.metadata.get("upstream")
        if upstream:
            parts.append(
                "Upstream task outputs:\n"
                + json.dumps(upstream, ensure_ascii=False, indent=2)
            )
        memories = task.metadata.get("memories")
        if memories:
            parts.append("Memories:\n" + "\n".join(memories))
        return "\n\n".join(parts)

    @abstractmethod
    def run(self, task: Task) -> AgentResult:
        pass
