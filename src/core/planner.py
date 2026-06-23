from core.models import Task
from core.models import AgentRole
import uuid
from engine.llm import LLMProvider
from utils.path_helper import get_cwd


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
    Current working directory: {working_dir}
    All file paths in task goals must be relative to this directory.

Available agents (agent_role must be one of these):
- dev: greenfield code (skills: code_write) or refactor existing code (skills: code_refactor)
- test: run tests (skills: run_test) — skip if no tests apply
- review: code review (skills: code_review)

Rules:
1. Return a JSON object matching the schema with a "tasks" array
2. task_id must be unique short ids (e.g. "t1-dev", "t2-test")
3. dependencies must only reference task_ids in the same array
4. Use a DAG: dev first; test/review depend on prior steps when included
5. Each goal should be specific and actionable for that agent
6. Preserve ALL deliverables from user goal in at least one dev task goal
7. Greenfield features: prefer ONE dev task that creates ALL files, then ONE review task
8. Do NOT split "create dir", "write html", "write js" into separate dev tasks
9. Each dev task goal MUST list concrete file paths
10. Use code_refactor dev goal when task involves merging, splitting, moving, or deleting files
11. Use code_write dev goal for greenfield (0-to-1) creation
12. ALWAYS add exactly one review task after dev task(s); review must depend on all dev tasks
13. Add test task only if user explicitly mentions testing
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


def _ensure_review_task(tasks: list[Task], user_goal: str) -> list[Task]:
    """Planner LLM may omit review; always append one after dev tasks."""
    if any(t.agent_role == AgentRole.REVIEW for t in tasks):
        return tasks
    dev_tasks = [t for t in tasks if t.agent_role == AgentRole.DEV]
    if not dev_tasks:
        return tasks

    existing_ids = {t.task_id for t in tasks}
    review_id = "t-review"
    suffix = 1
    while review_id in existing_ids:
        review_id = f"t-review-{suffix}"
        suffix += 1

    dev_paths = " ".join(t.goal for t in dev_tasks)
    tasks.append(
        Task(
            task_id=review_id,
            goal=(
                f"Review code for: {user_goal}. "
                f"Verify files and logic from dev work: {dev_paths}"
            ),
            agent_role=AgentRole.REVIEW,
            dependencies=[t.task_id for t in dev_tasks],
            priority=2,
        )
    )
    return tasks


def plan(goal: str, llm: LLMProvider) -> list[Task]:
    root_id = str(uuid.uuid4())[:8]
    working_dir = get_cwd()
    prompt = PLANNER_PROMPT_TEMPLATE.format(goal=goal, working_dir=working_dir)
    parsed = llm.structured_output(prompt, PLAN_SCHEMA)
    tasks = _parsed_to_tasks(parsed, root_id)
    tasks = _ensure_review_task(tasks, goal)
    for task in tasks:
        print(f"Task: goal={task.goal} agentRole={task.agent_role} ")
        print(f"")
    validate_task_graph(tasks)
    return tasks
