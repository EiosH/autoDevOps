import hashlib
import json
import re
from typing import Any

from core.models import AgentRole, MemoryRecord, MemoryType, RunContext, StepSnapshot, TaskStatus
from engine.content_parse import parse_finish_output
from engine.llm import LLMProvider
from memory.store import MemoryStore

DISTILL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "user_preference",
                            "fix_lesson",
                            "test_failure",
                            "project_convention",
                        ],
                    },
                    "problem": {"type": "string"},
                    "resolution": {"type": "string"},
                    "preferences": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["kind", "keywords"],
            },
        }
    },
    "required": ["memories"],
}

DISTILL_PROMPT = """You distill software-dev run artifacts into long-term project memories.

Return ONLY JSON matching this shape:
{{
  "memories": [
    {{
      "kind": "user_preference|fix_lesson|test_failure|project_convention",
      "problem": "one short sentence (fix_lesson/test_failure only)",
      "resolution": "one short sentence (fix_lesson only)",
      "preferences": ["..."],
      "keywords": ["3-8 search terms"]
    }}
  ]
}}

Rules:
- Output at most 3 memories; return {{"memories":[]}} if nothing reusable
- Store only durable knowledge (preferences, fix patterns, conventions) — not step IDs or tool traces
- fix_lesson: only when review failed then dev succeeded afterward
- user_preference: distill explicit user constraints from the goal
- keywords must help future retrieval (mix Chinese/English if input is Chinese)
- Keep each field under 120 characters

User goal:
{user_goal}

Run artifacts:
{artifacts}
"""

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "实现",
    "完成",
    "确保",
    "进行",
    "支持",
    "功能",
    "代码",
    "文件",
    "任务",
    "检查",
}


def extract_keywords(*texts: str, limit: int = 12) -> list[str]:
    combined = " ".join(text for text in texts if text)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z_][a-zA-Z0-9_]{2,}", combined)
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        key = token.lower()
        if key in STOPWORDS or key in seen:
            continue
        seen.add(key)
        result.append(token)
        if len(result) >= limit:
            break
    return result


def format_long_term_record(record: MemoryRecord) -> str:
    try:
        payload = json.loads(record.content)
    except json.JSONDecodeError:
        return record.content

    kind = payload.get("kind", record.metadata.get("kind", "memory"))
    keywords = payload.get("keywords", [])
    keyword_text = f" [keywords: {', '.join(keywords)}]" if keywords else ""

    if kind == "user_preference":
        prefs = payload.get("preferences") or [payload.get("summary", "")]
        return f"- [{kind}]{keyword_text} " + "；".join(p for p in prefs if p)

    problem = payload.get("problem", "")
    resolution = payload.get("resolution", "")
    if problem and resolution:
        return f"- [{kind}]{keyword_text} 问题: {problem} | 解法: {resolution}"
    if problem:
        return f"- [{kind}]{keyword_text} {problem}"
    return f"- [{kind}]{keyword_text} {payload.get('summary', record.content)}"


