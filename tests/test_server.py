"""Tests for the Chinese web UI rendering."""
import json
import os

from review_bridge.ollama import MockOllamaClient
from review_bridge.pipeline import build_digest
from review_bridge.serpapi import parse_serpapi_payload
from review_bridge.server import Bridge, render_page

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "real_reviews.json")


def digest():
    with open(FIXTURE, encoding="utf-8") as f:
        reviews = parse_serpapi_payload(json.load(f))
    return build_digest(reviews, MockOllamaClient())


def test_page_sells_the_loop_not_translation():
    page = render_page(digest(), 8)
    assert "小秘书" in page
    assert "今日简报" in page
    assert "差评预警" in page
    assert "代笔回复" in page
    # avg rating shown
    assert "4.0" in page
    # reply draft: English reply + Chinese explanation of what it says
    assert "MOCK EN REPLY" in page
    assert "这条回复的意思是" in page


def test_html_escaping():
    from review_bridge.models import Review

    evil = Review(author="<script>alert(1)</script>", rating=1, date="",
                  text="<b>bold</b>")
    d = build_digest([evil], MockOllamaClient())
    page = render_page(d, 1)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_empty_state():
    page = render_page(None, 0)
    assert "还没有评价数据" in page


def test_bridge_refresh_without_fetcher():
    bridge = Bridge([], MockOllamaClient())
    msg = bridge.refresh()
    assert "粘贴" in msg  # helpful guidance, no crash


def test_bridge_add_pasted():
    bridge = Bridge([], MockOllamaClient())
    msg = bridge.add_pasted("author: A\nrating: 1\nTerrible.")
    assert "1 条" in msg
    assert bridge.digest["attention_count"] == 1
