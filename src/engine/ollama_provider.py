import requests
import json
from engine.content_parse import parse_tool_call_from_content
from engine.llm import LLMProvider, ChatWithToolsResult, ToolCallRequest
from typing import List, Dict, Any, Generator


class OllamaProvider(LLMProvider):
    MODEL = "qwen2.5-coder:7b"
    BASE_URL = "http://127.0.0.1:11434/v1"
    API_KEY = ""

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.API_KEY:
            headers["Authorization"] = f"Bearer {self.API_KEY}"
        return headers

    def generate(self, prompt: str) -> str:
        payload = {"model": self.MODEL, "prompt": prompt}
        resp = requests.post(
            f"{self.BASE_URL}/completions", headers=self._get_headers(), json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["text"].strip()

    def chat(self, messages: List[dict]) -> str:
        payload = {"model": self.MODEL, "messages": messages}
        resp = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self._get_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    # 原始定义：全部接收完返回字符串列表
    def stream(self, prompt: str) -> List[str]:
        chunks = []
        for delta in self.stream_generator(prompt):
            chunks.append(delta)
        return chunks

    # 同步生成器，一边拉流一边产出片段，不占用完整内存
    def stream_generator(self, prompt: str) -> Generator[str, None, None]:
        payload = {"model": self.MODEL, "prompt": prompt, "stream": True}
        resp = requests.post(
            f"{self.BASE_URL}/completions",
            headers=self._get_headers(),
            json=payload,
            stream=True,  # 开启流式分块读取
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            # Ensure line is str or bytes-like (iter_lines may return memoryview in some environments)
            if isinstance(line, memoryview):
                line = line.tobytes()
            if isinstance(line, (bytes, bytearray)):
                if line.startswith(b"data: "):
                    raw_data = line[len(b"data: ") :].decode("utf-8")
                else:
                    continue
            elif isinstance(line, str):
                if line.startswith("data: "):
                    raw_data = line.removeprefix("data: ")
                else:
                    continue
            else:
                continue
            if raw_data == "[DONE]":
                return
            chunk = json.loads(raw_data)
            delta_text = chunk["choices"][0]["text"]
            yield delta_text

    def structured_output(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "guided_decoding": {"type": "json", "json_schema": schema},
        }
        resp = requests.post(
            f"{self.BASE_URL}/completions", headers=self._get_headers(), json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        raw_json_str = data["choices"][0]["text"].strip()
        return json.loads(raw_json_str)

    def chat_with_tools(
        self,
        messages: List[dict],
        tools: List[dict],
    ) -> ChatWithToolsResult:
        payload = {
            "model": self.MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",  # 修复1：auto自动选择工具
            "stream": False,
        }
        resp = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self._get_headers(),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        # 修复2：防止 choices 为空抛异常
        choices = data.get("choices", [])
        if not choices:
            return ChatWithToolsResult(
                content=None, tool_calls=[], usage=data.get("usage", {})
            )
        choice = choices[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        tool_calls: List[ToolCallRequest] = []

        # 分支1：标准OpenAI格式 tool_calls 数组（llama3.2等）
        raw_calls = message.get("tool_calls", [])
        for raw_call in raw_calls:
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
                    arguments=arguments,
                )
            )

        # 分支2：qwen 把 tool call 写在 content 里（可能带 ```json 围栏）
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
        return ChatWithToolsResult(content=content, tool_calls=tool_calls, usage=usage)
