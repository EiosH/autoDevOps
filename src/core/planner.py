from core.models import Task
from core.models import AgentRole
import uuid
from engine.llm import LLMProvider
from utils import get_project_root


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "goal": {"type": "string"},
                    "agent_role": {"type": "string", "enum": ["dev", "test", "review"]},
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                },
                "required": ["task_id", "goal", "agent_role"],
            },
        }
    },
    "required": ["tasks"],
}

PLANNER_PROMPT_TEMPLATE = """You are a task planner for a multi-agent DevOps system.

User goal:
{goal}

Project context:
    Auto-detected project root directory: {project_root}. 
    If the user does not specify a directory, the default directory is the project root directory.

Available agents (agent_role must be one of these):
- dev: read/write code, fix bugs (tools: read_file, write_patch, git_diff, shell_exec)
- test: write/run tests (tools: read_file, write_patch, run_tests) — skip if no tests apply
- review: read-only code review (tools: read_file, git_diff)

Rules:
1. Return a JSON object matching the schema with a "tasks" array
2. task_id must be unique short ids (e.g. "t1-dev", "t2-test")
3. dependencies must only reference task_ids in the same array
4. Use a DAG: dev first; test/review depend on prior steps when included
5. Each goal should be specific and actionable for that agent

Example for "fix workspace/index.html game":
tasks = [
  {{"task_id": "t1-dev", "goal": "Read and fix workspace/index.html so the game runs", "agent_role": "dev", "dependencies": [], "priority": 3}}
]
"""


def validate_task_graph(tasks: list[Task]) -> None:
    if not tasks:
        raise ValueError("Planner returned empty task list")

    ids = {t.task_id for t in tasks}
    allowed_roles = {AgentRole.DEV, AgentRole.TEST, AgentRole.REVIEW}

    for t in tasks:
        if t.agent_role not in allowed_roles:
            raise ValueError(f"Unsupported agent_role: {t.agent_role}")
        for dep in t.dependencies:
            if dep not in ids:
                raise ValueError(f"Unknown dependency {dep} for task {t.task_id}")

    # 环检测（简单拓扑）
    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {t.task_id: t for t in tasks}

    def dfs(tid: str) -> None:
        if tid in visiting:
            raise ValueError(f"Cycle detected at {tid}")
        if tid in visited:
            return
        visiting.add(tid)
        for dep in by_id[tid].dependencies:
            dfs(dep)
        visiting.remove(tid)
        visited.add(tid)

    for t in tasks:
        dfs(t.task_id)


def _parsed_to_tasks(parsed: dict, root_id: str) -> list[Task]:
    raw_tasks = parsed.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("Missing or empty 'tasks' in planner output")

    tasks: list[Task] = []
    for i, item in enumerate(raw_tasks):
        if not isinstance(item, dict):
            raise ValueError(f"Task item {i} is not an object")
        task_id = item.get("task_id") or f"{root_id}-{i}"
        tasks.append(
            Task(
                task_id=task_id,
                goal=item["goal"],
                agent_role=AgentRole(item["agent_role"]),
                dependencies=item.get("dependencies") or [],
                priority=item.get("priority", 3),
            )
        )
    return tasks


def plan(goal: str, llm: LLMProvider) -> list[Task]:
    root_id = str(uuid.uuid4())[:8]
    project_root = get_project_root()
    prompt = PLANNER_PROMPT_TEMPLATE.format(goal=goal, project_root=project_root)
    parsed = llm.structured_output(prompt, PLAN_SCHEMA)
    tasks = _parsed_to_tasks(parsed, root_id)
    print("tasks", tasks)
    validate_task_graph(tasks)
    return tasks
