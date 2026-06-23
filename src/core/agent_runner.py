from dataclasses import dataclass
import json

from core.models import AgentResult, RunContext, Task, TaskStatus, ToolCallRecord
from engine.content_parse import (
    example_from_finish_schema,
    is_valid_finish_output,
    parse_finish_output,
)
from engine.llm import LLMProvider
from skills.executor import SkillExecutor
from skills.registry import SkillRegistry


def skill_specs_to_openai_tools(
    registry: SkillRegistry, allowed_skills: list[str]
) -> list[dict]:
    tools = []
    for spec in registry.list_skills():
        if spec.name not in allowed_skills:
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
        )
    return tools


@dataclass
class AgentRunner:

    def run_loop(
        self,
        llm: LLMProvider,
        skill_executor: SkillExecutor,
        allowed_skills: list[str],
        task: Task,
        agent_name: str,
        system_prompt: str,
        user_message: str,
        finish_schema: dict,
        ctx: RunContext | None = None,
        max_steps: int = 20,
    ) -> AgentResult:
        tool_calls_log = []
        token_cost = 0

        finish_example = example_from_finish_schema(finish_schema)
        finish_instruction = (
            "When you are done and need no more skills, respond with ONLY a JSON object "
            "containing actual results (NOT a JSON Schema definition). Example:\n"
            + json.dumps(finish_example, ensure_ascii=False)
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt + "\n\n" + finish_instruction},
            {"role": "user", "content": user_message},
        ]

        openai_tools = skill_specs_to_openai_tools(
            skill_executor.registry, allowed_skills
        )
        print(f"\nagent {agent_name}----------")

        for _ in range(max_steps):
            response = llm.chat_with_tools(messages, openai_tools)
            token_cost += response.usage.get("total_tokens", 0)

            if response.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.name,
                                    "arguments": json.dumps(call.arguments),
                                },
                            }
                            for call in response.tool_calls
                        ],
                    }
                )
                for call in response.tool_calls:
                    if call.name not in allowed_skills:
                        record = ToolCallRecord(
                            tool_name=call.name,
                            arguments=call.arguments,
                            status=TaskStatus.FAILED,
                            error=(
                                f"Skill '{call.name}' is not available. "
                                f"Use only: {allowed_skills}. "
                                "When the task is complete, do NOT call a skill; "
                                "respond with the finish JSON object instead."
                            ),
                        )
                        inner_calls: list[ToolCallRecord] = []
                    else:
                        record, inner_calls = skill_executor.execute(
                            call.name, **call.arguments
                        )
                        print(
                            f"call skill: name:{call.name} argument:{call.arguments}",
                        )

                    tool_calls_log.append(record)
                    tool_calls_log.extend(inner_calls)
                    if ctx is not None:
                        ctx.tool_trace.append(record)
                        ctx.tool_trace.extend(inner_calls)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                record.result or {"error": record.error}
                            ),
                        }
                    )
                continue

            if response.content:
                output = parse_finish_output(response.content)
                if is_valid_finish_output(output, finish_schema):
                    last_skill = next(
                        (
                            r
                            for r in reversed(tool_calls_log)
                            if r.tool_name in allowed_skills
                        ),
                        None,
                    )
                    if last_skill and last_skill.status == TaskStatus.FAILED:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"Skill '{last_skill.tool_name}' failed: "
                                    f"{last_skill.error or last_skill.result}. "
                                    "Retry the skill with corrected paths before finishing."
                                ),
                            }
                        )
                        continue
                    return AgentResult(
                        agent_name=agent_name,
                        task_id=task.task_id,
                        status=TaskStatus.SUCCESS,
                        output=output,
                        tool_calls=tool_calls_log,
                        token_cost=token_cost,
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Invalid finish response. Return ONLY a JSON object with required keys "
                            f"{finish_schema.get('required', [])}. "
                            f"Example: {json.dumps(finish_example, ensure_ascii=False)}. "
                            f'Do not return {{"error": ...}}.'
                        ),
                    }
                )
                continue

        print(f"------------")

        return AgentResult(
            agent_name=agent_name,
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error="max_steps exceeded",
        )
