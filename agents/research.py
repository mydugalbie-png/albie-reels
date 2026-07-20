"""Research Agent – finds fresh, high-satire-potential UK/Scottish stories."""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import settings

_recent_story_hashes: set[str] = set()


def _hash_story(title: str, url: str | None = None) -> str:
    key = (title or "").strip().lower() + "|" + (url or "")
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class ResearchAgent:
    """Pulls trending Scottish/UK political & social stories and ranks them."""

    def __init__(self) -> None:
        self.focus = settings.yaml_cfg.get("research", {}).get("focus_topics", [])
        self.min_score = float(settings.yaml_cfg.get("research", {}).get("min_satire_score", 6.5))
        self.avoid_hours = int(settings.yaml_cfg.get("research", {}).get("avoid_repeat_hours", 24))

    async def run(self, exclude_hashes: set[str] | None = None) -> dict[str, Any] | None:
        exclude = exclude_hashes or _recent_story_hashes
        logger.info("ResearchAgent starting… focus={}", self.focus[:3])

        candidates: list[dict[str, Any]] = []

        try:
            candidates.extend(await self._search_duckduckgo())
        except Exception as e:
            logger.warning("DuckDuckGo search failed: {}", e)

        if settings.newsapi_key:
            try:
                candidates.extend(await self._search_newsapi())
            except Exception as e:
                logger.warning("NewsAPI failed: {}", e)

        if not candidates:
            logger.warning("No live results – using high-quality mock Scottish stories")
            candidates = self._mock_stories()

        ranked = self._rank(candidates)
        for story in ranked:
            h = _hash_story(story["title"], story.get("url"))
            if h in exclude:
                continue
            if story.get("satire_score", 0) < self.min_score:
                continue
            _recent_story_hashes.add(h)
            story["hash"] = h
            logger.success("Selected story: {} (score={})", story["title"][:80], story["satire_score"])
            return story

        logger.error("No suitable unused story found this run")
        return None

    async def _search_duckduckgo(self) -> list[dict]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

        results = []
        queries = [
            "Scotland politics news",
            "SNP government failure",
            "NHS Scotland crisis",
            "immigration Scotland",
            "crime Scotland women safety",
            "Holyrood scandal",
        ]
        with DDGS() as ddgs:
            for q in queries[:3]:
                for r in ddgs.news(q, max_results=4, region="uk-en"):
                    results.append({
                        "title": r.get("title", ""),
                        "summary": r.get("body", "")[:400],
                        "url": r.get("url"),
                        "source": r.get("source", "DuckDuckGo"),
                        "published_at": r.get("date"),
                        "raw": r,
                    })
        return results

    async def _search_newsapi(self) -> list[dict]:
        import httpx
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "OR ".join([f'"{t}"' for t in self.focus[:5]]),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 15,
            "apiKey": settings.newsapi_key,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        out = []
        for a in data.get("articles", []):
            out.append({
                "title": a.get("title") or "",
                "summary": (a.get("description") or a.get("content") or "")[:400],
                "url": a.get("url"),
                "source": (a.get("source") or {}).get("name", "NewsAPI"),
                "published_at": a.get("publishedAt"),
                "raw": a,
            })
        return out

    def _rank(self, candidates: list[dict]) -> list[dict]:
        scored = []
        for c in candidates:
            title = (c.get("title") or "").lower()
            summary = (c.get("summary") or "").lower()
            text = title + " " + summary

            score = 5.0
            if any(k in text for k in ["scandal", "failure", "crisis", "cover-up", "liar", "corrupt"]):
                score += 1.5
            if any(k in text for k in ["snp", "sturgeon", "swinney", "holyrood", "scottish government"]):
                score += 1.2
            if any(k in text for k in ["immigration", "asylum", "hotel", "migrant"]):
                score += 1.0
            if any(k in text for k in ["women", "safety", "assault", "grooming"]):
                score += 1.3
            if any(k in text for k in ["nhs", "waiting list", "ambulance"]):
                score += 0.9
            if any(k in text for k in ["crime", "knife", "police"]):
                score += 0.8

            score += random.uniform(0, 0.8)
            c["satire_score"] = round(min(score, 10.0), 2)
            c["virality_score"] = round(random.uniform(4.0, 9.0), 2)
            c["topics"] = [t for t in self.focus if t.lower().split()[0] in text]
            scored.append(c)

        scored.sort(key=lambda x: (x["satire_score"], x["virality_score"]), reverse=True)
        return scored

    def _mock_stories(self) -> list[dict]:
        return [
            {
                "title": "Scottish Government admits another NHS waiting-list record as winter approaches",
                "summary": "Figures show elective surgery backlogs hit new highs while ministers claim 'progress'. Opposition call it systemic failure.",
                "url": "https://example.com/nhs-waiting",
                "source": "Mock / The Scotsman style",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "satire_score": 8.4,
                "virality_score": 7.9,
                "topics": ["NHS Scotland", "SNP government failures"],
            },
            {
                "title": "Hotel housing asylum seekers in Glasgow sparks local safety concerns after third incident",
                "summary": "Residents report rising tension and a series of disturbances linked to temporary accommodation sites.",
                "url": "https://example.com/hotel-asylum",
                "source": "Mock / Daily Record style",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "satire_score": 8.7,
                "virality_score": 8.5,
                "topics": ["immigration", "crime Scotland", "women's safety"],
            },
            {
                "title": "Former First Minister faces fresh questions over missing campaign funds as inquiry calls grow",
                "summary": "MPs demand full police investigation after parliamentary exchanges raise new inconsistencies.",
                "url": "https://example.com/sturgeon-funds",
                "source": "Mock / Parliamentary sketch",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "satire_score": 9.1,
                "virality_score": 8.8,
                "topics": ["Scottish politics", "SNP government failures"],
            },
            {
                "title": "Police Scotland data shows continued rise in recorded sexual offences against women",
                "summary": "Campaigners say the system is failing victims while politicians trade slogans instead of solutions.",
                "url": "https://example.com/women-safety",
                "source": "Mock / BBC Scotland style",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "satire_score": 8.2,
                "virality_score": 7.6,
                "topics": ["women's safety UK", "crime Scotland"],
            },
        ]
