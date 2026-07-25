from src.state.fingerprints import fingerprint_payload


def test_fingerprint_is_stable_across_dictionary_order() -> None:
    assert fingerprint_payload({"b": 2, "a": 1}) == fingerprint_payload({"a": 1, "b": 2})
    assert len(fingerprint_payload({"a": 1})) == 64
