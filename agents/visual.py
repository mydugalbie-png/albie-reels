"""Visual & Video Agent – consistent Albie (no hat) + robust vertical reel assembly."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from utils.config import settings


class VisualAgent:
    def __init__(self) -> None:
        self.assets = settings.assets_dir
        self.output = settings.output_dir
        self.refs = sorted(
            list(self.assets.glob("albie_ref_*.jpg"))
            + list(self.assets.glob("albie_ref_*.png"))
            + list(self.assets.glob("albie_ref_*.jpeg"))
        )
        if not self.refs:
            logger.warning("No Albie reference images found in {}", self.assets)
        else:
            logger.info("Loaded {} Albie reference images", len(self.refs))

    async def run(self, run_id: int, story: dict[str, Any], script_data: dict[str, Any]) -> dict[str, Any]:
        logger.info("VisualAgent starting for run {}", run_id)
        run_dir = self.output / f"run_{run_id:04d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        image_paths = self._generate_albie_frames(run_dir, story, script_data)
        audio_path = await self._generate_tts(run_dir, script_data.get("script", ""))
        thumb_path = self._make_thumbnail(run_dir, story, image_paths[0] if image_paths else None)
        video_path = self._assemble_video_ffmpeg(run_dir, image_paths, audio_path, script_data)

        return {
            "image_paths": [str(p) for p in image_paths],
            "audio_path": str(audio_path) if audio_path else None,
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "video_path": str(video_path) if video_path else None,
            "run_dir": str(run_dir),
        }

    def _generate_albie_frames(self, run_dir: Path, story: dict, script_data: dict) -> list[Path]:
        paths: list[Path] = []
        title = (story.get("title") or "Albie Speaks")[:60]

        for i in range(5):
            out = run_dir / f"albie_frame_{i:02d}.jpg"
            if self.refs:
                src = self.refs[i % len(self.refs)]
                base = Image.open(src).convert("RGB")
                base = self._to_916(base)
            else:
                base = Image.new("RGB", (1080, 1920), color=(25, 28, 40))
                draw = ImageDraw.Draw(base)
                draw.text((100, 850), f"ALBIE FRAME {i+1}", fill=(255, 210, 80))

            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rectangle([0, 1450, 1080, 1920], fill=(0, 0, 0, 200))
            base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

            draw = ImageDraw.Draw(base)
            try:
                font_big = ImageFont.truetype("arial.ttf", 52)
                font_med = ImageFont.truetype("arial.ttf", 36)
            except Exception:
                font_big = ImageFont.load_default()
                font_med = font_big

            draw.text((50, 80), "ALBIE REELS", fill=(255, 200, 40), font=font_big)
            captions = [
                title[:45],
                "The numbers don't lie...",
                "Same faces. Same speeches.",
                "Ordinary folk pay the price.",
                "Albie out. Share if fed up.",
            ]
            draw.text((50, 1520), captions[i], fill=(255, 255, 255) if i < 4 else (255, 220, 80), font=font_med)

            base.save(out, quality=93)
            paths.append(out)

        logger.info("Generated {} Albie frames", len(paths))
        return paths

    def _to_916(self, img: Image.Image) -> Image.Image:
        target_w, target_h = 1080, 1920
        img = img.convert("RGB")
        ratio = max(target_w / img.width, target_h / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        left = (img.width - target_w) // 2
        top = (img.height - target_h) // 2
        return img.crop((left, top, left + target_w, top + target_h))

    async def _generate_tts(self, run_dir: Path, script: str) -> Path | None:
        out = run_dir / "voiceover.mp3"
        text = (script or "Albie speaking. Stay tuned.").strip()
        try:
            import edge_tts
            voice = "en-GB-RyanNeural"
            communicate = edge_tts.Communicate(text, voice, rate="+8%")
            await communicate.save(str(out))
            if out.exists() and out.stat().st_size > 1000:
                logger.info("edge-tts voiceover saved → {}", out)
                return out
        except Exception as e:
            logger.error("edge-tts failed: {}", e)

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                 "-t", "40", "-q:a", "9", "-acodec", "libmp3lame", str(out)],
                check=True, capture_output=True, timeout=30,
            )
            return out
        except Exception:
            out.write_bytes(b"")
            return out

    def _make_thumbnail(self, run_dir: Path, story: dict, face_path: Path | None) -> Path | None:
        out = run_dir / "thumbnail.jpg"
        try:
            if face_path and face_path.exists():
                base = self._to_916(Image.open(face_path))
            else:
                base = Image.new("RGB", (1080, 1920), (20, 22, 35))
            draw = ImageDraw.Draw(base)
            draw.rectangle([30, 1380, 1050, 1880], fill=(0, 0, 0))
            try:
                font = ImageFont.truetype("arial.ttf", 48)
            except Exception:
                font = ImageFont.load_default()
            title = (story.get("title") or "Albie Speaks")[:50]
            draw.text((60, 1420), "ALBIE REELS", fill=(255, 200, 40), font=font)
            draw.text((60, 1520), title, fill=(255, 255, 255), font=font)
            base.save(out, quality=90)
            return out
        except Exception as e:
            logger.error("Thumbnail failed: {}", e)
            return None

    def _assemble_video_ffmpeg(
        self, run_dir: Path, images: list[Path], audio: Path | None, script_data: dict
    ) -> Path | None:
        """Reliable FFmpeg assembly using filter_complex (correct option order)."""
        out = run_dir / "reel_final.mp4"
        if not images:
            return None

        # Get audio duration
        audio_dur = 40.0
        has_audio = audio and audio.exists() and audio.stat().st_size > 1000
        if has_audio:
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
                    capture_output=True, text=True, timeout=10,
                )
                audio_dur = float(probe.stdout.strip()) or 40.0
            except Exception:
                pass

        per = max(3.5, audio_dur / len(images))

        # Build input list: each image as a looped still
        cmd = ["ffmpeg", "-y"]
        for img in images:
            cmd.extend(["-loop", "1", "-t", f"{per:.3f}", "-i", str(img.resolve())])

        if has_audio:
            cmd.extend(["-i", str(audio.resolve())])

        # Build filter_complex to scale + concat
        n = len(images)
        filters = []
        for i in range(n):
            filters.append(
                f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]"
            )
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        filters.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")

        cmd.extend(["-filter_complex", ";".join(filters)])
        cmd.extend(["-map", "[vout]"])

        if has_audio:
            cmd.extend(["-map", f"{n}:a", "-c:a", "aac", "-b:a", "192k", "-shortest"])

        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            str(out),
        ])

        try:
            logger.info("Assembling video with FFmpeg…")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                logger.error("FFmpeg failed:\n{}", result.stderr[-1200:])
                return None
            if out.exists() and out.stat().st_size > 10000:
                logger.success("Video ready → {} ({:.1f} KB)", out, out.stat().st_size / 1024)
                return out
            logger.error("Video file missing or too small")
            return None
        except Exception as e:
            logger.error("Assembly exception: {}", e)
            return None
