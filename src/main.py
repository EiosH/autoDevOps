from core.scheduler import ThinHarnessScheduler
from agents import DevAgent, ReviewAgent, TestAgent
from tools import (
    ToolRegistry,
    ReadFileTool,
    WritePatchTool,
    DeleteFileTool,
    CheckFormatTool,
    GitDiffTool,
    RunTestsTool,
)
from skills import (
    SkillRegistry,
    SkillExecutor,
    CodeWriteSkill,
    CodeRefactorSkill,
    CodeReviewSkill,
    RunTestSkill,
)
from protocols.mcp import LocalMcpClient, LocalMcpServer
from core.planner import plan
from engine.ollama_provider import OllamaProvider
from memory import LongTermMemoryManager, create_memory_store


def main():
    tool_registry = ToolRegistry()
    tool_registry.register(ReadFileTool())
    tool_registry.register(WritePatchTool())
    tool_registry.register(DeleteFileTool())
    tool_registry.register(CheckFormatTool())
    tool_registry.register(GitDiffTool())
    tool_registry.register(RunTestsTool())

    mcp = LocalMcpClient(LocalMcpServer(tool_registry))

    skill_registry = SkillRegistry()
    skill_registry.register(CodeWriteSkill())
    skill_registry.register(CodeRefactorSkill())
    skill_registry.register(CodeReviewSkill())
    skill_registry.register(RunTestSkill())

    llm = OllamaProvider()
    skill_executor = SkillExecutor(skill_registry, mcp, llm)
    long_term_memory = LongTermMemoryManager(
        llm,
        create_memory_store(),
        project_id="autoDevOps",
    )

    scheduler = ThinHarnessScheduler(long_term_memory=long_term_memory)
    scheduler.register_agent(DevAgent(llm, skill_executor))
    scheduler.register_agent(TestAgent(llm, skill_executor))
    scheduler.register_agent(ReviewAgent(llm, skill_executor))

    user_goal = """1.失败之后不要怕重复弹出 “game over” 提示 2.支持新功能，等待玩家按下空格键开始
    """
    run_id = "run1"
    tasks = plan(user_goal, llm=llm)
    scheduler.execute_task_graph(run_id, tasks, user_goal=user_goal)
    print(scheduler.build_report(run_id))


if __name__ == "__main__":
    main()
