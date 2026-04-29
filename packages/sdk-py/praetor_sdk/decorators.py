from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

from praetor_sdk.transport import PolicyDenied, PraetorClient

F = TypeVar("F", bound=Callable[..., Any])


def governed(tool_name: str | None = None) -> Callable[[F], F]:
    def decorate(func: F) -> F:
        name = tool_name or func.__name__

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = PraetorClient()
            decision = client.evaluate_policy({"tool": name, "args": kwargs})
            if not decision.get("allowed", False):
                raise PolicyDenied(str(decision.get("rationale", "policy denied tool call")))
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorate
