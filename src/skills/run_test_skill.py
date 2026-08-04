from core.models import SkillSpec
from skills.prompt_skill import PromptSkill

FINISH_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {"type": "boolean"},
        "test_path": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["passed", "summary"],
}

SYSTEM_PROMPT = """You are a test-running skill.

Use MCP tools to read relevant source files if needed, then run_tests.
Interpret the test tool output and finish with whether tests passed.

Rules:
- Prefer run_tests with an appropriate test_path (default tests/ if unspecified)
- Summarize failures briefly from stdout/stderr
- When finished, return JSON with passed, test_path, and summary
"""


class RunTestSkill(PromptSkill):
    allowed_tools = ["read_file", "run_tests"]
    system_prompt = SYSTEM_PROMPT
    finish_schema = FINISH_SCHEMA

    def __init__(self) -> None:
        super().__init__(
            SkillSpec(
                name="run_test",
                description="Read source files and run tests via pytest",
                input_schema={
                    "type": "object",
                    "properties": {
                        "goal": {
                            "type": "string",
                            "description": "What to test; include file paths if relevant",
                        },
                        "test_path": {
                            "type": "string",
                            "description": "Path to test file or directory",
                            "default": "tests/",
                        },
                    },
                    "required": ["goal"],
                },
            )
        )

    def build_user_message(self, **kwargs) -> str:
        goal = kwargs.get("goal", "")
        test_path = kwargs.get("test_path", "tests/")
        return f"Goal:\n{goal}\n\nPreferred test_path: {test_path}"
