import requests
import json
from engine.llm import LLMProvider
from typing import List, Dict, Any, Generator


class OllamaProvider(LLMProvider):
    BASE_URL = "http://127.0.0.1:11434/"
    API_KEY = ""

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.API_KEY:
            headers["Authorization"] = f"Bearer {self.API_KEY}"
        return headers

    def generate(self, prompt: str) -> str:
        payload = {"model": "auto", "prompt": prompt}
        resp = requests.post(f"{self.BASE_URL}/completions",
                             headers=self._get_headers(),
                             json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["text"].strip()

    def chat(self, messages: List[dict]) -> str:
        payload = {"model": "auto", "messages": messages}
        resp = requests.post(f"{self.BASE_URL}/chat/completions",
                             headers=self._get_headers(),
                             json=payload)
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
        payload = {"model": "auto", "prompt": prompt, "stream": True}
        resp = requests.post(
            f"{self.BASE_URL}/completions",
            headers=self._get_headers(),
            json=payload,
            stream=True  # 开启流式分块读取
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
                    raw_data = line[len(b"data: "):].decode("utf-8")
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

    def structured_output(self, prompt: str,
                          schema: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "model": "auto",
            "prompt": prompt,
            "guided_decoding": {
                "type": "json",
                "json_schema": schema
            }
        }
        resp = requests.post(f"{self.BASE_URL}/completions",
                             headers=self._get_headers(),
                             json=payload)
        resp.raise_for_status()
        data = resp.json()
        raw_json_str = data["choices"][0]["text"].strip()
        return json.loads(raw_json_str)
