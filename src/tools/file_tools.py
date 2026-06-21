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
        path = kwargs["path"]
        content = kwargs["content"]
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "status": "written", "bytes": len(content)}


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
