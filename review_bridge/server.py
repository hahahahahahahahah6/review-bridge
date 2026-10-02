"""Phone-friendly Simplified-Chinese web UI (stdlib http.server only)."""
from __future__ import annotations

import html
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .models import Review
from .paste import parse_pasted
from .pipeline import build_digest

PAGE_CSS = """
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
margin:0;padding:16px;background:#faf7f2;color:#333;max-width:720px}
h1{font-size:22px}h2{font-size:18px;margin-top:28px;border-bottom:2px solid #d94f30;padding-bottom:6px}
.card{background:#fff;border-radius:10px;padding:12px;margin:10px 0;box-shadow:0 1px 3px #0001}
.alert{border-left:5px solid #d94f30}
.stars{color:#e8a13a;font-weight:bold}
.meta{color:#888;font-size:13px}
.reply{background:#f4f8ff;border-radius:8px;padding:10px;margin-top:8px;font-size:14px}
textarea{width:100%;height:160px;font-size:15px;border-radius:8px;padding:8px;box-sizing:border-box}
button,.btn{background:#d94f30;color:#fff;border:0;border-radius:8px;
padding:12px 20px;font-size:16px;margin:8px 4px 8px 0;cursor:pointer}
.tag{display:inline-block;background:#eee;border-radius:12px;padding:2px 10px;margin:2px;font-size:13px}
.themes{margin:6px 0}
"""


def _esc(s: str) -> str:
    return html.escape(s or "")


def render_page(digest: dict | None, review_count: int = 0) -> str:
    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<style>{PAGE_CSS}</style><title>面馆评价小秘书</title></head><body>",
        "<h1>🍜 面馆评价小秘书</h1>",
        "<p class='meta'>盯着评价 → 中文简报 → 差评预警 → 代笔回复。不用再看英文了。</p>",
    ]
    if not digest or not digest["items"]:
        parts.append(
            "<div class='card'>还没有评价数据。点下面 <b>粘贴评价</b> 手动添加，"
            "或用 <b>刷新</b> 从 Google 地图拉取最新评价。</div>"
        )
    else:
        d = digest
        # 1. 中文简报
        parts.append("<h2>📊 今日简报</h2><div class='card'>")
        if d["avg_rating"]:
            dist = " · ".join(
                f"{s}星×{d['rating_dist'][s]}" for s in (5, 4, 3, 2, 1)
                if d["rating_dist"][s]
            )
            parts.append(
                f"<p style='font-size:20px'>⭐ <b>{d['avg_rating']}</b> "
                f"<span class='meta'>（{len(d['items'])} 条评价{(' · ' + dist) if dist else ''}）</span></p>"
            )
        parts.append(f"<p>{_esc(d['summary'])}</p>")
        if d["good_themes"]:
            parts.append("<div class='themes'>👍 大家最夸的：" + "".join(
                f"<span class='tag'>{_esc(t)}</span>" for t in d["good_themes"]) + "</div>")
        if d["bad_themes"]:
            parts.append("<div class='themes'>👎 被吐槽最多的：" + "".join(
                f"<span class='tag'>{_esc(t)}</span>" for t in d["bad_themes"]) + "</div>")
        parts.append("</div>")

        # 2. 差评预警 + 代笔回复
        if d["attention_count"]:
            parts.append(f"<h2>🚨 差评预警（{d['attention_count']} 条要处理）</h2>")
        else:
            parts.append("<h2>🎉 暂无差评，继续保持！</h2>")
        for idx, it in enumerate(d["items"]):
            if not it.needs_attention:
                continue
            r = it.review
            card = [
                "<div class='card alert'>",
                f"<div class='stars'>{'★' * int(r.rating)}{'☆' * (5 - int(r.rating))} {r.rating:g}星</div>",
                f"<div class='meta'>{_esc(r.author)} · {_esc(r.date)}</div>",
                f"<p>{_esc(it.zh_text)}</p>",
            ]
            reply = d["replies"].get(idx)
            if reply:
                card.append(
                    "<div class='reply'><b>✍️ 代笔回复（可直接发到 Google 地图）：</b><br>"
                    f"{_esc(reply['en_reply'])}<br><br>"
                    "<b>这条回复的意思是：</b><br>"
                    f"{_esc(reply['zh_explanation'])}</div>"
                )
            card.append("</div>")
            parts.append("".join(card))

        # 3. 全部评价（收起，翻译只是底料）
        parts.append("<details><summary><h2 style='display:inline'>💬 全部评价明细</h2></summary>")
        for it in d["items"]:
            r = it.review
            parts.append(
                "<div class='card'>"
                f"<div class='stars'>{'★' * int(r.rating)}{'☆' * (5 - int(r.rating))}</div>"
                f"<div class='meta'>{_esc(r.author)} · {_esc(r.date)}</div>"
                f"<p>{_esc(it.zh_text)}</p>"
                + "</div>"
            )
        parts.append("</details>")
    parts.append(
        "<h2>🔄 更新评价</h2>"
        "<form method='post' action='/refresh'><button type='submit'>从 Google 地图刷新</button></form>"
        "<h3>或手动粘贴评价</h3>"
        "<form method='post' action='/paste'><textarea name='text' placeholder='author: 张三\nrating: 5\n评价内容……\n---\n下一条评价……'></textarea><br>"
        "<button type='submit'>添加这些评价</button></form>"
        f"<p class='meta'>当前共 {review_count} 条评价 · review-bridge</p>"
        "</body></html>"
    )
    return "".join(parts)


class Bridge:
    """Holds reviews + digest; the HTTP handler delegates to it."""

    def __init__(self, reviews: list[Review], client, fetcher=None):
        self.reviews = list(reviews)
        self.client = client
        self.fetcher = fetcher  # () -> list[Review], used by /refresh
        self.digest = build_digest(self.reviews, self.client) if self.reviews else None

    def refresh(self) -> str:
        if not self.fetcher:
            return "没有配置拉取来源，请用粘贴模式添加评价。"
        try:
            self.reviews = self.fetcher()
        except Exception as exc:  # show the error in-page, stay alive
            return f"拉取失败：{exc}"
        self.digest = build_digest(self.reviews, self.client) if self.reviews else None
        return f"已更新：{len(self.reviews)} 条评价。"

    def add_pasted(self, text: str) -> str:
        new = parse_pasted(text)
        self.reviews.extend(new)
        self.digest = build_digest(self.reviews, self.client)
        return f"已添加 {len(new)} 条评价。"


def make_handler(bridge: Bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "review-bridge/0.1.0"

        def _send(self, body: str, code: int = 200):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(render_page(bridge.digest, len(bridge.reviews)))
            else:
                self._send("not found", 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            form = urllib.parse.parse_qs(
                self.rfile.read(length).decode("utf-8", "replace")
            )
            if self.path == "/refresh":
                msg = bridge.refresh()
            elif self.path == "/paste":
                msg = bridge.add_pasted(form.get("text", [""])[0])
            else:
                self._send("not found", 404)
                return
            self._send(
                f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
                f"<meta http-equiv='refresh' content='1;url=/'></head>"
                f"<body><p>{_esc(msg)} 正在返回……</p></body></html>"
            )

        def log_message(self, *args):
            pass  # quiet

    return Handler


def serve(bridge: Bridge, port: int = 8080) -> None:
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler(bridge))
    print(f"面馆评价小秘书运行在 http://localhost:{port}（手机连同一 Wi-Fi 访问）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
