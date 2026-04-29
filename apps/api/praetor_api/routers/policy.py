from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from praetor_api.services.policy_hot import evaluate

router = APIRouter(tags=["policy"])


class PolicyEvaluateRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluateResponse(BaseModel):
    allowed: bool
    outcome: str
    rationale: str
    latency_ms: float
    input_hash: str


@router.post("/policy:evaluate", response_model=PolicyEvaluateResponse)
@router.post("/policy/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_policy(request: PolicyEvaluateRequest) -> PolicyEvaluateResponse:
    result = evaluate(request.input)
    return PolicyEvaluateResponse(
        allowed=result.allowed,
        outcome=result.outcome,
        rationale=result.rationale,
        latency_ms=result.latency_ms,
        input_hash=result.input_hash,
    )
