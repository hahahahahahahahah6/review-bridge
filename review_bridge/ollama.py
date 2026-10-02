"""Ollama client (stdlib only) plus a mock for tests and --mock mode.

Prompts carry a [TASK:...] tag on the first line so the mock can route to
canned responses. The tag is harmless to a real model.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .serpapi import ReviewBridgeError


class OllamaClient:
    def __init__(
        self,
        model: str = "gemma3:4b",
        host: str = "http://localhost:11434",
        timeout: int = 180,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False}
        ).encode("utf-8")
        req = urllib.request.Request(
            self.host + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise ReviewBridgeError(
                f"Ollama is not reachable at {self.host}. "
                "Start it with `ollama serve` (or run with --mock)."
            ) from exc
        return str(data.get("response", ""))


class MockOllamaClient(OllamaClient):
    """Deterministic canned answers, keyed off the [TASK:...] tag."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if prompt.startswith("[TASK:translate]"):
            marker = prompt.splitlines()[-1][:24] if prompt.splitlines() else ""
            return json.dumps(
                {"zh": "【模拟翻译】" + marker + "……", "topics": ["模拟主题"]},
                ensure_ascii=False,
            )
        if prompt.startswith("[TASK:summarize]"):
            return json.dumps(
                {
                    "summary": "【模拟总结】大家普遍觉得面好吃，分量足。",
                    "good_themes": ["面条好吃", "分量足"],
                    "bad_themes": ["等位久"],
                },
                ensure_ascii=False,
            )
        if prompt.startswith("[TASK:reply]"):
            return json.dumps(
                {
                    "en_reply": "[MOCK EN REPLY] We're sorry about your experience and will improve.",
                    "zh_explanation": "【模拟说明】这条英文回复先道歉，再承诺改进，最后邀请顾客再来。",
                },
                ensure_ascii=False,
            )
        return json.dumps({"zh": "【模拟】", "topics": []}, ensure_ascii=False)
