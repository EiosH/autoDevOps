import json
import os

from core.models import SkillSpec, TaskStatus
from engine.llm import LLMProvider
from skills.base import BaseSkill, SkillResult
from skills.path_utils import resolve_paths_for_goal
from tools.executor import ToolExecutor

REFACTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["write", "delete"],
                    },
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["action", "path"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["changes", "summary"],
}

REFACTOR_PROMPT = """You are a code refactoring assistant.

Task:
{goal}

Existing files (empty string means file does not exist):
{existing}

Rules:
- Use action "write" to create or update a file (provide full content)
- Use action "delete" to remove obsolete files (no content needed)
- Apply logical order: write merged/updated files before deleting sources
- Return complete, runnable file contents for writes (no placeholders)
- Paths must be relative to the current working directory
- Update references in remaining files when deleting dependencies
"""


class CodeRefactorSkill(BaseSkill):
    def __init__(self) -> None:
        self.spec = SkillSpec(
            name="code_refactor",
            description=(
                "Refactor existing code: rewrite files, add new files, "
                "or delete obsolete files"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": (
                            "Refactoring goal; include all affected file paths"
                        ),
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional explicit list of files involved",
                    },
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
        extra_paths = kwargs.get("paths") or []
        tool_calls: list = []

        paths = resolve_paths_for_goal(goal, list(extra_paths))
        existing: dict[str, str] = {}
        for path in paths:
            record = executor.execute("read_file", path=path)
            tool_calls.append(record)
            if record.status == TaskStatus.SUCCESS and record.result:
                existing[path] = record.result.get("content", "")
            else:
                existing[path] = ""

        prompt = REFACTOR_PROMPT.format(
            goal=goal,
            existing=json.dumps(existing, ensure_ascii=False, indent=2),
        )
        try:
            plan = llm.structured_output(prompt, REFACTOR_SCHEMA)
        except Exception as e:
            return SkillResult(
                success=False,
                output={},
                error=f"LLM refactor planning failed: {e}",
                tool_calls=tool_calls,
            )

        changes = plan.get("changes", [])
        writes = [c for c in changes if c.get("action") == "write"]
        deletes = [c for c in changes if c.get("action") == "delete"]

        changed_files: list[str] = []
        deleted_files: list[str] = []

        for item in writes:
            path = item.get("path", "")
            content = item.get("content", "")
            if not path:
                continue

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

        for item in deletes:
            path = item.get("path", "")
            if not path:
                continue

            delete_rec = executor.execute("delete_file", path=path)
            tool_calls.append(delete_rec)
            if delete_rec.status != TaskStatus.SUCCESS:
                continue

            if not os.path.isfile(path):
                deleted_files.append(path)

        diff_rec = executor.execute("git_diff")
        tool_calls.append(diff_rec)

        if not changed_files and not deleted_files:
            return SkillResult(
                success=False,
                output={
                    "changed_files": [],
                    "deleted_files": [],
                    "summary": plan.get("summary", ""),
                },
                error="No files were changed or deleted successfully",
                tool_calls=tool_calls,
            )

        return SkillResult(
            success=True,
            output={
                "changed_files": changed_files,
                "deleted_files": deleted_files,
                "summary": plan.get("summary", ""),
            },
            tool_calls=tool_calls,
        )
