from fastapi.testclient import TestClient

from praetor_api.main import app

HEADERS = {"Authorization": "Bearer dev"}


def test_corpus_ingest_and_search() -> None:
    client = TestClient(app)
    corpus = client.get("/corpora/internal_data_min", headers=HEADERS)
    assert corpus.status_code == 200
    assert corpus.json()["urn"] == "urn:praetor:corpus:internal_data_min"

    ingest = client.post(
        "/corpora/internal_data_min/documents:ingest",
        headers=HEADERS,
        json={
            "title": "Policy",
            "source_uri": "seed://policy",
            "text": "Email tools must validate recipient domains.\n\nOther text.",
        },
    )
    assert ingest.status_code == 200
    assert ingest.json()["chunk_count"] == 2

    search = client.post(
        "/corpora/internal_data_min:search",
        headers=HEADERS,
        json={"query": "recipient domains", "k": 3},
    )
    assert search.status_code == 200
    assert search.json()[0]["score"] > 0

    documents = client.get("/corpora/internal_data_min/documents", headers=HEADERS)
    assert documents.status_code == 200


def test_hook_test_endpoint() -> None:
    response = TestClient(app).post("/hooks/github_stub:test", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["ok"] is True
