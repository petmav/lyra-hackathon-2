DEFINITION = {
    "name": "ai_system_intake",
    "steps": [
        {
            "id": "classify",
            "type": "transform",
            "with": {"asset_type": "ai_system", "risk_tier": "L2"},
        },
        {
            "id": "policy_gate",
            "type": "gate.policy",
            "depends_on": ["classify"],
            "with": {"severity": "medium"},
        },
    ],
}
