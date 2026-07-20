"""Visual & Video Agent – consistent Albie (no hat) + vertical reel assembly."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageDraw

from utils.config import settings


class VisualAgent:
    def __init__(self) -> None:
        self.assets = settings.assets_dir
        self.output = settings.output_dir
        self.backend = settings.yaml_cfg.get("visual", {}).get("image_gen_backend", "mock")
        self.refs = list(self.assets.glob("albie_ref_*.jpg")) + list(self.assets.glob("albie_ref_*.png"))
        if not self.refs:
            logger.warning("No Albie reference images found in {}", self.assets)

    async def run(self, run_id: int, story: dict[str, Any], script_data: dict[str, Any]) -> dict[str, Any]:
        logger.info("VisualAgent starting for run {}", run_id)
        run_dir = self.output / f"run_{run_id:04d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        image_paths = await self._generate_albie_images(run_dir, story, script_data)
        audio_path = await self._generate_tts(run_dir, script_data.get("script", ""))
        thumb_path = await self._make_thumbnail(run_dir, story, image_paths[0] if image_paths else None)
        video_path = await self._assemble_video(run_dir, image_paths, audio_path, script_data)

        return {
            "image_paths": [str(p) for p in image_paths],
            "audio_path": str(audio_path) if audio_path else None,
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "video_path": str(video_path) if video_path else None,
            "run_dir": str(run_dir),
        }

    async def _generate_albie_images(self, run_dir: Path, story: dict, script_data: dict) -> list[Path]:
        paths: list[Path] = []
        for i in range(5):
            out = run_dir / f"albie_frame_{i:02d}.jpg"
            if self.refs:
                src = self.refs[i % len(self.refs)]
                Image.open(src).convert("RGB").save(out, quality=92)
            else:
                img = Image.new("RGB", (1080, 1920), color=(30, 30, 40))
                draw = ImageDraw.Draw(img)
                draw.text((80, 900), f"Albie frame {i}", fill=(255, 220, 100))
                img.save(out)
            paths.append(out)
        logger.info("Generated {} Albie frames", len(paths))
        return paths

    async def _generate_tts(self, run_dir: Path, script: str) -> Path | None:
        out = run_dir / "voiceover.mp3"
        try:
            import edge_tts
            voice = "en-GB-RyanNeural"
            communicate = edge_tts.Communicate(script or "Albie speaking.", voice, rate="+5%")
            await communicate.save(str(out))
            logger.info("edge-tts voiceover saved → {}", out)
            return out
        except Exception as e:
            logger.error("TTS failed: {}", e)
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "40",
                     "-q:a", "9", "-acodec", "libmp3lame", str(out)],
                    check=True, capture_output=True,
                )
            except Exception:
                out.write_bytes(b"")
            return out

    async def _make_thumbnail(self, run_dir: Path, story: dict, face_path: Path | None) -> Path | None:
        out = run_dir / "thumbnail.jpg"
        try:
            if face_path and face_path.exists():
                base = Image.open(face_path).convert("RGB").resize((1080, 1920))
            else:
                base = Image.new("RGB", (1080, 1920), (20, 20, 30))
            draw = ImageDraw.Draw(base)
            title = (story.get("title") or "Albie Speaks")[:55]
            draw.rectangle([40, 1400, 1040, 1850], fill=(0, 0, 0))
            draw.text((60, 1450), "ALBIE REELS", fill=(255, 200, 50))
            draw.text((60, 1550), title, fill=(255, 255, 255))
            base.save(out, quality=90)
            return out
        except Exception as e:
            logger.error("Thumbnail failed: {}", e)
            return None

    async def _assemble_video(self, run_dir: Path, images: list[Path], audio: Path | None, script_data: dict) -> Path | None:
        out = run_dir / "reel_final.mp4"
        if not images:
            return None
        try:
            from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
            duration = script_data.get("estimated_seconds", 45)
            per_image = max(3.0, duration / max(len(images), 1))
            clips = []
            for img in images:
                clip = ImageClip(str(img)).with_duration(per_image).resized((1080, 1920))
                clips.append(clip)
            video = concatenate_videoclips(clips, method="compose")
            if audio and audio.exists() and audio.stat().st_size > 100:
                audioclip = AudioFileClip(str(audio))
                video = video.with_audio(audioclip)
                video = video.with_duration(min(video.duration, audioclip.duration + 0.5))
            video.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac", preset="medium", threads=4, logger=None)
            logger.success("Video assembled → {}", out)
            return out
        except Exception as e:
            logger.error("MoviePy assembly failed: {} – trying ffmpeg fallback", e)
            return await self._ffmpeg_fallback(run_dir, images, audio, out)

    async def _ffmpeg_fallback(self, run_dir: Path, images: list[Path], audio: Path | None, out: Path) -> Path | None:
        list_file = run_dir / "images.txt"
        with open(list_file, "w") as f:
            for img in images:
                f.write(f"file '{img.resolve()}'\n")
                f.write("duration 5\n")
            f.write(f"file '{images[-1].resolve()}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-vsync", "vfr", "-pix_fmt", "yuv420p",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        ]
        if audio and audio.exists():
            cmd.extend(["-i", str(audio), "-c:a", "aac", "-shortest"])
        cmd.extend(["-c:v", "libx264", "-r", "30", str(out)])
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return out
        except Exception as e:
            logger.error("ffmpeg fallback also failed: {}", e)
            return None
