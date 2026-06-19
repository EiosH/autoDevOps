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
        path = kwargs["path"]
        with open(path, "r", encoding="utf-8") as f:
            return {"path": path, "content": f.read()}
