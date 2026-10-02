"""Paste mode: turn manually pasted review text into Reviews, no API key needed.

Format: blocks separated by a line containing only `---`.
Each block is free text; optional header lines set metadata:

    author: Jane D.
    rating: 2
    date: 2026-09-20
    The noodles were cold and the wait was 40 minutes...

Anything that is not a header line is the review text. rating defaults to 5,
author to 匿名, date to "".
"""
from __future__ import annotations

import re

from .models import Review

_HEADER = re.compile(r"^(author|rating|date)\s*:\s*(.+)$", re.IGNORECASE)


def parse_pasted(text: str) -> list[Review]:
    reviews: list[Review] = []
    for block in re.split(r"(?m)^\s*---\s*$", text or ""):
        block = block.strip()
        if not block:
            continue
        author, rating, date = "匿名", 5.0, ""
        body_lines: list[str] = []
        for line in block.splitlines():
            m = _HEADER.match(line.strip())
            if m:
                key, val = m.group(1).lower(), m.group(2).strip()
                if key == "author" and val:
                    author = val
                elif key == "rating":
                    try:
                        rating = float(val)
                    except ValueError:
                        pass
                elif key == "date":
                    date = val
            else:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        reviews.append(Review(author=author, rating=rating, date=date, text=body))
    return reviews
