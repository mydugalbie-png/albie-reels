"""Script Agent – writes tight 30-60s satirical Albie monologues."""
from __future__ import annotations

import random
from typing import Any

from loguru import logger

from utils.config import settings

SCOTTISH_FLAVOUR = [
    "Right, listen up yous…",
    "Aye, well would ye look at this…",
    "Here we go again, eh?",
    "Pure mental, this is.",
    "I'm no even surprised anymore.",
    "Typical.",
    "Absolute state of it.",
    "They must think we're all daft.",
]


class ScriptAgent:
    def __init__(self) -> None:
        self.target_sec = int(settings.yaml_cfg.get("script", {}).get("target_duration_sec", 45))
        self.max_words = int(settings.yaml_cfg.get("script", {}).get("max_words", 140))
        self.tone = settings.yaml_cfg.get("script", {}).get("tone", "sharp, savage, witty")

    async def run(self, story: dict[str, Any], dialect: str = "scottish") -> dict[str, Any]:
        logger.info("ScriptAgent writing for: {}", story.get("title", "")[:60])

        title = story.get("title", "this latest mess")
        summary = story.get("summary", "")
        topics = story.get("topics", [])

        hook = self._make_hook(title, dialect)
        setup = self._make_setup(title, summary)
        punches = self._make_punchlines(title, summary, topics)
        cta = self._make_cta()

        full_script = f"{hook}\n\n{setup}\n\n{punches}\n\n{cta}"

        words = full_script.split()
        if len(words) > self.max_words:
            full_script = " ".join(words[: self.max_words]) + "…"

        captions = self._platform_captions(title, full_script)
        hashtags = self._hashtags(topics)

        return {
            "script": full_script.strip(),
            "hook": hook,
            "setup": setup,
            "punchlines": punches,
            "cta": cta,
            "estimated_seconds": min(60, max(30, int(len(full_script.split()) * 0.4))),
            "captions": captions,
            "hashtags": hashtags,
            "dialect": dialect,
        }

    def _make_hook(self, title: str, dialect: str) -> str:
        openers = [
            f"Right, Albie here. {random.choice(SCOTTISH_FLAVOUR)}",
            "You are not going to believe this one.",
            "Another day, another absolute howler from the people running the show.",
            "Sit down, grab a biscuit, and listen to this.",
        ]
        short_title = title[:70] + ("…" if len(title) > 70 else "")
        return f"{random.choice(openers)} {short_title}."

    def _make_setup(self, title: str, summary: str) -> str:
        return (
            f"So the latest is: {summary[:180].rstrip('.')}. "
            "Now, on paper that already sounds bad. In practice? Even worse."
        )

    def _make_punchlines(self, title: str, summary: str, topics: list) -> str:
        punches = [
            "They keep telling us everything is under control. The numbers keep telling a different story.",
            "If this was a private company the board would have been cleared out months ago.",
            "But somehow the same faces are still giving the same speeches about 'progress'.",
            "Ordinary folk are the ones paying the price while the spin machine keeps spinning.",
        ]
        if any("nhs" in t.lower() for t in topics):
            punches.append("Patients waiting years while the ministers wait for the next election cycle.")
        if any("immig" in t.lower() or "asylum" in t.lower() for t in topics):
            punches.append("Communities raising legitimate concerns get called names instead of getting answers.")
        if any("women" in t.lower() or "safety" in t.lower() for t in topics):
            punches.append("Women's safety should not be a political football. Yet here we are.")

        selected = random.sample(punches, k=min(3, len(punches)))
        return " ".join(selected)

    def _make_cta(self) -> str:
        ctas = [
            "Share this if you're as fed up as I am. And remember – keep watching, keep questioning.",
            "Follow for more no-nonsense takes. Albie out.",
            "Like and share if this needs to be seen. We're not daft.",
            "Drop a comment with your thoughts. The more of us that speak up, the harder it is to ignore.",
        ]
        return random.choice(ctas)

    def _platform_captions(self, title: str, script: str) -> dict[str, str]:
        short = script[:180] + "…"
        return {
            "instagram_reels": f"{short}\n\n#AlbieReels #Scotland #Truth",
            "tiktok": f"{short}\n\n#fyp #Scotland #PoliticalComedy",
            "youtube_shorts": f"{title}\n\n{short}\n\nSubscribe for daily Albie takes.",
            "facebook": f"Albie's take on the latest:\n\n{script[:300]}…\n\nWhat do you think?",
        }

    def _hashtags(self, topics: list) -> list[str]:
        base = ["#AlbieReels", "#Scotland", "#UKPolitics", "#NoNonsense"]
        extra = []
        for t in topics:
            tag = "#" + "".join(w.capitalize() for w in t.replace("'", "").split()[:3])
            if tag not in base:
                extra.append(tag)
        return base + extra[:6]
