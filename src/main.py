import json
from core.scheduler import ThinHarnessScheduler, MemoryStore
from agents import DevAgent, ReviewAgent, TestAgent
from tools import (
    ToolRegistry,
    ToolExecutor,
    ReadFileTool,
    WritePatchTool,
    GitDiffTool,
    RunTestsTool,
    ShellExecTool,
)
from core.models import Task, AgentRole
from core.planner import plan
from engine.ollama_provider import OllamaProvider


def main():
    toolRegistry = ToolRegistry()
    toolRegistry.register(ReadFileTool())
    toolRegistry.register(WritePatchTool())
    toolRegistry.register(GitDiffTool())
    toolRegistry.register(RunTestsTool())
    toolRegistry.register(ShellExecTool())
    toolExecutor = ToolExecutor(toolRegistry)
    ollama = OllamaProvider()
    devAgent = DevAgent(ollama, toolExecutor)
    test = TestAgent(ollama, toolExecutor)
    review = ReviewAgent(ollama, toolExecutor)
    scheduler = ThinHarnessScheduler()
    scheduler.register_agent(devAgent)
    scheduler.register_agent(test)
    scheduler.register_agent(review)
    user_goal = "workspace 里面的游戏程序 index.html 帮我修复下，能让游戏跑通"
    run_id = "run1"
    tasks = plan(user_goal, llm=ollama)
    snapshots = scheduler.execute_task_graph(run_id, tasks)
    report = scheduler.build_report(run_id)
    print(report)


if __name__ == "__main__":
    main()
