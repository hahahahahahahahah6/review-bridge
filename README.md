# review-bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![No dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](pyproject.toml)

My parents run a noodle restaurant. They don't read English, so in fifteen years
they have never read a single one of their own Google Maps reviews. The 1-star
reviews sit there unanswered — and every restaurateur knows that *replying* to
reviews is what brings new customers in.

review-bridge is their **review secretary**. It watches Google Maps for them and
runs a loop they can actually use:

**盯着 → 汇总 → 预警 → 代笔回复 — watch, brief, alert, ghostwrite.**

1. **📊 中文简报 (brief)** — every morning, a Chinese briefing: average rating,
   rating trend, which dishes customers praise most, what they complain about most.
   Google Translate can translate a review. It cannot do this.
2. **🚨 差评预警 (alert)** — 1–2 star reviews get flagged immediately with urgency.
   My parents never open Google Maps; the tool watches it for them.
3. **✍️ 代笔回复 (ghostwrite)** — for each flagged review, a polite, natural
   *English* reply draft they can post publicly, plus a Chinese explanation of
   what the reply says and why. This is the real unlock: non-English-speaking
   owners responding to customers in fluent English.

Translation happens underneath, as plumbing. It is never presented as the product.

## Why open AI matters here

- **Runs offline** on the family laptop — no internet needed in a restaurant backroom.
- **Customer feedback never leaves the laptop** — no review data sent to a third-party AI API.
- **Zero cost** — a small family business shouldn't pay a SaaS subscription to read its own reviews.
- **The family controls it** — the whole UI is in Simplified Chinese, tuned for the owners, not for a generic dashboard.

The AI core is [Gemma 3](https://deepmind.google/technologies/gemma/) running locally
via [Ollama](https://ollama.com). Review fetching uses [SerpApi](https://serpapi.com)'s
Google Maps Reviews API (free tier: 100 searches/month — plenty for one restaurant).

Built for the [Hacktoberfest 2026 Weekend Challenge](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01)
(*Build for a Friend*). Entered prize categories: **Best Use of Gemma** ($200),
**Best Use of SerpApi** ($100).

## Quickstart (Windows laptop)

```powershell
# 1. Install Ollama from https://ollama.com, then:
ollama pull gemma3:4b

# 2. Free SerpApi key from https://serpapi.com (no credit card), then:
setx SERPAPI_KEY "your-key-here"

# 3. Install and run:
pip install review-bridge
review-bridge serve --query "Best Noodle House Rosemead"
# open http://localhost:8080 on your phone (same Wi-Fi)
```

No SerpApi key? Paste mode needs nothing:

```powershell
review-bridge paste < reviews.txt     # blocks separated by ---
review-bridge serve --mock            # demo with sample data, no network/AI
```

Paste format — blocks separated by a `---` line:

```
author: Jane D.
rating: 2
date: 2026-09-20
The noodles were cold and we waited 40 minutes...
---
author: Bob
rating: 5
Best beef noodle soup ever!
```

## CLI

```
review-bridge fetch --query "Restaurant Name"   # pull + print Chinese briefing
review-bridge fetch --place-id <serpapi_id>     # skip the name lookup
review-bridge paste [--file reviews.txt]        # no API key needed
review-bridge serve [--port 8080]               # Chinese web UI
review-bridge <cmd> --mock                      # canned data, no network/AI
```

## Tests

```
python -m pytest tests/ -q    # 26 tests, stdlib only
```

## Honest limitations

- The SerpApi free tier caps at 100 searches/month; a busy restaurant chain would outgrow it.
- Review-reply drafts are AI-generated — the owners should skim the Chinese explanation before posting.
- Star ratings on aggregator mirrors are sometimes sub-ratings; the tool trusts what the API returns.
- The local model needs ~4GB RAM free; a very old laptop will be slow (the `--mock` demo still works).
- This watches *Google Maps* reviews only — Yelp/DoorDash are separate worlds.
