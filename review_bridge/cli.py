"""review-bridge CLI.

Modes:
  fetch  --query "Restaurant Name" | --place-id ...   pull Google Maps reviews via SerpApi
  paste  [--file reviews.txt]                        read reviews from stdin/file, no API key
  serve  [--port 8080]                               Chinese web UI for the family

Global flags: --mock (canned AI + fixture reviews, no network/AI needed),
--model, --ollama-host, --api-key.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .ollama import MockOllamaClient, OllamaClient
from .paste import parse_pasted
from .pipeline import build_digest
from .serpapi import ReviewBridgeError, fetch_reviews, parse_serpapi_payload
from .server import Bridge, render_page, serve

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                       "serpapi_reviews.json")


def _client(args):
    if args.mock:
        return MockOllamaClient(model=args.model)
    return OllamaClient(model=args.model, host=args.ollama_host)


def _mock_reviews():
    with open(FIXTURE, encoding="utf-8") as f:
        return parse_serpapi_payload(json.load(f))


def cmd_fetch(args) -> int:
    try:
        if args.mock:
            reviews = _mock_reviews()
        else:
            reviews = fetch_reviews(
                query=args.query, place_id=args.place_id, api_key=args.api_key
            )
    except ReviewBridgeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    digest = build_digest(reviews, _client(args))
    print(f"📊 简报：{len(reviews)} 条评价，平均 {digest['avg_rating']} 星。")
    print("总结：" + digest["summary"])
    if digest["good_themes"]:
        print("大家最夸的：" + "、".join(digest["good_themes"]))
    if digest["bad_themes"]:
        print("被吐槽最多的：" + "、".join(digest["bad_themes"]))
    if digest["attention_count"]:
        print(f"\n🚨 差评预警：{digest['attention_count']} 条需要回复：")
    for idx, it in enumerate(digest["items"]):
        if it.needs_attention:
            print(f"\n[{it.review.rating:g}星] {it.review.author}: {it.zh_text}")
            reply = digest["replies"].get(idx, {})
            print("  代笔英文回复：" + reply.get("en_reply", ""))
            print("  回复的意思：" + reply.get("zh_explanation", ""))
    return 0


def cmd_paste(args) -> int:
    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    reviews = parse_pasted(text)
    if not reviews:
        print("没有解析到评价，请检查格式。", file=sys.stderr)
        return 1
    digest = build_digest(reviews, _client(args))
    print(render_page(digest, len(reviews)))
    return 0


def cmd_serve(args) -> int:
    client = _client(args)
    fetcher = None
    reviews = []
    if args.mock:
        reviews = _mock_reviews()
    elif args.query or args.place_id:
        def fetcher():
            return fetch_reviews(
                query=args.query, place_id=args.place_id, api_key=args.api_key
            )
        try:
            reviews = fetcher()
        except ReviewBridgeError as exc:
            print(f"提醒：{exc}（可先用粘贴模式）")
    bridge = Bridge(reviews, client, fetcher)
    serve(bridge, args.port)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="review-bridge",
        description="面馆评价小秘书：盯着 Google 地图评价 → 中文简报 → 差评预警 → 代笔英文回复",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--mock", action="store_true",
                    help="模拟模式：用内置假数据，不连 SerpApi 也不连 Ollama")
    ap.add_argument("--model", default="gemma3:4b", help="Ollama 模型名")
    ap.add_argument("--ollama-host", default="http://localhost:11434")
    ap.add_argument("--api-key", default=None, help="SerpApi key（默认读 SERPAPI_KEY）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="从 Google Maps 拉取评价并打印中文摘要")
    f.add_argument("--query", help="餐馆名，如 'Noodle House Arcadia'")
    f.add_argument("--place-id", help="SerpApi place_id（比名字更准）")
    f.set_defaults(func=cmd_fetch)

    p = sub.add_parser("paste", help="从 stdin/文件粘贴评价文本")
    p.add_argument("--file", help="评价文本文件（不给则从 stdin 读）")
    p.set_defaults(func=cmd_paste)

    s = sub.add_parser("serve", help="启动中文网页（手机可访问）")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--query", help="启动时预拉取该餐馆的评价")
    s.add_argument("--place-id")
    s.set_defaults(func=cmd_serve)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
