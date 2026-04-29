DEFINITION = {
    "name": "code_compliance_scan_full",
    "steps": [
        {
            "id": "pull",
            "type": "hook.in",
            "with": {"repo_url": "{{ inputs.repo_url }}"},
        },
        {
            "id": "retrieve_controls",
            "type": "corpus.query",
            "depends_on": ["pull"],
            "with": {
                "query": "recipient domain validation for email tools",
                "corpora": ["iso_42001", "internal_data_min"],
            },
        },
        {
            "id": "scan",
            "type": "agent",
            "depends_on": ["retrieve_controls"],
            "with": {"files": "{{ steps.pull.outputs.files }}"},
        },
        {
            "id": "emit",
            "type": "finding.emit",
            "depends_on": ["scan"],
            "with": {"findings": "{{ steps.scan.outputs.findings }}"},
        },
        {
            "id": "propose",
            "type": "change.propose",
            "depends_on": ["emit"],
            "with": {
                "finding": "{{ steps.emit.outputs.emitted.0 }}",
                "target": "tools.py",
            },
        },
        {
            "id": "policy_gate",
            "type": "gate.policy",
            "depends_on": ["propose"],
            "with": {"severity": "high"},
        },
        {
            "id": "human_gate",
            "type": "gate.human",
            "depends_on": ["policy_gate"],
            "with": {
                "subject": "{{ steps.propose.outputs.finding_title }}",
                "role_required": "grc_reviewer",
                "approved": "{{ inputs.approved }}",
            },
        },
        {
            "id": "open_pr",
            "type": "hook.out",
            "depends_on": ["human_gate"],
            "with": {
                "hook_id": "github_stub",
                "operation": "open_pr",
                "payload": "{{ steps.propose.outputs }}",
            },
        },
    ],
}
