from tools.base import BaseTool
from core.models import ToolSpec, RiskLevel


class ReadFileTool(BaseTool):

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(name="read_file",
                     description="Read text content from a local project file",
                     risk_level=RiskLevel.LOW,
                     input_schema={
                         "type": "object",
                         "properties": {
                             "path": {
                                 "type": "string"
                             }
                         },
                         "required": ["path"]
                     }))

    def run(self, **kwargs):
        import os

        path = kwargs["path"]
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        result = {"path": path, "content": content, "exists": True}
        if content == "":
            result["note"] = (
                "File exists but is empty (0 bytes). "
                "This is NOT the same as 'file does not exist'."
            )
        return result


class WritePatchTool(BaseTool):

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(name="write_patch",
                     description="Write or update file content",
                     risk_level=RiskLevel.MEDIUM,
                     input_schema={
                         "type": "object",
                         "properties": {
                             "path": {
                                 "type": "string"
                             },
                             "content": {
                                 "type": "string"
                             }
                         },
                         "required": ["path", "content"]
                     }))

    def run(self, **kwargs):
        import os

        path = kwargs["path"]
        content = kwargs["content"]
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "status": "written", "bytes": len(content)}


class DeleteFileTool(BaseTool):

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(
                name="delete_file",
                description="Delete a file from the project",
                risk_level=RiskLevel.MEDIUM,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            )
        )

    def run(self, **kwargs):
        import os

        path = kwargs["path"]
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")
        os.remove(path)
        return {"path": path, "status": "deleted"}


class CheckFormatTool(BaseTool):
    _WEB_EXTS = {".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".vue", ".json", ".md"}

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(
                name="check_format",
                description="Check code formatting and style for a single file",
                risk_level=RiskLevel.LOW,
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            )
        )

    def _basic_checks(self, path: str, content: str) -> list[dict]:
        issues: list[dict] = []
        if content and not content.endswith("\n"):
            issues.append({"message": "File must end with a newline"})
        for i, line in enumerate(content.splitlines(), start=1):
            if line.rstrip() != line:
                issues.append(
                    {"line": i, "message": "Trailing whitespace"}
                )
                break
        if "\t" in content and "    " in content:
            issues.append({"message": "Mixed tabs and spaces for indentation"})
        return issues

    def _run_cmd(self, cmd: list[str]):
        import subprocess

        return subprocess.run(cmd, capture_output=True, text=True, cwd=".")

    def _check_python(self, path: str) -> list[dict]:
        import shutil
        import subprocess

        issues: list[dict] = []
        compile_result = self._run_cmd(["python3", "-m", "py_compile", path])
        if compile_result.returncode != 0:
            msg = (compile_result.stderr or compile_result.stdout or "").strip()
            issues.append({"message": f"Python syntax error: {msg}"})

        if shutil.which("black"):
            result = self._run_cmd(["black", "--check", "--quiet", path])
            if result.returncode != 0:
                issues.append({"message": "black format check failed"})
        return issues

    def _check_prettier(self, path: str) -> list[dict]:
        import shutil

        if shutil.which("npx"):
            result = self._run_cmd(["npx", "--yes", "prettier", "--check", path])
            if result.returncode != 0:
                detail = (result.stdout or result.stderr or "").strip()
                return [{"message": f"prettier check failed: {detail[:200]}"}]
            return []

        if shutil.which("prettier"):
            result = self._run_cmd(["prettier", "--check", path])
            if result.returncode != 0:
                detail = (result.stdout or result.stderr or "").strip()
                return [{"message": f"prettier check failed: {detail[:200]}"}]
            return []

        return []

    def run(self, **kwargs):
        import os

        path = kwargs["path"]
        if not os.path.isfile(path):
            raise FileNotFoundError(f"No such file: {path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        ext = os.path.splitext(path)[1].lower()
        issues = self._basic_checks(path, content)

        if ext == ".py":
            issues.extend(self._check_python(path))
        elif ext in self._WEB_EXTS:
            issues.extend(self._check_prettier(path))

        return {"path": path, "passed": len(issues) == 0, "issues": issues}


class GitDiffTool(BaseTool):

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(name="git_diff",
                     description="Show git diff for modified files",
                     risk_level=RiskLevel.LOW,
                     input_schema={
                         "type": "object",
                         "properties": {
                             "file_path": {
                                 "type": "string",
                                 "description": "optional specific file"
                             }
                         }
                     }))

    def run(self, **kwargs):
        import subprocess
        file_path = kwargs.get("file_path", "")
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        return {
            "diff": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }


class RunTestsTool(BaseTool):

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(name="run_tests",
                     description="Run unit tests",
                     risk_level=RiskLevel.MEDIUM,
                     input_schema={
                         "type": "object",
                         "properties": {
                             "test_path": {
                                 "type": "string",
                                 "description": "path to test file or dir"
                             }
                         }
                     }))

    def run(self, **kwargs):
        import subprocess
        test_path = kwargs.get("test_path", "tests/")
        cmd = ["python", "-m", "pytest", test_path, "-v"]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }


class ShellExecTool(BaseTool):

    def __init__(self) -> None:
        super().__init__(
            ToolSpec(name="shell_exec",
                     description="Execute shell command safely",
                     risk_level=RiskLevel.HIGH,
                     input_schema={
                         "type": "object",
                         "properties": {
                             "command": {
                                 "type": "string"
                             }
                         },
                         "required": ["command"]
                     }))

    def run(self, **kwargs):
        import subprocess
        command = kwargs["command"]
        result = subprocess.run(command,
                                shell=True,
                                capture_output=True,
                                text=True,
                                cwd=".",
                                timeout=30)
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
