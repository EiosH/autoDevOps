from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatWithToolsResult:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        pass

    @abstractmethod
    def stream(self, prompt: str) -> list[str]:
        pass

    @abstractmethod
    def structured_output(self, prompt: str, schema: dict) -> dict:
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> ChatWithToolsResult:
        pass
