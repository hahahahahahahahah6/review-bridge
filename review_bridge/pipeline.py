"""The review -> Chinese digest pipeline.

Each review is translated to Simplified Chinese with topic keywords, the whole
set is summarized, and 1-2 star reviews get bilingual reply drafts.
All model I/O goes through defensive JSON extraction: model output is
unreliable, the pipeline must never crash on it.
"""
from __future__ import annotations

import json
import re

from .models import DigestItem, Review
from .ollama import OllamaClient

TASK_TRANSLATE = "[TASK:translate]"
TASK_SUMMARIZE = "[TASK:summarize]"
TASK_REPLY = "[TASK:reply]"


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of messy model output.

    Handles markdown fences, leading chatter, and trailing junk.
    Returns {} when nothing parseable is found.
    """
    if not text:
        return {}
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    if start < 0:
        return {}
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(cleaned[start : i + 1])
                        return parsed if isinstance(parsed, dict) else {}
                    except json.JSONDecodeError:
                        return {}
    return {}


def _as_list(value) -> list:
    return [str(v) for v in value] if isinstance(value, list) else []


def translate_review(review: Review, client: OllamaClient) -> DigestItem:
    prompt = (
        f"{TASK_TRANSLATE}\n"
        "Translate the following restaurant review to Simplified Chinese. "
        "Also list 1-3 topic keywords in Chinese (e.g. 牛肉面, 服务, 等位). "
        'Reply with ONLY JSON: {"zh": "...", "topics": ["..."]}\n'
        f"Review (rating {review.rating:g}/5 by {review.author} on {review.date}):\n"
        f"{review.text}"
    )
    data = extract_json(client.generate(prompt))
    zh = str(data.get("zh") or "").strip() or review.text  # fall back to original
    return DigestItem(review=review, zh_text=zh, topics=_as_list(data.get("topics")))


def summarize_items(items: list[DigestItem], client: OllamaClient) -> dict:
    lines = []
    for it in items:
        lines.append(f"- [{it.review.rating:g}星] {it.zh_text} (主题: {'、'.join(it.topics)})")
    prompt = (
        f"{TASK_SUMMARIZE}\n"
        "You are the review secretary for a Chinese noodle restaurant. The owners "
        "read Simplified Chinese and never check Google Maps themselves. "
        "Write a 2-3 sentence Chinese briefing: overall vibe, then name the "
        "SPECIFIC dishes/topics customers praise most and the SPECIFIC things "
        "they complain about most (quote dish names like 牛肉面, 重庆小面, 服务, 等位). "
        'Reply with ONLY JSON: {"summary": "...", "good_themes": ["..."], "bad_themes": ["..."]}\n'
        + "\n".join(lines)
    )
    data = extract_json(client.generate(prompt))
    return {
        "summary": str(data.get("summary") or "暂无总结。"),
        "good_themes": _as_list(data.get("good_themes")),
        "bad_themes": _as_list(data.get("bad_themes")),
    }


def draft_reply(item: DigestItem, client: OllamaClient) -> dict:
    """Draft the public English reply + a Chinese explanation for the owners.

    The owners don't read English, so the Chinese text explains what the
    English reply says and why — it's the briefing, not a second reply.
    """
    prompt = (
        f"{TASK_REPLY}\n"
        "Write a polite public reply from a noodle restaurant owner to this "
        f"{item.review.rating:g}-star Google Maps review. "
        "The reply will be posted publicly in ENGLISH: make it sound natural and "
        "warm, reference the customer's actual complaint specifically, apologize "
        "briefly, state one concrete improvement, invite them back. "
        "Then, in Simplified Chinese, explain to the owners (who don't read "
        "English) what the English reply says and why it says it, in 2-3 sentences. "
        'Reply with ONLY JSON: {"en_reply": "...", "zh_explanation": "..."}\n'
        f"Original review: {item.review.text}\n"
        f"Chinese translation: {item.zh_text}"
    )
    data = extract_json(client.generate(prompt))
    return {
        "en_reply": str(data.get("en_reply") or "(no suggestion)"),
        "zh_explanation": str(data.get("zh_explanation") or "（暂无说明）"),
    }


def build_digest(reviews: list[Review], client: OllamaClient) -> dict:
    """Full secretary loop: brief -> alert -> ghostwrite. Never raises on model weirdness."""
    items = [translate_review(r, client) for r in reviews]
    summary = summarize_items(items, client) if items else {
        "summary": "还没有评价。",
        "good_themes": [],
        "bad_themes": [],
    }
    replies = {}
    for idx, it in enumerate(items):
        if it.needs_attention:
            replies[idx] = draft_reply(it, client)
    rated = [r.rating for r in reviews if r.rating > 0]
    return {
        "items": items,
        "summary": summary["summary"],
        "good_themes": summary["good_themes"],
        "bad_themes": summary["bad_themes"],
        "replies": replies,
        "attention_count": sum(1 for it in items if it.needs_attention),
        "avg_rating": round(sum(rated) / len(rated), 1) if rated else 0.0,
        "rating_dist": {
            s: sum(1 for r in rated if int(r) == s) for s in (5, 4, 3, 2, 1)
        },
    }
