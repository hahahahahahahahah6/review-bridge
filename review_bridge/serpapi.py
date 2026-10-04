"""Fetch Google Maps reviews through SerpApi (stdlib only).

Two entry points:
  fetch_reviews(query=..., place_id=...)  -> live SerpApi call, needs SERPAPI_KEY
  parse_serpapi_payload(data)             -> pure parser, used by tests and --mock
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .models import Review

ENGINE_URL = "https://serpapi.com/search.json"


class ReviewBridgeError(Exception):
    """User-facing error with an actionable message."""


def _get(engine: str, params: dict, api_key: str, timeout: int = 30) -> dict:
    q = {"engine": engine, "api_key": api_key}
    q.update(params)
    url = ENGINE_URL + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "review-bridge/0.1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:
            detail = ""
        raise ReviewBridgeError(f"SerpApi HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ReviewBridgeError(f"SerpApi unreachable: {exc.reason}") from exc


def _coerce_rating(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_serpapi_payload(data: dict) -> list[Review]:
    """Parse a google_maps_reviews SerpApi payload into Reviews. Skips junk."""
    out: list[Review] = []
    reviews = data.get("reviews") if isinstance(data, dict) else None
    for raw in reviews or []:
        if not isinstance(raw, dict):
            continue
        user = raw.get("user") or {}
        text = raw.get("snippet") or raw.get("text") or raw.get("review_text") or ""
        text = str(text).strip()
        if not text:
            continue
        out.append(
            Review(
                author=str(user.get("name") or "匿名"),
                rating=_coerce_rating(raw.get("rating")),
                date=str(raw.get("date") or ""),
                text=text,
            )
        )
    return out


def resolve_place_id(query: str, api_key: str) -> str:
    """Turn a restaurant name into a SerpApi place_id via google_maps search."""
    data = _get("google_maps", {"q": query, "type": "search"}, api_key)
    pr = data.get("place_results")
    # 精确命中时 place_results 是单个 dict，不是 list
    if isinstance(pr, dict) and pr.get("place_id"):
        return str(pr["place_id"])
    results: list = []
    if isinstance(pr, list):
        results.extend(pr)
    lr = data.get("local_results")
    if isinstance(lr, list):
        results.extend(lr)
    if not results or not isinstance(results[0], dict):
        raise ReviewBridgeError(f"No place found for query: {query!r}")
    place_id = results[0].get("place_id")
    if not place_id:
        raise ReviewBridgeError(f"Search result for {query!r} had no place_id")
    return str(place_id)


def fetch_reviews(
    query: str | None = None,
    place_id: str | None = None,
    api_key: str | None = None,
) -> list[Review]:
    api_key = api_key or os.environ.get("SERPAPI_KEY")
    if not api_key:
        raise ReviewBridgeError(
            "SERPAPI_KEY is not set. Set the env var, pass --api-key, "
            "or skip the API entirely with paste mode: review-bridge paste"
        )
    if not place_id:
        if not query:
            raise ReviewBridgeError("Need --query or --place-id to fetch reviews")
        place_id = resolve_place_id(query, api_key)
    data = _get("google_maps_reviews", {"place_id": place_id}, api_key)
    if data.get("error"):
        raise ReviewBridgeError(f"SerpApi error: {data['error']}")
    return parse_serpapi_payload(data)
