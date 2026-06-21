import json
import os
from typing import Any, Dict, Generator, List

import requests

from engine.content_parse import parse_finish_output, parse_tool_call_from_content
from engine.llm import ChatWithToolsResult, LLMProvider, ToolCallRequest


class vLLMProvider(LLMProvider):
    """OpenAI-compatible client for a local vLLM server."""

    BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    MODEL = os.getenv("VLLM_MODEL", "Qwen2.5-Coder-7B-Instruct-AWQ")
    API_KEY = os.getenv("VLLM_API_KEY", "")
    TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "120"))

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ) -> None:
        if base_url is not None:
            self.BASE_URL = base_url.rstrip("/")
        if model is not None:
            self.MODEL = model
        if api_key is not None:
            self.API_KEY = api_key
        if timeout is not None:
            self.TIMEOUT = timeout

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.API_KEY:
            headers["Authorization"] = f"Bearer {self.API_KEY}"
        return headers

    def _post(self, path: str, payload: dict, **kwargs) -> dict:
        resp = requests.post(
            f"{self.BASE_URL}{path}",
            headers=self._get_headers(),
            json=payload,
            timeout=kwargs.pop("timeout", self.TIMEOUT),
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()

    def _model_payload(self, **extra: Any) -> dict:
        return {"model": self.MODEL, **extra}

    def generate(self, prompt: str) -> str:
        data = self._post(
            "/completions",
            self._model_payload(prompt=prompt),
        )
        return data["choices"][0]["text"].strip()

    def chat(self, messages: List[dict]) -> str:
        data = self._post(
            "/chat/completions",
            self._model_payload(messages=messages, stream=False),
        )
        return data["choices"][0]["message"]["content"].strip()

    def stream(self, prompt: str) -> List[str]:
        return list(self.stream_generator(prompt))

    def stream_generator(self, prompt: str) -> Generator[str, None, None]:
        resp = requests.post(
            f"{self.BASE_URL}/completions",
            headers=self._get_headers(),
            json=self._model_payload(prompt=prompt, stream=True),
            stream=True,
            timeout=self.TIMEOUT,
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if isinstance(line, memoryview):
                line = line.tobytes()
            if isinstance(line, (bytes, bytearray)):
                if not line.startswith(b"data: "):
                    continue
                raw_data = line[len(b"data: ") :].decode("utf-8")
            elif isinstance(line, str):
                if not line.startswith("data: "):
                    continue
                raw_data = line.removeprefix("data: ")
            else:
                continue
            if raw_data == "[DONE]":
                return
            chunk = json.loads(raw_data)
            delta_text = chunk["choices"][0].get("text") or ""
            if delta_text:
                yield delta_text

    def structured_output(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]

        try:
            data = self._post(
                "/chat/completions",
                self._model_payload(
                    messages=messages,
                    stream=False,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "result_schema",
                            "schema": schema,
                            "strict": True,
                        },
                    },
                ),
            )
            content = data["choices"][0]["message"]["content"]
            return json.loads(content.strip())
        except (requests.HTTPError, json.JSONDecodeError, KeyError, IndexError):
            pass

        # vLLM fallback: guided JSON via extra_body
        try:
            data = self._post(
                "/chat/completions",
                self._model_payload(
                    messages=messages,
                    stream=False,
                    extra_body={"guided_json": schema},
                ),
            )
            content = data["choices"][0]["message"]["content"]
            return json.loads(content.strip())
        except (requests.HTTPError, json.JSONDecodeError, KeyError, IndexError):
            pass

        # Last resort: plain chat + parse
        raw = self.chat(messages)
        return parse_finish_output(raw)

    def chat_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
    ) -> ChatWithToolsResult:
        data = self._post(
            "/chat/completions",
            self._model_payload(
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=False,
            ),
        )

        choices = data.get("choices", [])
        if not choices:
            return ChatWithToolsResult(
                content=None,
                tool_calls=[],
                usage=data.get("usage", {}),
            )

        message = choices[0].get("message", {})
        usage = data.get("usage", {})
        tool_calls: List[ToolCallRequest] = []

        for raw_call in message.get("tool_calls") or []:
            fn = raw_call.get("function", {})
            args_raw = fn.get("arguments", "{}")
            try:
                arguments = (
                    json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                )
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCallRequest(
                    id=raw_call.get("id", ""),
                    name=fn.get("name", ""),
                    arguments=arguments or {},
                )
            )

        content_raw = (message.get("content") or "").strip()
        if content_raw and not tool_calls:
            func_data = parse_tool_call_from_content(content_raw)
            if func_data:
                tool_calls.append(
                    ToolCallRequest(
                        id="local_qwen_call",
                        name=func_data["name"],
                        arguments=func_data["arguments"],
                    )
                )
                content_raw = ""

        content = content_raw if content_raw else None
        return ChatWithToolsResult(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
        )
