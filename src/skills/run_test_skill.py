from core.models import SkillSpec, TaskStatus
from engine.llm import LLMProvider
from skills.base import BaseSkill, SkillResult
from skills.path_utils import extract_paths
from tools.executor import ToolExecutor


class RunTestSkill(BaseSkill):
    def __init__(self) -> None:
        self.spec = SkillSpec(
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

    def execute(
        self,
        executor: ToolExecutor,
        llm: LLMProvider,
        **kwargs,
    ) -> SkillResult:
        goal = kwargs.get("goal", "")
        test_path = kwargs.get("test_path", "tests/")
        tool_calls: list = []

        for path in extract_paths(goal):
            rec = executor.execute("read_file", path=path)
            tool_calls.append(rec)

        test_rec = executor.execute("run_tests", test_path=test_path)
        tool_calls.append(test_rec)

        passed = False
        stdout = ""
        if test_rec.status == TaskStatus.SUCCESS and test_rec.result:
            passed = test_rec.result.get("returncode") == 0
            stdout = test_rec.result.get("stdout", "")

        output = {
            "passed": passed,
            "test_path": test_path,
            "summary": stdout[:500] if stdout else "No test output",
        }
        return SkillResult(
            success=passed,
            output=output,
            error=None if passed else "Tests failed",
            tool_calls=tool_calls,
        )
