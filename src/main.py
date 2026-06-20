import json
from core.scheduler import ThinHarnessScheduler, MemoryStore
from agents import DevAgent, ReviewAgent, TestAgent
from tools import ToolRegistry, ToolExecutor, ReadFileTool
from core.models import Task, AgentRole
from core.planner import plan


def main():
    toolRegistry = ToolRegistry()
    toolRegistry.register(ReadFileTool())
    toolExecutor = ToolExecutor(toolRegistry)
    devAgent = DevAgent(toolExecutor)
    test = TestAgent()
    review = ReviewAgent()
    scheduler = ThinHarnessScheduler()
    scheduler.register_agent(devAgent)
    scheduler.register_agent(test)
    scheduler.register_agent(review)
    tasks = plan("Fix readme wording and add unit tests")
    run_id = "run1"
    result = scheduler.execute_task_graph(run_id, tasks)
    report = scheduler.build_report("run1")
    print(report)


if __name__ == "__main__":
    main()
