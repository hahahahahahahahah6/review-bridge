"""Data models for review-bridge."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Review:
    author: str
    rating: float  # 1.0 - 5.0, 0.0 when unknown
    date: str
    text: str
    source: str = "google_maps"

    @property
    def needs_attention(self) -> bool:
        """1-2 star reviews get flagged for the owners."""
        return 0 < self.rating <= 2


@dataclass
class DigestItem:
    review: Review
    zh_text: str
    topics: List[str] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return self.review.needs_attention
