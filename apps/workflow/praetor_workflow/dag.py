from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Step:
    id: str
    type: str
    with_: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    steps: tuple[Step, ...]


def parse_definition(raw: dict[str, Any]) -> WorkflowDefinition:
    steps = tuple(
        Step(
            id=item["id"],
            type=item["type"],
            with_=item.get("with", {}),
            depends_on=tuple(item.get("depends_on", ())),
        )
        for item in raw["steps"]
    )
    return WorkflowDefinition(name=raw["name"], steps=steps)


def topo_sort(definition: WorkflowDefinition) -> list[Step]:
    by_id = {step.id: step for step in definition.steps}
    visited: set[str] = set()
    visiting: set[str] = set()
    ordered: list[Step] = []

    def visit(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            raise ValueError(f"workflow DAG contains a cycle at {step_id}")
        if step_id not in by_id:
            raise ValueError(f"workflow references unknown step {step_id}")

        visiting.add(step_id)
        for dep in by_id[step_id].depends_on:
            visit(dep)
        visiting.remove(step_id)
        visited.add(step_id)
        ordered.append(by_id[step_id])

    for step in definition.steps:
        visit(step.id)

    return ordered
