from abc import ABC, abstractmethod
from core.models import ToolSpec
from typing import Any


class BaseTool(ABC):
    spec: ToolSpec

    def __init__(self, spec) -> None:
        self.spec = spec

    @abstractmethod
    def run(self, **kwargs) -> Any:
        pass
