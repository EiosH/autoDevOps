import json
import re
from typing import Any


def strip_markdown_json(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _properties_look_like_schema_defs(props: dict[str, Any]) -> bool:
    for value in props.values():
        if isinstance(value, dict) and "type" in value:
            return True
    return False


def parse_tool_call_from_content(content_raw: str) -> dict[str, Any] | None:
    """Parse qwen-style tool JSON from message content. Returns None if not a tool call."""
    text = strip_markdown_json(content_raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    # Finish answers sometimes look like {"type":"object","properties":{...}}
    if data.get("type") == "object" and "properties" in data:
        return None

    name = data.get("name")
    arguments = data.get("arguments")
    if isinstance(name, str) and isinstance(arguments, dict):
        return {"name": name, "arguments": arguments}
    return None


def example_from_finish_schema(schema: dict[str, Any]) -> dict[str, Any]:
    props = schema.get("properties", {})
    example: dict[str, Any] = {}
    for key, spec in props.items():
        field_type = spec.get("type")
        if field_type == "array":
            example[key] = []
        elif field_type == "boolean":
            example[key] = True
        elif field_type == "string":
            example[key] = "done"
        elif field_type == "object":
            example[key] = {}
        else:
            example[key] = None
    return example


def unwrap_schema_shaped_finish(parsed: dict[str, Any]) -> dict[str, Any]:
    """If the model returned a JSON Schema wrapper, extract values from properties."""
    if parsed.get("type") != "object" or "properties" not in parsed:
        return parsed

    props = parsed["properties"]
    if not isinstance(props, dict):
        return parsed

    if _properties_look_like_schema_defs(props):
        return parsed

    return dict(props)


def is_valid_finish_output(output: dict[str, Any], finish_schema: dict[str, Any]) -> bool:
    required = finish_schema.get("required", [])
    if not required:
        return bool(output)

    if set(output.keys()) == {"error"}:
        return False

    return all(key in output for key in required)


def parse_finish_output(content: str) -> dict[str, Any]:
    text = strip_markdown_json(content)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"summary": content}

    if not isinstance(parsed, dict):
        return {"summary": content}

    return unwrap_schema_shaped_finish(parsed)
