import re

_PATH_RE = re.compile(
    r"[\w./-]+\.(?:html|js|css|py|ts|tsx|json|md|txt|jsx|vue)\b"
)


def extract_paths(text: str) -> list[str]:
    return list(dict.fromkeys(_PATH_RE.findall(text)))


def resolve_paths_for_goal(goal: str, extra: list[str] | None = None) -> list[str]:
    extra = extra or []
    return list(dict.fromkeys(extract_paths(goal) + list(extra)))
