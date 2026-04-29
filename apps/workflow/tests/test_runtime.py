from praetor_workflow.dag import parse_definition, topo_sort
from praetor_workflow.runtime import run
from templates.code_compliance_scan import DEFINITION
from templates.code_compliance_scan_full import DEFINITION as FULL_DEFINITION


def test_topo_sort_orders_dependencies() -> None:
    definition = parse_definition(DEFINITION)

    assert [step.id for step in topo_sort(definition)] == ["pull", "scan", "emit"]


def test_code_compliance_scan_emits_finding() -> None:
    definition = parse_definition(DEFINITION)
    result = run(definition, {"repo_url": "stub://support-bot"})

    assert result.status == "succeeded"
    assert result.outputs["count"] == 1
    assert result.outputs["emitted"][0]["severity"] == "high"


def test_full_scan_pauses_for_human_approval() -> None:
    definition = parse_definition(FULL_DEFINITION)
    result = run(definition, {"repo_url": "stub://support-bot", "approved": False})

    assert result.status == "awaiting_approval"
    assert result.steps[-1].step_id == "human_gate"
    assert result.outputs["role_required"] == "grc_reviewer"


def test_full_scan_opens_pr_when_approved() -> None:
    definition = parse_definition(FULL_DEFINITION)
    result = run(definition, {"repo_url": "stub://support-bot", "approved": True})

    assert result.status == "succeeded"
    assert result.steps[-1].step_id == "open_pr"
    assert result.outputs["pr_url"].endswith("/pull/42")


def test_every_planned_demo_template_parses() -> None:
    from templates.ai_system_intake import DEFINITION as ai_system_intake
    from templates.evidence_collection import DEFINITION as evidence_collection
    from templates.policy_gap_analysis import DEFINITION as policy_gap_analysis
    from templates.vendor_risk_review import DEFINITION as vendor_risk_review

    for raw in [ai_system_intake, evidence_collection, policy_gap_analysis, vendor_risk_review]:
        definition = parse_definition(raw)
        assert topo_sort(definition)
