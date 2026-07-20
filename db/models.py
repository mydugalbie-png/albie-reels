"""SQLAlchemy models for Albie Reels."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class RunStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"
    SCRIPTING = "scripting"
    GENERATING_VISUALS = "generating_visuals"
    ASSEMBLING = "assembling"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    POSTED = "posted"
    DISCARDED = "discarded"
    FAILED = "failed"
    DRAFT = "draft"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(256)
    )
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    satire_score: Mapped[float] = mapped_column(Float, default=0.0)
    virality_score: Mapped[float] = mapped_column(Float, default=0.0)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    runs: Mapped[list["Run"]] = relationship(back_populates="story")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_number: Mapped[int] = mapped_column(Integer)
    day: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.PENDING.value)
    story_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stories.id"), nullable=True)
    script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    captions: Mapped[dict] = mapped_column(JSON, default=dict)
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    video_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    image_paths: Mapped[list] = mapped_column(JSON, default=list)
    audio_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_platforms: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    story: Mapped[Optional["Story"]] = relationship(back_populates="runs")

    __table_args__ = (UniqueConstraint("day", "run_number", name="uq_day_run"),)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[str] = mapped_column(String(10), unique=True)
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    ready_count: Mapped[int] = mapped_column(Integer, default=0)
    approved_count: Mapped[int] = mapped_column(Integer, default=0)
    posted_count: Mapped[int] = mapped_column(Integer, default=0)
    discarded_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
