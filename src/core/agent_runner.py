from dataclasses import dataclass
import json

from core.models import AgentResult, Task, TaskStatus, ToolCallRecord
from engine.content_parse import (
    example_from_finish_schema,
    is_valid_finish_output,
    parse_finish_output,
)
from engine.llm import LLMProvider
from tools.executor import ToolExecutor
from tools.registry import ToolRegistry


def specs_to_openai_tools(
    registry: ToolRegistry, allowed_tools: list[str]
) -> list[dict]:
    tools = []
    for spec in registry.list_tools():
        if spec.name not in allowed_tools:
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
        tool_executor: ToolExecutor,
        allowed_tools: list[str],
        task: Task,
        agent_name: str,
        system_prompt: str,
        user_message: str,
        finish_schema: dict,
        max_steps: int = 20,
    ) -> AgentResult:
        tool_calls_log = []
        token_cost = 0

        finish_example = example_from_finish_schema(finish_schema)
        finish_instruction = (
            "When you are done and need no more tools, respond with ONLY a JSON object "
            "containing actual results (NOT a JSON Schema definition). Example:\n"
            + json.dumps(finish_example, ensure_ascii=False)
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt + "\n\n" + finish_instruction},
            {"role": "user", "content": user_message},
        ]

        openai_tools = specs_to_openai_tools(tool_executor.registry, allowed_tools)
        # print("allowed tools:", [t["function"]["name"] for t in openai_tools])
        for _ in range(max_steps):
            response = llm.chat_with_tools(messages, openai_tools)
            token_cost += response.usage.get("total_tokens", 0)
            # print("response.tool_calls", response.tool_calls)

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
                    if call.name not in allowed_tools:
                        record = ToolCallRecord(
                            tool_name=call.name,
                            arguments=call.arguments,
                            status=TaskStatus.FAILED,
                            error=(
                                f"Tool '{call.name}' is not available. "
                                f"Use only: {allowed_tools}. "
                                "When the task is complete, do NOT call a tool; "
                                "respond with the finish JSON object instead."
                            ),
                        )
                    else:
                        record = tool_executor.execute(call.name, **call.arguments)
                    tool_calls_log.append(record)
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

            # print("response content:", response.content)
            # print("response called tools:", response.tool_calls)
            if response.content:
                output = parse_finish_output(response.content)
                if is_valid_finish_output(output, finish_schema):
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

        return AgentResult(
            agent_name=agent_name,
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            error="max_steps exceeded",
        )
