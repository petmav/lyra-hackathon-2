import re
from typing import Any

TOKEN_RE = re.compile(r"{{\s*([^}]+?)\s*}}")


def resolve_path(context: dict[str, Any], path: str) -> Any:
    value: Any = context
    for part in path.split("."):
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list):
            value = value[int(part)]
        else:
            value = getattr(value, part)
    return value


def render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: render(child, context) for key, child in value.items()}
    if isinstance(value, list):
        return [render(child, context) for child in value]
    if not isinstance(value, str):
        return value

    match = TOKEN_RE.fullmatch(value)
    if match:
        return resolve_path(context, match.group(1))

    return TOKEN_RE.sub(lambda token: str(resolve_path(context, token.group(1))), value)
