DEFINITION = {
    "name": "code_compliance_scan",
    "steps": [
        {
            "id": "pull",
            "type": "hook.in",
            "with": {"repo_url": "{{ inputs.repo_url }}"},
        },
        {
            "id": "scan",
            "type": "agent",
            "depends_on": ["pull"],
            "with": {"files": "{{ steps.pull.outputs.files }}"},
        },
        {
            "id": "emit",
            "type": "finding.emit",
            "depends_on": ["scan"],
            "with": {"findings": "{{ steps.scan.outputs.findings }}"},
        },
    ],
}
