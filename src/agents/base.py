from abc import ABC, abstractmethod
from core.models import AgentCard, Task, AgentResult


class BaseAgent(ABC):
    card: AgentCard

    def __init__(self, card) -> None:
        self.card = card

    def can_handle(self, task: Task) -> bool:
        return task.agent_role == self.card.role

    @abstractmethod
    def run(self, task: Task) -> AgentResult:
        pass
