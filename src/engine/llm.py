from abc import ABC, abstractmethod


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
