import json
import re

from core.models import SkillSpec, TaskStatus
from engine.llm import LLMProvider
from skills.path_utils import resolve_paths_for_goal
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

Format check results (automated, treat failures as medium-severity issues):
{format_results}

File contents:
{files}

Review for correctness, maintainability, completeness, and code format.
Do NOT suggest file modifications — only report issues.
Mark approved=false if there are high-severity issues or any format check failures.
"""


def _paths_from_diff(diff: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)))


def _format_issues_from_results(
    format_results: list[dict],
) -> list[dict]:
    issues: list[dict] = []
    for result in format_results:
        if result.get("passed"):
            continue
        path = result.get("path", "")
        for item in result.get("issues", []):
            line = item.get("line")
            msg = item.get("message", "format issue")
            comment = f"[format] {msg}" + (f" (line {line})" if line else "")
            issues.append(
                {
                    "severity": "medium",
                    "file": path,
                    "comment": comment,
                }
            )
    return issues


class CodeReviewSkill(BaseSkill):
    def __init__(self) -> None:
        self.spec = SkillSpec(
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

    def _run_format_checks(
        self, executor: ToolExecutor, paths: list[str], tool_calls: list
    ) -> list[dict]:
        import os

        results: list[dict] = []
        for path in paths:
            if not os.path.isfile(path):
                continue
            rec = executor.execute("check_format", path=path)
            tool_calls.append(rec)
            if rec.status == TaskStatus.SUCCESS and rec.result:
                results.append(rec.result)
            else:
                results.append(
                    {
                        "path": path,
                        "passed": False,
                        "issues": [
                            {
                                "message": rec.error or "format check tool failed"
                            }
                        ],
                    }
                )
        return results

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

        paths = resolve_paths_for_goal(goal) or _paths_from_diff(diff_text)
        file_contents: dict[str, str] = {}
        for path in paths:
            rec = executor.execute("read_file", path=path)
            tool_calls.append(rec)
            if rec.status == TaskStatus.SUCCESS and rec.result:
                file_contents[path] = rec.result.get("content", "")

        format_results = self._run_format_checks(executor, paths, tool_calls)
        format_issues = _format_issues_from_results(format_results)

        prompt = REVIEW_PROMPT.format(
            goal=goal,
            diff=diff_text or "(no diff)",
            format_results=json.dumps(format_results, ensure_ascii=False, indent=2),
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

        existing_issues = review.get("issues", [])
        seen = {(i.get("file"), i.get("comment")) for i in existing_issues}
        for issue in format_issues:
            key = (issue.get("file"), issue.get("comment"))
            if key not in seen:
                existing_issues.append(issue)
                seen.add(key)

        review["issues"] = existing_issues
        review["format_check"] = {
            "passed": all(r.get("passed") for r in format_results),
            "results": format_results,
        }
        if format_issues and review.get("approved") is not False:
            review["approved"] = False

        return SkillResult(
            success=True,
            output=review,
            tool_calls=tool_calls,
        )
