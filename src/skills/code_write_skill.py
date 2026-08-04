from core.models import SkillSpec
from skills.prompt_skill import PromptSkill

FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "changed_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["changed_files", "summary"],
}

SYSTEM_PROMPT = """You are a greenfield code generation skill.

Use MCP tools to create new files from scratch (0-to-1). Prefer write_patch for new
or updated file contents. Use read_file to check whether a path already exists.
Use git_diff at the end to verify changes.

Rules:
- Write complete, runnable file contents (no placeholders or TODO-only stubs)
- Paths must be relative to the current working directory
- Include every file needed to fulfill the goal
- When finished, return JSON with changed_files and summary
"""


class CodeWriteSkill(PromptSkill):
    allowed_tools = ["read_file", "write_patch", "git_diff"]
    system_prompt = SYSTEM_PROMPT
    finish_schema = FINISH_SCHEMA

    def __init__(self) -> None:
        super().__init__(
            SkillSpec(
                name="code_write",
                description=(
                    "Greenfield code generation: create new files from scratch "
                    "(0-to-1). Use when no existing code needs restructuring."
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
        )

    def build_user_message(self, **kwargs) -> str:
        goal = kwargs.get("goal", "")
        return f"Goal:\n{goal}"
