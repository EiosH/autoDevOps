import json
import os
import re

from core.models import SkillSpec, TaskStatus
from engine.llm import LLMProvider
from skills.base import BaseSkill, SkillResult
from tools.executor import ToolExecutor

_PATH_RE = re.compile(
    r"[\w./-]+\.(?:html|js|css|py|ts|tsx|json|md|txt|jsx|vue)\b"
)

CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["files", "summary"],
}

GENERATE_PROMPT = """You are a code generation assistant.

Task:
{goal}

Existing files (empty string means file does not exist yet):
{existing}

Rules:
- Return complete, runnable file contents (no placeholders or TODO-only stubs)
- Include every file path needed to fulfill the task
- Paths must be relative to the project root
"""


def extract_paths(text: str) -> list[str]:
    return list(dict.fromkeys(_PATH_RE.findall(text)))


class CodeWriteSkill(BaseSkill):
    def __init__(self) -> None:
        self.spec = SkillSpec(
            name="code_write",
            description=(
                "Read existing files, generate complete runnable code, "
                "write files, verify, and show git diff"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": (
                            "What to implement or change; include concrete file paths"
                        ),
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
        paths = extract_paths(goal)
        existing: dict[str, str] = {}

        for path in paths:
            record = executor.execute("read_file", path=path)
            tool_calls.append(record)
            if record.status == TaskStatus.SUCCESS and record.result:
                existing[path] = record.result.get("content", "")
            else:
                existing[path] = ""

        prompt = GENERATE_PROMPT.format(
            goal=goal,
            existing=json.dumps(existing, ensure_ascii=False, indent=2),
        )
        try:
            generated = llm.structured_output(prompt, CODE_SCHEMA)
        except Exception as e:
            return SkillResult(
                success=False,
                output={},
                error=f"LLM generation failed: {e}",
                tool_calls=tool_calls,
            )

        changed_files: list[str] = []
        for item in generated.get("files", []):
            path = item.get("path", "")
            content = item.get("content", "")
            if not path:
                continue

            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            write_rec = executor.execute("write_patch", path=path, content=content)
            tool_calls.append(write_rec)
            if write_rec.status != TaskStatus.SUCCESS:
                continue

            verify = executor.execute("read_file", path=path)
            tool_calls.append(verify)
            if (
                verify.status == TaskStatus.SUCCESS
                and verify.result
                and verify.result.get("content")
            ):
                changed_files.append(path)

        diff_rec = executor.execute("git_diff")
        tool_calls.append(diff_rec)

        if not changed_files:
            return SkillResult(
                success=False,
                output={"changed_files": [], "summary": generated.get("summary", "")},
                error="No files were written successfully",
                tool_calls=tool_calls,
            )

        return SkillResult(
            success=True,
            output={
                "changed_files": changed_files,
                "summary": generated.get("summary", ""),
            },
            tool_calls=tool_calls,
        )
