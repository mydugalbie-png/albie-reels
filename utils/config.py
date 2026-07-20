"""Configuration loader for Albie Reels."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"


def load_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    database_url: str = Field(default="sqlite+aiosqlite:///./data/albie_reels.db")

    auto_post: bool = False
    generate_only_mode: bool = True
    max_posts_per_day: int = 2

    newsapi_key: str | None = None
    x_bearer_token: str | None = None
    x_api_key: str | None = None
    x_api_secret: str | None = None
    x_access_token: str | None = None
    x_access_secret: str | None = None
    serpapi_key: str | None = None
    replicate_api_token: str | None = None
    fal_key: str | None = None
    stability_api_key: str | None = None
    openai_api_key: str | None = None
    xai_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None

    yaml_cfg: dict[str, Any] = Field(default_factory=load_yaml_config)

    @property
    def runs_per_day(self) -> int:
        return int(self.yaml_cfg.get("scheduler", {}).get("runs_per_day", 5))

    @property
    def schedule_times(self) -> list[str]:
        return list(self.yaml_cfg.get("scheduler", {}).get("schedule_times", ["07:00", "11:00", "15:00", "19:00", "22:00"]))

    @property
    def timezone(self) -> str:
        return self.yaml_cfg.get("app", {}).get("timezone", "Europe/London")

    @property
    def assets_dir(self) -> Path:
        p = Path(self.yaml_cfg.get("app", {}).get("assets_dir", "./assets/character_assets"))
        return (ROOT / p).resolve() if not p.is_absolute() else p

    @property
    def output_dir(self) -> Path:
        p = Path(self.yaml_cfg.get("app", {}).get("output_dir", "./output"))
        out = (ROOT / p).resolve() if not p.is_absolute() else p
        out.mkdir(parents=True, exist_ok=True)
        return out

    @property
    def data_dir(self) -> Path:
        p = Path(self.yaml_cfg.get("app", {}).get("data_dir", "./data"))
        d = (ROOT / p).resolve() if not p.is_absolute() else p
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def abs_database_url(self) -> str:
        db_path = self.data_dir / "albie_reels.db"
        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def is_generate_only(self) -> bool:
        return self.generate_only_mode or not self.auto_post


settings = Settings()
