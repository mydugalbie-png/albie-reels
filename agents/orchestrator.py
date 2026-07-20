"""Orchestrator – coordinates one full research → generate cycle."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.research import ResearchAgent
from agents.script import ScriptAgent
from agents.visual import VisualAgent
from agents.posting import PostingAgent
from db.models import Run, Story, RunStatus
from db.session import get_session
from utils.config import settings


class Orchestrator:
    def __init__(self) -> None:
        self.research = ResearchAgent()
        self.script = ScriptAgent()
        self.visual = VisualAgent()
        self.posting = PostingAgent()
        self.tz = ZoneInfo(settings.timezone)

    async def execute_run(self, run_number: int | None = None) -> dict[str, Any]:
        now = datetime.now(self.tz)
        day = now.strftime("%Y-%m-%d")

        async with get_session() as session:
            if run_number is None:
                result = await session.execute(
                    select(Run).where(Run.day == day).order_by(Run.run_number.desc())
                )
                last = result.scalars().first()
                run_number = (last.run_number + 1) if last else 1

            if run_number > settings.runs_per_day:
                logger.warning("Max runs per day reached ({})", settings.runs_per_day)
                return {"error": "max_runs_reached"}

            run = Run(run_number=run_number, day=day, status=RunStatus.RESEARCHING.value)
            session.add(run)
            await session.flush()
            run_id = run.id
            logger.info("=== Starting Run {} (id={}) on {} ===", run_number, run_id, day)

            try:
                story_data = await self.research.run()
                if not story_data:
                    run.status = RunStatus.FAILED.value
                    run.error_message = "No suitable story found"
                    await session.commit()
                    return {"error": "no_story", "run_id": run_id}

                story = Story(
                    title=story_data["title"],
                    summary=story_data.get("summary", ""),
                    source=story_data.get("source", "unknown"),
                    url=story_data.get("url"),
                    satire_score=story_data.get("satire_score", 0),
                    virality_score=story_data.get("virality_score", 0),
                    topics=story_data.get("topics", []),
                    raw=story_data.get("raw", {}),
                    used_at=now,
                )
                session.add(story)
                await session.flush()
                run.story_id = story.id
                run.status = RunStatus.SCRIPTING.value
                await session.commit()

                script_data = await self.script.run(story_data)
                run.script = script_data["script"]
                run.captions = script_data.get("captions", {})
                run.hashtags = script_data.get("hashtags", [])
                run.status = RunStatus.GENERATING_VISUALS.value
                await session.commit()

                visual_data = await self.visual.run(run_id, story_data, script_data)
                run.image_paths = visual_data.get("image_paths", [])
                run.audio_path = visual_data.get("audio_path")
                run.thumbnail_path = visual_data.get("thumbnail_path")
                run.video_path = visual_data.get("video_path")
                run.status = RunStatus.READY_FOR_REVIEW.value
                await session.commit()

                drafts = await self.posting.prepare({**script_data, **visual_data})

                logger.success("Run {} ready for human review. Video: {}", run_id, run.video_path)
                return {
                    "run_id": run_id,
                    "run_number": run_number,
                    "day": day,
                    "status": run.status,
                    "story": {
                        "title": story.title,
                        "source": story.source,
                        "url": story.url,
                        "satire_score": story.satire_score,
                    },
                    "script": run.script,
                    "video_path": run.video_path,
                    "thumbnail_path": run.thumbnail_path,
                    "captions": run.captions,
                    "hashtags": run.hashtags,
                    "drafts": drafts,
                }

            except Exception as e:
                logger.exception("Run {} failed", run_id)
                run.status = RunStatus.FAILED.value
                run.error_message = str(e)[:1000]
                await session.commit()
                return {"error": str(e), "run_id": run_id}
