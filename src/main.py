from core.scheduler import ThinHarnessScheduler
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
from skills import (
    SkillRegistry,
    SkillExecutor,
    CodeWriteSkill,
    CodeReviewSkill,
    RunTestSkill,
)
from core.planner import plan
from engine.ollama_provider import OllamaProvider
from engine.vllm_provider import vLLMProvider


def main():
    toolRegistry = ToolRegistry()
    toolRegistry.register(ReadFileTool())
    toolRegistry.register(WritePatchTool())
    toolRegistry.register(GitDiffTool())
    toolRegistry.register(RunTestsTool())
    toolRegistry.register(ShellExecTool())
    toolExecutor = ToolExecutor(toolRegistry)

    skillRegistry = SkillRegistry()
    skillRegistry.register(CodeWriteSkill())
    skillRegistry.register(CodeReviewSkill())
    skillRegistry.register(RunTestSkill())

    llm = OllamaProvider()
    # llm = vLLMProvider()
    skillExecutor = SkillExecutor(skillRegistry, toolExecutor, llm)
    devAgent = DevAgent(llm, skillExecutor)
    test = TestAgent(llm, skillExecutor)
    review = ReviewAgent(llm, skillExecutor)
    scheduler = ThinHarnessScheduler()
    scheduler.register_agent(devAgent)
    scheduler.register_agent(test)
    scheduler.register_agent(review)
    # user_goal = "在根目录里新建 workspace 文件夹，在里面实现 workspace/index.html 和 workspace/index.js 文件，做一个扫雷小游戏。实现完成后检查代码，确保不出问题"
    user_goal = "读取 workspace 下的 index.html、index.js文件，合并成一个，并且检查逻辑，然后完善"
    run_id = "run1"
    tasks = plan(user_goal, llm=llm)
    snapshots = scheduler.execute_task_graph(run_id, tasks, user_goal=user_goal)
    report = scheduler.build_report(run_id)
    print(report)


if __name__ == "__main__":
    main()
