from __future__ import annotations

from recall.contracts import canonical_json_bytes, content_hash


def test_canonical_json_is_sorted_compact_and_utf8() -> None:
    encoded = canonical_json_bytes({"z": 2, "message": "kanıt", "a": 1})

    assert encoded == '{"a":1,"message":"kanıt","z":2}'.encode()


def test_content_hash_omits_only_the_top_level_hash() -> None:
    first = {
        "schema_name": "FailureReceipt",
        "content_hash": "0" * 64,
        "details": {"observed_hash": "1" * 64},
    }
    reordered = {
        "details": {"observed_hash": "1" * 64},
        "content_hash": "f" * 64,
        "schema_name": "FailureReceipt",
    }

    assert content_hash(first) == content_hash(reordered)
    assert content_hash(first) != content_hash(
        {**first, "details": {"observed_hash": "2" * 64}}
    )
