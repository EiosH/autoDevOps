import json
from core.scheduler import ThinHarnessScheduler, MemoryStore
from agents import DevAgent, ReviewAgent, TestAgent
from tools import ToolRegistry, ToolExecutor, ReadFileTool
from core.models import Task, AgentRole
from core.planner import plan
from engine.ollama_provider import OllamaProvider


def main():
    toolRegistry = ToolRegistry()
    toolRegistry.register(ReadFileTool())
    toolExecutor = ToolExecutor(toolRegistry)
    ollama = OllamaProvider()
    devAgent = DevAgent(ollama, toolExecutor)
    test = TestAgent(ollama)
    review = ReviewAgent(ollama)
    scheduler = ThinHarnessScheduler()
    scheduler.register_agent(devAgent)
    scheduler.register_agent(test)
    scheduler.register_agent(review)
    tasks = plan("Fix readme wording and add unit tests")
    run_id = "run1"
    scheduler.execute_task_graph(run_id, tasks)
    report = scheduler.build_report("run1")
    print(report)


if __name__ == "__main__":
    main()
