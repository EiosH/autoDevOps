import json
import re

from core.models import SkillSpec, TaskStatus
from engine.llm import LLMProvider
from skills.code_write_skill import extract_paths
from skills.base import BaseSkill, SkillResult
from tools.executor import ToolExecutor

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "file": {"type": "string"},
                    "comment": {"type": "string"},
                },
                "required": ["severity", "comment"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["approved", "issues", "summary"],
}

REVIEW_PROMPT = """You are a code review assistant.

Task:
{goal}

Git diff:
{diff}

File contents:
{files}

Review for correctness, maintainability, and completeness.
Do NOT suggest file modifications — only report issues.
Mark approved=false if there are high-severity issues.
"""


def _paths_from_diff(diff: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)))


class CodeReviewSkill(BaseSkill):
    def __init__(self) -> None:
        self.spec = SkillSpec(
            name="code_review",
            description="Inspect git diff and file contents, produce a code review",
            input_schema={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "What to review; include file paths if known",
                    }
                },
                "required": ["goal"],
            },
        )

    def execute(
        self,
        executor: ToolExecutor,
        llm: LLMProvider,
        **kwargs,
    ) -> SkillResult:
        goal = kwargs.get("goal", "")
        tool_calls: list = []

        diff_rec = executor.execute("git_diff")
        tool_calls.append(diff_rec)
        diff_text = ""
        if diff_rec.status == TaskStatus.SUCCESS and diff_rec.result:
            diff_text = diff_rec.result.get("diff", "")

        paths = extract_paths(goal) or _paths_from_diff(diff_text)
        file_contents: dict[str, str] = {}
        for path in paths:
            rec = executor.execute("read_file", path=path)
            tool_calls.append(rec)
            if rec.status == TaskStatus.SUCCESS and rec.result:
                file_contents[path] = rec.result.get("content", "")

        prompt = REVIEW_PROMPT.format(
            goal=goal,
            diff=diff_text or "(no diff)",
            files=json.dumps(file_contents, ensure_ascii=False, indent=2),
        )
        try:
            review = llm.structured_output(prompt, REVIEW_SCHEMA)
        except Exception as e:
            return SkillResult(
                success=False,
                output={},
                error=f"LLM review failed: {e}",
                tool_calls=tool_calls,
            )

        return SkillResult(
            success=True,
            output=review,
            tool_calls=tool_calls,
        )
