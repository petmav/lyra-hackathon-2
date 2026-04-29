from typing import Any


def query_corpus(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", ""))
    corpora = args.get("corpora", [])
    chunks = [
        {
            "corpus_id": corpus_id,
            "citation_path": "paragraph 1",
            "text": f"{corpus_id} requires controls relevant to: {query}",
            "score": 0.88,
        }
        for corpus_id in corpora
    ]
    return {"query": query, "chunks": chunks}
