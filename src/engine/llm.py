from abc import ABC, abstractmethod


class LLMProvider(ABC):

    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        ...

    @abstractmethod
    def structured_output(self, prompt: str, schema: dict) -> dict:
        ...
