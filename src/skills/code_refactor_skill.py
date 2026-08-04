from core.models import SkillSpec
from skills.prompt_skill import PromptSkill

FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "changed_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "deleted_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["changed_files", "summary"],
}

SYSTEM_PROMPT = """You are a code refactoring skill.

Use MCP tools to inspect and change existing code: read files, write updates,
delete obsolete files, then verify with git_diff.

Rules:
- Prefer reading relevant files before editing
- Use write_patch for create/update; delete_file for removals
- Write complete, runnable contents (no placeholders)
- Paths must be relative to the current working directory
- Update references in remaining files when deleting dependencies
- When finished, return JSON with changed_files, deleted_files (if any), and summary
"""


class CodeRefactorSkill(PromptSkill):
    allowed_tools = ["read_file", "write_patch", "delete_file", "git_diff"]
    system_prompt = SYSTEM_PROMPT
    finish_schema = FINISH_SCHEMA

    def __init__(self) -> None:
        super().__init__(
            SkillSpec(
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
        )

    def build_user_message(self, **kwargs) -> str:
        goal = kwargs.get("goal", "")
        paths = kwargs.get("paths") or []
        parts = [f"Goal:\n{goal}"]
        if paths:
            parts.append("Explicit paths:\n" + "\n".join(f"- {p}" for p in paths))
        return "\n\n".join(parts)
