from core.models import SkillSpec
from skills.prompt_skill import PromptSkill

FINISH_SCHEMA = {
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

SYSTEM_PROMPT = """You are a code review skill.

Use MCP tools to gather evidence: git_diff, read_file, and check_format on changed files.
Do NOT modify files — only report issues.

Rules:
- Treat format check failures as at least medium-severity issues
- Mark approved=false if there are high-severity issues or format failures
- Do not suggest applying patches yourself; reporting only
- When finished, return JSON with approved, issues, and summary
"""


class CodeReviewSkill(PromptSkill):
    allowed_tools = ["git_diff", "read_file", "check_format"]
    system_prompt = SYSTEM_PROMPT
    finish_schema = FINISH_SCHEMA

    def __init__(self) -> None:
        super().__init__(
            SkillSpec(
                name="code_review",
                description=(
                    "Inspect git diff, run format checks, read file contents, "
                    "and produce a code review"
                ),
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
        )

    def build_user_message(self, **kwargs) -> str:
        goal = kwargs.get("goal", "")
        return f"Review goal:\n{goal}"
