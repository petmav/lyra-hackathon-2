DEFINITION = {
    "name": "vendor_risk_review",
    "steps": [
        {
            "id": "retrieve_policy",
            "type": "corpus.query",
            "with": {"query": "vendor AI risk review", "corpora": ["internal_data_min"]},
        },
        {
            "id": "emit",
            "type": "finding.emit",
            "depends_on": ["retrieve_policy"],
            "with": {"findings": []},
        },
    ],
}
