"""Posting Agent – only posts after explicit human approval."""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from utils.config import settings


class PostingAgent:
    def __init__(self) -> None:
        self.platforms = settings.yaml_cfg.get("posting", {}).get("platforms", [])
        self.prepare_only = settings.yaml_cfg.get("posting", {}).get("prepare_drafts_only", True)
        self.delay = int(settings.yaml_cfg.get("posting", {}).get("delay_between_platforms_sec", 45))
        self.require_approval = True

    async def prepare(self, run_data: dict[str, Any]) -> dict[str, Any]:
        drafts = {}
        for platform in self.platforms:
            drafts[platform] = {
                "caption": run_data.get("captions", {}).get(platform, run_data.get("script", "")[:200]),
                "hashtags": run_data.get("hashtags", []),
                "video_path": run_data.get("video_path"),
                "thumbnail_path": run_data.get("thumbnail_path"),
                "status": "draft_ready",
            }
        logger.info("Drafts prepared for platforms: {}", list(drafts.keys()))
        return drafts

    async def post_approved(self, run_id: int, run_data: dict[str, Any], platforms: list[str] | None = None) -> dict[str, Any]:
        if settings.is_generate_only:
            logger.warning("GENERATE_ONLY_MODE is active – refusing to post run {}", run_id)
            return {"status": "blocked_by_generate_only_mode", "posted": []}

        if not self.require_approval:
            raise RuntimeError("Safety violation: require_approval must be True")

        target = platforms or self.platforms
        results = {}
        for p in target:
            logger.info("Would post run {} to {} (real API call gated)", run_id, p)
            results[p] = {
                "status": "simulated_success" if settings.app_env == "development" else "not_implemented",
                "message": "Posting endpoints are stubbed for safety. Wire real credentials carefully.",
            }
            await asyncio.sleep(self.delay)

        return {"status": "completed", "results": results}
