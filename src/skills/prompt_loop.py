"""LLM function-calling loop over MCP tools, constrained by a skill whitelist."""

from __future__ import annotations

import json
from time import time

from core.models import TaskStatus, ToolCallRecord
from engine.content_parse import (
    example_from_finish_schema,
    is_valid_finish_output,
    parse_finish_output,
)
from engine.llm import LLMProvider
from protocols.mcp.client import McpClient
from protocols.mcp.convert import mcp_tools_to_openai
from skills.base import SkillResult


def run_prompt_skill_loop(
    *,
    llm: LLMProvider,
    mcp: McpClient,
    allowed_tools: list[str],
    system_prompt: str,
    user_message: str,
    finish_schema: dict,
    max_steps: int = 15,
) -> SkillResult:
    if not allowed_tools:
        return SkillResult(
            success=False,
            output={},
            error="PromptSkill requires a non-empty allowed_tools whitelist",
        )

    allowed = set(allowed_tools)
    mcp_tools = [t for t in mcp.list_tools() if t.name in allowed]

    discovered = {t.name for t in mcp_tools}
    missing = [n for n in allowed_tools if n not in discovered]
    if missing:
        return SkillResult(
            success=False,
            output={},
            error=(
                f"Whitelist tools not found via MCP discovery: {missing}. "
                f"Available: {sorted(discovered)}"
            ),
        )

    openai_tools = mcp_tools_to_openai(mcp_tools)
    finish_example = example_from_finish_schema(finish_schema)
    finish_instruction = (
        "When the task is complete, do NOT call a tool. "
        "Respond with ONLY a JSON object matching this shape (real values, not a schema):\n"
        + json.dumps(finish_example, ensure_ascii=False)
    )
    whitelist_note = (
        f"You may only call these MCP tools: {allowed_tools}. "
        "Use tools to inspect and change the workspace as needed."
    )

    messages: list[dict] = [
        {
            "role": "system",
            "content": system_prompt + "\n\n" + whitelist_note + "\n\n" + finish_instruction,
        },
        {"role": "user", "content": user_message},
    ]

    tool_calls: list[ToolCallRecord] = []

    for _ in range(max_steps):
        response = llm.chat_with_tools(messages, openai_tools)

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
                record = _invoke_mcp_tool(mcp, call.name, call.arguments, allowed_tools)
                tool_calls.append(record)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(
                            record.result
                            if record.result is not None
                            else {"error": record.error},
                            ensure_ascii=False,
                            default=str,
                        ),
                    }
                )
            continue

        if response.content:
            output = parse_finish_output(response.content)
            if is_valid_finish_output(output, finish_schema):
                return SkillResult(
                    success=True,
                    output=output,
                    tool_calls=tool_calls,
                )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Invalid finish JSON. Return ONLY an object with keys "
                        f"{finish_schema.get('required', [])}. "
                        f"Example: {json.dumps(finish_example, ensure_ascii=False)}"
                    ),
                }
            )
            continue

    return SkillResult(
        success=False,
        output={},
        error="PromptSkill max_steps exceeded",
        tool_calls=tool_calls,
    )


def _invoke_mcp_tool(
    mcp: McpClient,
    name: str,
    arguments: dict,
    allowed_tools: list[str],
) -> ToolCallRecord:
    started = time()
    if name not in allowed_tools:
        return ToolCallRecord(
            tool_name=name,
            arguments=arguments,
            status=TaskStatus.FAILED,
            started_at=started,
            finished_at=time(),
            error=(
                f"Tool '{name}' is not in this skill's whitelist. "
                f"Allowed: {allowed_tools}"
            ),
        )

    result = mcp.call_tool(name, arguments)
    finished = time()
    if result.is_error:
        return ToolCallRecord(
            tool_name=name,
            arguments=arguments,
            status=TaskStatus.FAILED,
            started_at=started,
            finished_at=finished,
            error=result.error or "MCP tool error",
            result={"error": result.error},
        )

    content = result.content
    if not isinstance(content, dict):
        content = {"result": content}
    return ToolCallRecord(
        tool_name=name,
        arguments=arguments,
        result=content,
        status=TaskStatus.SUCCESS,
        started_at=started,
        finished_at=finished,
    )
