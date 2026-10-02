"""Tests for paste-mode parsing."""
from review_bridge.paste import parse_pasted


def test_basic_blocks():
    reviews = parse_pasted(
        "author: Jane D.\n"
        "rating: 2\n"
        "date: 2026-09-20\n"
        "The noodles were cold.\n"
        "---\n"
        "author: Bob\n"
        "rating: 5\n"
        "Best beef noodle soup ever!\n"
    )
    assert len(reviews) == 2
    assert reviews[0].author == "Jane D."
    assert reviews[0].rating == 2.0
    assert reviews[0].date == "2026-09-20"
    assert reviews[0].text == "The noodles were cold."
    assert reviews[0].needs_attention
    assert reviews[1].author == "Bob"
    assert not reviews[1].needs_attention


def test_defaults_and_bad_rating():
    (r,) = parse_pasted("rating: not-a-number\nJust some text here")
    assert r.author == "匿名"
    assert r.rating == 5.0  # default kept when unparseable
    assert r.text == "Just some text here"


def test_empty_and_header_only_blocks_skipped():
    assert parse_pasted("") == []
    assert parse_pasted("---\n---\n") == []
    assert parse_pasted("author: Nobody\nrating: 5\n") == []  # no body text


def test_multiline_body_preserved():
    (r,) = parse_pasted("line one\nline two\nline three")
    assert r.text == "line one\nline two\nline three"
