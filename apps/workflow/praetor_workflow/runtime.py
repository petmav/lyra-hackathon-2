from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from praetor_workflow.dag import WorkflowDefinition, topo_sort
from praetor_workflow.executors import (
    AwaitingHumanApproval,
    call_hook_in,
    call_hook_out,
    emit_finding,
    gate_human,
    gate_policy,
    propose_change,
    query_corpus,
    run_agent,
    transform,
)
from praetor_workflow.templating import render


@dataclass
class StepResult:
    step_id: str
    step_type: str
    status: str
    outputs: dict[str, Any]


@dataclass
class WorkflowResult:
    run_id: str
    status: str
    steps: list[StepResult] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)


EXECUTORS = {
    "hook.in": call_hook_in,
    "hook.out": call_hook_out,
    "agent": run_agent,
    "corpus.query": query_corpus,
    "finding.emit": emit_finding,
    "gate.policy": gate_policy,
    "gate.human": gate_human,
    "change.propose": propose_change,
    "transform": transform,
}


def run(definition: WorkflowDefinition, inputs: dict[str, Any]) -> WorkflowResult:
    context: dict[str, Any] = {"inputs": inputs, "steps": {}}
    result = WorkflowResult(run_id=f"wfr_{uuid4().hex[:12]}", status="running")

    for step in topo_sort(definition):
        executor = EXECUTORS[step.type]
        args = render(step.with_, context)
        try:
            outputs = executor(args)
            status = "succeeded"
        except AwaitingHumanApproval as exc:
            outputs = exc.approval
            status = "awaiting_approval"

        context["steps"][step.id] = {"outputs": outputs, "status": status}
        result.steps.append(
            StepResult(
                step_id=step.id,
                step_type=step.type,
                status=status,
                outputs=outputs,
            )
        )

        if status == "awaiting_approval":
            result.status = "awaiting_approval"
            result.outputs = outputs
            return result

    result.status = "succeeded"
    result.outputs = result.steps[-1].outputs if result.steps else {}
    return result
