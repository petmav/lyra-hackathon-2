DEFINITION = {
    "name": "policy_gap_analysis",
    "steps": [
        {
            "id": "retrieve_controls",
            "type": "corpus.query",
            "with": {"query": "policy gap controls", "corpora": ["iso_42001"]},
        },
        {
            "id": "summarize",
            "type": "transform",
            "depends_on": ["retrieve_controls"],
            "with": {"summary": "deterministic policy gap summary"},
        },
    ],
}