class LongTermMemoryManager:
    def __init__(
        self,
        llm: LLMProvider,
        store: MemoryStore,
        *,
        project_id: str = "default",
        recall_limit: int = 5,
    ) -> None:
        self.llm = llm
        self.store = store
        self.project_id = project_id
        self.recall_limit = recall_limit

    def recall(self, user_goal: str) -> list[MemoryRecord]:
        query_keywords = extract_keywords(user_goal)
        if not query_keywords:
            return []
        return self.store.recall_long_term(
            self.project_id,
            query_keywords,
            self.recall_limit,
        )

    def promote(self, ctx: RunContext) -> list[MemoryRecord]:
        artifacts = self._collect_artifacts(ctx)
        if not self._has_promotable_content(artifacts):
            return []

        distilled = self._distill_with_llm(ctx.user_goal, artifacts)
        saved: list[MemoryRecord] = []
        for item in distilled:
            if self._is_duplicate(item):
                continue
            record = self._to_record(item, ctx.run_id)
            self.store.add(record)
            saved.append(record)
        return saved

    def _collect_artifacts(self, ctx: RunContext) -> dict[str, Any]:
        artifacts: dict[str, Any] = {
            "user_goal": ctx.user_goal,
            "fix_cycles": [],
            "test_failures": [],
            "dev_summaries": [],
        }

        for index, snap in enumerate(ctx.snapshots):
            if snap.task.agent_role == AgentRole.REVIEW and self._review_failed(snap):
                dev_after = self._next_dev_snapshot(ctx.snapshots, index)
                if dev_after is not None:
                    artifacts["fix_cycles"].append(
                        {
                            "review_issues": snap.result.output.get("issues", []),
                            "review_summary": snap.result.output.get("summary"),
                            "dev_summary": dev_after.result.output.get("summary"),
                            "changed_files": dev_after.result.output.get("changed_files", []),
                            "dev_succeeded": dev_after.result.status == TaskStatus.SUCCESS,
                        }
                    )

            if snap.task.agent_role == AgentRole.TEST and not snap.result.output.get(
                "passed", True
            ):
                artifacts["test_failures"].append(
                    {
                        "summary": snap.result.output.get("summary"),
                        "test_path": snap.result.output.get("test_path"),
                    }
                )

            if (
                snap.task.agent_role == AgentRole.DEV
                and snap.result.status == TaskStatus.SUCCESS
            ):
                summary = snap.result.output.get("summary")
                if summary:
                    artifacts["dev_summaries"].append(summary)

        return artifacts

    def _has_promotable_content(self, artifacts: dict[str, Any]) -> bool:
        if artifacts.get("user_goal", "").strip():
            return True
        return bool(
            artifacts.get("fix_cycles")
            or artifacts.get("test_failures")
            or artifacts.get("dev_summaries")
        )

    def _distill_with_llm(self, user_goal: str, artifacts: dict[str, Any]) -> list[dict[str, Any]]:
        prompt = DISTILL_PROMPT.format(
            user_goal=user_goal,
            artifacts=json.dumps(artifacts, ensure_ascii=False, indent=2),
        )
        try:
            result = self.llm.structured_output(prompt, DISTILL_SCHEMA)
        except Exception:
            raw = self.llm.chat([{"role": "user", "content": prompt}])
            result = parse_finish_output(raw)

        memories = result.get("memories", [])
        if not isinstance(memories, list):
            return []
        return [item for item in memories if isinstance(item, dict) and item.get("kind")][:3]

    def _is_duplicate(self, item: dict[str, Any]) -> bool:
        keywords = [kw for kw in item.get("keywords", []) if isinstance(kw, str)]
        problem = item.get("problem") or ""
        return self.store.is_duplicate_long_term(
            self.project_id,
            problem,
            keywords,
        )

    def _to_record(self, item: dict[str, Any], run_id: str) -> MemoryRecord:
        kind = item.get("kind", "memory")
        fingerprint = json.dumps(item, ensure_ascii=False, sort_keys=True)
        digest = hashlib.md5(fingerprint.encode()).hexdigest()[:8]
        keywords = [kw for kw in item.get("keywords", []) if isinstance(kw, str)]
        return MemoryRecord(
            memory_id=f"{self.project_id}:{kind}:{digest}",
            memory_type=MemoryType.LONG_TERM,
            content=json.dumps(item, ensure_ascii=False),
            source="long_term.promote",
            metadata={
                "kind": kind,
                "keywords": keywords,
                "project": self.project_id,
                "run_id": run_id,
            },
        )

    @staticmethod
    def _review_failed(snap: StepSnapshot) -> bool:
        if snap.result.status == TaskStatus.FAILED:
            return True
        return snap.result.output.get("approved") is False

    @staticmethod
    def _next_dev_snapshot(
        snapshots: list[StepSnapshot], review_index: int
    ) -> StepSnapshot | None:
        for snap in snapshots[review_index + 1 :]:
            if snap.task.agent_role == AgentRole.DEV:
                return snap
        return None
