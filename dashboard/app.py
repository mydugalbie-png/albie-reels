"""Albie Reels Review Queue Dashboard – simple Gradio UI."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import gradio as gr
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.models import Run, RunStatus
from db.session import get_session, init_db
from agents.orchestrator import Orchestrator
from agents.posting import PostingAgent
from utils.config import settings

orchestrator = Orchestrator()
poster = PostingAgent()


async def get_runs_for_day(day: str | None = None):
    if day is None:
        day = datetime.now().strftime("%Y-%m-%d")
    async with get_session() as session:
        result = await session.execute(
            select(Run).options(selectinload(Run.story)).where(Run.day == day).order_by(Run.run_number)
        )
        runs = result.scalars().all()
        out = []
        for r in runs:
            out.append({
                "id": r.id,
                "run_number": r.run_number,
                "status": r.status,
                "title": r.story.title if r.story else "—",
                "source": r.story.source if r.story else "—",
                "satire_score": r.story.satire_score if r.story else 0,
                "script": r.script or "",
                "video_path": r.video_path,
                "thumbnail_path": r.thumbnail_path,
                "created_at": str(r.created_at),
            })
        return out


def format_run_card(run: dict) -> str:
    status_emoji = {
        "ready_for_review": "YELLOW READY",
        "approved": "GREEN APPROVED",
        "posted": "POSTED",
        "discarded": "DISCARDED",
        "failed": "FAILED",
    }.get(run["status"], run["status"])
    return f"""### Run #{run['run_number']} — {status_emoji}
**Story:** {run['title']}
**Source:** {run['source']} | Satire: {run['satire_score']}
**Created:** {run['created_at']}

**Script:**
```
{run['script'][:600]}{'...' if len(run['script'])>600 else ''}
```
**Video:** `{run['video_path'] or 'not yet'}`
"""


async def trigger_manual_run():
    result = await orchestrator.execute_run()
    if "error" in result:
        return f"Error: {result['error']}"
    return f"Run {result.get('run_id')} completed and ready for review.\nStory: {result.get('story', {}).get('title')}"


async def approve_run(run_id: int):
    async with get_session() as session:
        result = await session.execute(select(Run).where(Run.id == int(run_id)))
        run = result.scalar_one_or_none()
        if not run:
            return "Run not found"
        run.status = RunStatus.APPROVED.value
        run.approved_at = datetime.utcnow()
        await session.commit()
    return f"Run {run_id} marked APPROVED."


async def discard_run(run_id: int):
    async with get_session() as session:
        result = await session.execute(select(Run).where(Run.id == int(run_id)))
        run = result.scalar_one_or_none()
        if not run:
            return "Run not found"
        run.status = RunStatus.DISCARDED.value
        await session.commit()
    return f"Run {run_id} discarded."


def build_ui():
    with gr.Blocks(title="Albie Reels – Review Queue", theme=gr.themes.Soft(primary_hue="amber")) as demo:
        gr.Markdown("# Albie Reels – Human Review Queue\n**Nothing is posted without your explicit approval.**")
        with gr.Row():
            day_input = gr.Textbox(label="Day (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d"))
            refresh_btn = gr.Button("Refresh Queue", variant="primary")
            manual_run_btn = gr.Button("Trigger Manual Run Now")
        status_box = gr.Markdown("Ready.")
        queue_md = gr.Markdown("Click Refresh to load runs.")
        run_id_input = gr.Number(label="Run ID to act on", precision=0)
        with gr.Row():
            approve_btn = gr.Button("Approve", variant="primary")
            discard_btn = gr.Button("Discard", variant="stop")

        async def refresh(day):
            runs = await get_runs_for_day(day)
            if not runs:
                return "No runs for this day yet. Trigger a manual run.", "No data."
            cards = "\n\n---\n\n".join(format_run_card(r) for r in runs)
            ready = sum(1 for r in runs if r["status"] == "ready_for_review")
            return cards, f"**{day}** — Total: {len(runs)} | Ready: {ready}"

        refresh_btn.click(refresh, inputs=[day_input], outputs=[queue_md, status_box])
        manual_run_btn.click(trigger_manual_run, outputs=[status_box])
        approve_btn.click(approve_run, inputs=[run_id_input], outputs=[status_box])
        discard_btn.click(discard_run, inputs=[run_id_input], outputs=[status_box])
        demo.load(refresh, inputs=[day_input], outputs=[queue_md, status_box])
    return demo


def launch():
    asyncio.get_event_loop().run_until_complete(init_db())
    demo = build_ui()
    demo.queue().launch(
        server_name=settings.yaml_cfg.get("dashboard", {}).get("host", "0.0.0.0"),
        server_port=int(settings.yaml_cfg.get("dashboard", {}).get("port", 7860)),
        share=False,
    )


if __name__ == "__main__":
    launch()
