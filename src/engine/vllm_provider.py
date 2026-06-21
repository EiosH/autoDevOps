import json
import os
from typing import Any, Dict, Generator, List

import requests

from engine.content_parse import parse_finish_output, parse_tool_call_from_content
from engine.llm import ChatWithToolsResult, LLMProvider, ToolCallRequest


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class vLLMProvider(LLMProvider):
    """OpenAI-compatible client for a local vLLM server."""

    BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
    MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ")
    API_KEY = os.getenv("VLLM_API_KEY", "")
    TIMEOUT = int(os.getenv("VLLM_TIMEOUT", "120"))
    # Most vLLM deployments omit --enable-auto-tool-choice; client-side parsing avoids 400s.
    NATIVE_TOOLS = _env_bool("VLLM_NATIVE_TOOLS", False)
    # Only sent when NATIVE_TOOLS=true. Leave unset to omit tool_choice (vLLM default).
    TOOL_CHOICE = os.getenv("VLLM_TOOL_CHOICE")

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
        if not resp.ok:
            detail = resp.text[:500]
            raise requests.HTTPError(
                f"{resp.status_code} {resp.reason} for {path}: {detail}",
                response=resp,
            )
        return resp.json()

    @staticmethod
    def _sanitize_messages(messages: List[dict]) -> List[dict]:
        """vLLM rejects null assistant content; normalize for multi-turn tool loops."""
        sanitized: List[dict] = []
        for msg in messages:
            cleaned = dict(msg)
            if cleaned.get("role") == "assistant" and cleaned.get("content") is None:
                cleaned["content"] = ""
            sanitized.append(cleaned)
        return sanitized

    @staticmethod
    def _tools_prompt(tools: List[dict]) -> str:
        lines = [
            "Available tools. To call a tool, respond with ONLY a JSON object:",
            '{"name": "<tool_name>", "arguments": {<params>}}',
            "",
        ]
        for tool in tools:
            fn = tool.get("function", {})
            lines.append(f"- {fn.get('name', '')}: {fn.get('description', '')}")
            params = fn.get("parameters")
            if params:
                lines.append(
                    f"  parameters schema: {json.dumps(params, ensure_ascii=False)}"
                )
        return "\n".join(lines)

    def _inject_tools_prompt(
        self, messages: List[dict], tools: List[dict]
    ) -> List[dict]:
        if not tools:
            return list(messages)
        prompt = self._tools_prompt(tools)
        enriched = [dict(m) for m in messages]
        for msg in enriched:
            if msg.get("role") == "system":
                msg["content"] = f"{msg.get('content', '')}\n\n{prompt}"
                return enriched
        enriched.insert(0, {"role": "system", "content": prompt})
        return enriched

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
            self._model_payload(
                messages=self._sanitize_messages(messages),
                stream=False,
            ),
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

        # vLLM fallback: guided JSON as a top-level field (not extra_body)
        try:
            data = self._post(
                "/chat/completions",
                self._model_payload(
                    messages=messages,
                    stream=False,
                    guided_json=schema,
                ),
            )
            content = data["choices"][0]["message"]["content"]
            return json.loads(content.strip())
        except (requests.HTTPError, json.JSONDecodeError, KeyError, IndexError):
            pass

        # Last resort: plain chat + parse
        raw = self.chat(messages)
        return parse_finish_output(raw)

    def _parse_chat_response(self, data: dict) -> ChatWithToolsResult:
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

    def chat_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
    ) -> ChatWithToolsResult:
        sanitized = self._sanitize_messages(messages)

        if self.NATIVE_TOOLS:
            payload = self._model_payload(
                messages=sanitized,
                tools=tools,
                stream=False,
            )
            # tool_choice="auto" returns 400 unless the server was started with
            # --enable-auto-tool-choice; omit "auto" for compatibility.
            if self.TOOL_CHOICE:
                payload["tool_choice"] = self.TOOL_CHOICE
            data = self._post("/chat/completions", payload)
            return self._parse_chat_response(data)

        # Client-side tool parsing (recommended for Qwen2.5-Coder + default vLLM).
        api_messages = self._inject_tools_prompt(sanitized, tools)
        data = self._post(
            "/chat/completions",
            self._model_payload(messages=api_messages, stream=False),
        )
        return self._parse_chat_response(data)
