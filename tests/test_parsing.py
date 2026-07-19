import pytest

from parsing import extract_list, extract_object, parse_json


def test_plain_list():
    assert extract_list('[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]


def test_list_wrapped_in_known_key():
    assert extract_list('{"news": [{"a": 1}]}') == [{"a": 1}]


def test_list_wrapped_in_unknown_key():
    assert extract_list('{"whatever": [{"a": 1}]}') == [{"a": 1}]


def test_list_from_markdown_fence():
    text = "Here you go:\n```json\n[{\"a\": 1}]\n```\nThanks!"
    assert extract_list(text) == [{"a": 1}]


def test_object_with_leading_prose():
    text = 'Sure! {"period_start": "2026-06-01", "x": 2} done'
    assert extract_object(text)["x"] == 2


def test_braces_inside_strings_handled():
    text = '{"summary": "rates rose by {a lot}", "n": 1}'
    assert extract_object(text) == {"summary": "rates rose by {a lot}", "n": 1}


def test_single_object_to_list():
    assert extract_list('{"title": "x"}') == [{"title": "x"}]


def test_truncated_array_salvaged():
    # Last object is cut off (simulates a token-truncated grounding response).
    text = '{"news": [{"a": 1}, {"b": 2}, {"c":'
    assert extract_list(text) == [{"a": 1}, {"b": 2}]


def test_invalid_raises():
    with pytest.raises(ValueError):
        parse_json("no json at all here")
