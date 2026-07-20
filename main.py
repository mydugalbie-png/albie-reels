#!/usr/bin/env python3
"""Albie Reels – main entry point."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

import click
from loguru import logger

from utils.config import settings
from db.session import init_db
from agents.orchestrator import Orchestrator


@click.group()
def cli():
    """Albie Reels – autonomous satirical content engine with mandatory human approval."""
    logger.remove()
    logger.add(sys.stderr, level=settings.yaml_cfg.get("app", {}).get("log_level", "INFO"))
    log_path = settings.data_dir / "albie_reels.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_path, rotation="10 MB", retention="30 days", level="DEBUG")


@cli.command()
def init():
    """Initialise database and folders."""
    async def _init():
        await init_db()
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        settings.assets_dir.mkdir(parents=True, exist_ok=True)
        (ROOT / "review_queue").mkdir(parents=True, exist_ok=True)
        logger.success("Database and folders ready.")
        print("Init complete. You can now run: python main.py run")
    asyncio.run(_init())


@cli.command()
@click.option("--run-number", type=int, default=None)
def run(run_number):
    """Execute one full research + generation cycle."""
    async def _run():
        await init_db()
        orch = Orchestrator()
        result = await orch.execute_run(run_number=run_number)
        if "error" in result:
            logger.error("Failed: {}", result["error"])
            print(f"ERROR: {result['error']}")
            sys.exit(1)
        print("\n=== QUICK PREVIEW ===")
        story = result.get("story") or {}
        print("Story:", story.get("title", "N/A"))
        script = result.get("script") or ""
        print("Script preview:\n", script[:500])
        print("Video:", result.get("video_path") or "Not generated yet")
        print("\nNext: python main.py dashboard")
    asyncio.run(_run())


@cli.command()
def dashboard():
    """Launch the human review dashboard."""
    from dashboard.app import launch
    launch()


@cli.command()
def schedule():
    """Start the APScheduler daemon."""
    from scripts.scheduler import main as sched_main
    sched_main()


@cli.command()
def status():
    """Show current configuration snapshot."""
    print("=" * 50)
    print("  ALBIE REELS STATUS")
    print("=" * 50)
    print(f"Generate-only:    {settings.is_generate_only}")
    print(f"Auto-post:        {settings.auto_post}")
    print(f"Runs per day:     {settings.runs_per_day}")
    print(f"Max posts/day:    {settings.max_posts_per_day}")
    print(f"Schedule:         {settings.schedule_times}")
    refs = list(settings.assets_dir.glob("albie_ref_*")) if settings.assets_dir.exists() else []
    print(f"Albie refs:       {len(refs)} images")
    print(f"Output dir:       {settings.output_dir}")
    print("=" * 50)
    print("Commands: python main.py init | run | dashboard | schedule | status")
    print("=" * 50)


if __name__ == "__main__":
    cli()
