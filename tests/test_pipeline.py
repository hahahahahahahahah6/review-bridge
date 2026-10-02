"""Tests for the secretary-loop pipeline (mock AI, no network)."""
import json
import os

from review_bridge.models import Review
from review_bridge.ollama import MockOllamaClient
from review_bridge.pipeline import (
    build_digest,
    draft_reply,
    extract_json,
    summarize_items,
    translate_review,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "real_reviews.json")


def real_reviews():
    from review_bridge.serpapi import parse_serpapi_payload

    with open(FIXTURE, encoding="utf-8") as f:
        return parse_serpapi_payload(json.load(f))


def test_real_fixture_parses():
    reviews = real_reviews()
    assert len(reviews) == 8
    assert sum(1 for r in reviews if r.needs_attention) == 2  # Zoe 2★, Alice 1★


def test_end_to_end_secretary_loop():
    client = MockOllamaClient()
    digest = build_digest(real_reviews(), client)

    # 1. 简报
    assert digest["avg_rating"] == 4.0  # (5+2+5+1+5+5+5+4)/8
    assert digest["rating_dist"] == {5: 5, 4: 1, 3: 0, 2: 1, 1: 1}
    assert digest["summary"]
    assert digest["good_themes"] and digest["bad_themes"]

    # 2. 预警
    assert digest["attention_count"] == 2

    # 3. 代笔: English reply + Chinese explanation of what it says
    assert set(digest["replies"]) == {
        i for i, r in enumerate(real_reviews()) if r.needs_attention
    }
    for reply in digest["replies"].values():
        assert reply["en_reply"] and reply["zh_explanation"]
        assert "zh_reply" not in reply  # old shape is gone

    # every review got a translation (plumbing), none crashed
    assert len(digest["items"]) == 8
    assert all(it.zh_text for it in digest["items"])


def test_translate_falls_back_to_original_on_garbage():
    class Garbage(MockOllamaClient):
        def generate(self, prompt):
            return "sorry, no json here at all"

    r = Review(author="X", rating=5, date="", text="Great noodles!")
    item = translate_review(r, Garbage())
    assert item.zh_text == "Great noodles!"  # original preserved
    assert item.topics == []


def test_empty_reviews_digest():
    digest = build_digest([], MockOllamaClient())
    assert digest["items"] == []
    assert digest["avg_rating"] == 0.0
    assert digest["attention_count"] == 0
    assert digest["replies"] == {}


def test_draft_reply_shape():
    client = MockOllamaClient()
    r = Review(author="Zoe Z.", rating=2, date="", text="Portion too small.")
    reply = draft_reply(
        translate_review(r, client), client
    )
    assert set(reply) == {"en_reply", "zh_explanation"}


class TestExtractJson:
    def test_plain(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_fences(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_chatter(self):
        assert extract_json('Here you go: {"a": 1} hope it helps') == {"a": 1}

    def test_nested_braces_in_strings(self):
        assert extract_json('{"zh": "用了 {大括号} 没问题", "t": []}')["zh"].startswith("用了")

    def test_garbage(self):
        assert extract_json("no json at all") == {}
        assert extract_json("") == {}
        assert extract_json('{"unclosed": ') == {}

    def test_non_dict(self):
        assert extract_json("[1, 2, 3]") == {}
