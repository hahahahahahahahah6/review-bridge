"""Tests for the SerpApi fetch/parse layer."""
import json
import os

import pytest

from review_bridge.models import Review
from review_bridge.serpapi import (
    ReviewBridgeError,
    fetch_reviews,
    parse_serpapi_payload,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "serpapi_reviews.json")


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_parse_fixture():
    reviews = parse_serpapi_payload(load_fixture())
    # 4 real reviews; the empty-snippet one and the junk entry are skipped
    assert len(reviews) == 4
    assert reviews[0].author == "Daniel K."
    assert reviews[0].rating == 5.0
    assert "beef noodle" in reviews[0].text
    assert reviews[2].needs_attention  # 2 stars
    assert reviews[3].needs_attention  # 1 star
    assert not reviews[0].needs_attention


def test_parse_handles_weird_shapes():
    assert parse_serpapi_payload({}) == []
    assert parse_serpapi_payload({"reviews": None}) == []
    assert parse_serpapi_payload({"reviews": ["nope", 42, None]}) == []
    # rating as string coerces; missing user falls back to 匿名
    (r,) = parse_serpapi_payload(
        {"reviews": [{"rating": "4", "snippet": "ok", "date": "2026-01-01"}]}
    )
    assert r.rating == 4.0
    assert r.author == "匿名"
    # unparseable rating -> 0.0, which is NOT flagged as needing attention
    (r2,) = parse_serpapi_payload(
        {"reviews": [{"rating": "n/a", "snippet": "meh"}]}
    )
    assert r2.rating == 0.0
    assert not r2.needs_attention


def test_fetch_requires_api_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    with pytest.raises(ReviewBridgeError, match="SERPAPI_KEY"):
        fetch_reviews(query="Noodle House")


def test_fetch_needs_query_or_place_id(monkeypatch):
    monkeypatch.setenv("SERPAPI_KEY", "fake")
    with pytest.raises(ReviewBridgeError, match="--query or --place-id"):
        fetch_reviews()


def test_fetch_uses_fixture_shape(monkeypatch):
    """fetch_reviews wires query -> place_id -> reviews parsing."""
    import review_bridge.serpapi as mod

    calls = []

    def fake_get(engine, params, api_key, timeout=30):
        calls.append(engine)
        if engine == "google_maps":
            return {"place_results": [{"place_id": "abc123"}]}
        return load_fixture()

    monkeypatch.setattr(mod, "_get", fake_get)
    reviews = fetch_reviews(query="Noodle House", api_key="fake")
    assert calls == ["google_maps", "google_maps_reviews"]
    assert len(reviews) == 4
    assert all(isinstance(r, Review) for r in reviews)


def test_serpapi_error_payload(monkeypatch):
    import review_bridge.serpapi as mod

    def fake_get(engine, params, api_key, timeout=30):
        return {"error": "Invalid API key"}

    monkeypatch.setattr(mod, "_get", fake_get)
    with pytest.raises(ReviewBridgeError, match="Invalid API key"):
        fetch_reviews(place_id="abc", api_key="fake")
