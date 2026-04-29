DEFINITION = {
    "name": "evidence_collection",
    "steps": [
        {
            "id": "read_files",
            "type": "hook.in",
            "with": {"repo_url": "stub://evidence"},
        },
        {
            "id": "emit",
            "type": "finding.emit",
            "depends_on": ["read_files"],
            "with": {"findings": []},
        },
    ],
}
