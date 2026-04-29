from praetor_api.hashchain import ZERO_HASH, compute


def test_compute_starts_from_zero_hash() -> None:
    prev, self_hash = compute(None, {"b": 2, "a": 1})

    assert prev == ZERO_HASH
    assert len(self_hash) == 64


def test_second_event_links_to_first() -> None:
    _, first = compute(None, {"type": "agent.tool.called"})
    prev, second = compute(first, {"type": "agent.tool.refused"})

    assert prev == first
    assert second != first
