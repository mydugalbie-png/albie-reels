"""Visual & Video Agent – Albie photos + Ken Burns motion + Grok Imagine prompts."""
from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from utils.config import settings


ALBIE_CHARACTER_LOCK = """
Photorealistic brown-and-white dog named Albie. Medium-sized, short coat, 
brown ears and eye patches, white muzzle, chest and paws, intelligent dark eyes, 
slightly serious / unimpressed expression, no hat, no clothing, natural outdoor 
or clean indoor lighting, sharp detail, 9:16 vertical composition, cinematic.
""".strip()


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

        # Write Grok Imagine prompts for this run
        prompts_path = self._write_grok_imagine_prompts(run_dir, story, script_data)

        video_path = self._assemble_video_ffmpeg(run_dir, image_paths, audio_path, script_data)

        return {
            "image_paths": [str(p) for p in image_paths],
            "audio_path": str(audio_path) if audio_path else None,
            "thumbnail_path": str(thumb_path) if thumb_path else None,
            "video_path": str(video_path) if video_path else None,
            "grok_imagine_prompts": str(prompts_path) if prompts_path else None,
            "run_dir": str(run_dir),
        }

    def _generate_albie_frames(self, run_dir: Path, story: dict, script_data: dict) -> list[Path]:
        """Create 5 vertical frames from real Albie photos + bold text."""
        paths: list[Path] = []
        title = (story.get("title") or "Albie Speaks")[:55]

        captions = [
            title,
            "The numbers don't lie...",
            "Same faces. Same speeches.",
            "Ordinary folk pay the price.",
            "Albie out. Share if fed up.",
        ]

        for i in range(5):
            out = run_dir / f"albie_frame_{i:02d}.jpg"
            if self.refs:
                src = self.refs[i % len(self.refs)]
                base = Image.open(src).convert("RGB")
                base = self._to_916(base)
                # Slight contrast boost so it pops on mobile
                base = ImageEnhance.Contrast(base).enhance(1.08)
                base = ImageEnhance.Color(base).enhance(1.05)
            else:
                base = Image.new("RGB", (1080, 1920), color=(25, 28, 40))

            # Bottom gradient bar for readability
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rectangle([0, 1420, 1080, 1920], fill=(0, 0, 0, 210))
            base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

            draw = ImageDraw.Draw(base)
            try:
                font_brand = ImageFont.truetype("arial.ttf", 48)
                font_cap = ImageFont.truetype("arial.ttf", 38)
            except Exception:
                font_brand = ImageFont.load_default()
                font_cap = font_brand

            draw.text((48, 70), "ALBIE REELS", fill=(255, 200, 40), font=font_brand)
            # Word-wrap caption
            cap = captions[i]
            lines = textwrap.wrap(cap, width=28)[:3]
            y = 1500
            for line in lines:
                draw.text((48, y), line, fill=(255, 255, 255) if i < 4 else (255, 220, 80), font=font_cap)
                y += 48

            base.save(out, quality=94)
            paths.append(out)

        logger.info("Generated {} Albie frames from real photos", len(paths))
        return paths

    def _to_916(self, img: Image.Image) -> Image.Image:
        target_w, target_h = 1080, 1920
        img = img.convert("RGB")
        ratio = max(target_w / img.width, target_h / img.height)
        new_size = (int(img.width * ratio + 0.5), int(img.height * ratio + 0.5))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        left = max(0, (img.width - target_w) // 2)
        top = max(0, (img.height - target_h) // 2)
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
                font = ImageFont.truetype("arial.ttf", 46)
            except Exception:
                font = ImageFont.load_default()
            title = (story.get("title") or "Albie Speaks")[:48]
            draw.text((50, 1420), "ALBIE REELS", fill=(255, 200, 40), font=font)
            for i, line in enumerate(textwrap.wrap(title, width=26)[:2]):
                draw.text((50, 1520 + i * 55), line, fill=(255, 255, 255), font=font)
            base.save(out, quality=91)
            return out
        except Exception as e:
            logger.error("Thumbnail failed: {}", e)
            return None

    def _write_grok_imagine_prompts(self, run_dir: Path, story: dict, script_data: dict) -> Path | None:
        """Create ready-to-paste Grok Imagine prompts locked to Albie."""
        out = run_dir / "grok_imagine_prompts.txt"
        title = story.get("title") or "latest Scottish politics mess"
        hook = (script_data.get("hook") or "")[:120]

        prompts = [
            f"{ALBIE_CHARACTER_LOCK} Looking directly at camera with a dry, unimpressed expression. Slight head tilt. Soft natural window light. Ultra detailed fur. 9:16 vertical.",
            f"{ALBIE_CHARACTER_LOCK} Side eye to camera, one eyebrow raised, as if saying 'are you serious?'. Shallow depth of field. Cinematic. 9:16 vertical.",
            f"{ALBIE_CHARACTER_LOCK} Sitting upright, ears slightly back, serious news-anchor energy. Clean background blur. Sharp eyes. 9:16 vertical.",
            f"{ALBIE_CHARACTER_LOCK} Close-up portrait, looking slightly off-camera then locking eyes, judgemental Scottish dog energy. Dramatic lighting. 9:16 vertical.",
            f"{ALBIE_CHARACTER_LOCK} Medium shot, Albie reacting to bad news, subtle head shake energy, mouth closed, intelligent eyes. Natural outdoor bokeh. 9:16 vertical.",
            f"{ALBIE_CHARACTER_LOCK} Hero shot for thumbnail: Albie facing camera, confident and unimpressed, bold negative space at bottom for text overlay 'ALBIE REELS'. 9:16 vertical, high detail.",
        ]

        content = f"""ALBIE REELS – GROK IMAGINE PROMPTS
Run folder: {run_dir.name}
Story: {title}
Hook: {hook}

HOW TO USE:
1. Go to Grok / Imagine
2. Paste one prompt at a time
3. (Optional) upload one of your albie_ref_*.jpg photos as reference / style lock
4. Generate 9:16 images
5. Save the best ones back into this folder as albie_frame_00.jpg etc. and re-assemble
   OR just keep them for future reference.

CHARACTER LOCK (always keep this):
{ALBIE_CHARACTER_LOCK}

--- PROMPTS ---

"""
        for i, p in enumerate(prompts, 1):
            content += f"\nPROMPT {i}:\n{p}\n"

        content += """

TIP: For best consistency, generate all 6 in the same chat/session and pick the strongest 5.
Then replace the frames in this run folder and re-run the ffmpeg assemble step if you want.
"""
        try:
            out.write_text(content, encoding="utf-8")
            logger.info("Grok Imagine prompts saved → {}", out)
            return out
        except Exception as e:
            logger.error("Failed to write Grok prompts: {}", e)
            return None

    def _assemble_video_ffmpeg(
        self, run_dir: Path, images: list[Path], audio: Path | None, script_data: dict
    ) -> Path | None:
        """FFmpeg assembly with subtle Ken Burns (slow zoom) motion."""
        out = run_dir / "reel_final.mp4"
        if not images:
            return None

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

        per = max(3.8, audio_dur / len(images))

        cmd = ["ffmpeg", "-y"]
        for img in images:
            cmd.extend(["-loop", "1", "-t", f"{per:.3f}", "-i", str(img.resolve())])

        if has_audio:
            cmd.extend(["-i", str(audio.resolve())])

        n = len(images)
        filters = []
        # Ken Burns: gentle zoom in / out alternating for life
        for i in range(n):
            if i % 2 == 0:
                # slow zoom in
                zoom = (
                    f"[{i}:v]scale=1200:2133,zoompan=z='min(zoom+0.0008,1.15)':"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(per*30)}:"
                    f"s=1080x1920:fps=30,setsar=1[v{i}]"
                )
            else:
                # slow zoom out from slight zoom
                zoom = (
                    f"[{i}:v]scale=1200:2133,zoompan=z='if(eq(on,1),1.12,max(zoom-0.0008,1.0))':"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(per*30)}:"
                    f"s=1080x1920:fps=30,setsar=1[v{i}]"
                )
            filters.append(zoom)

        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        filters.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")

        cmd.extend(["-filter_complex", ";".join(filters)])
        cmd.extend(["-map", "[vout]"])

        if has_audio:
            cmd.extend(["-map", f"{n}:a", "-c:a", "aac", "-b:a", "192k", "-shortest"])

        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            str(out),
        ])

        try:
            logger.info("Assembling video with Ken Burns motion…")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if result.returncode != 0:
                logger.error("FFmpeg failed:\n{}", result.stderr[-1400:])
                # Fallback: simple version without zoompan
                return self._assemble_simple_fallback(run_dir, images, audio, per, has_audio, out)
            if out.exists() and out.stat().st_size > 10000:
                logger.success("Video ready → {} ({:.1f} KB)", out, out.stat().st_size / 1024)
                return out
            return None
        except Exception as e:
            logger.error("Assembly exception: {}", e)
            return self._assemble_simple_fallback(run_dir, images, audio, per, has_audio, out)

    def _assemble_simple_fallback(self, run_dir, images, audio, per, has_audio, out) -> Path | None:
        """No-zoom fallback if zoompan fails on some FFmpeg builds."""
        try:
            cmd = ["ffmpeg", "-y"]
            for img in images:
                cmd.extend(["-loop", "1", "-t", f"{per:.3f}", "-i", str(img.resolve())])
            if has_audio:
                cmd.extend(["-i", str(audio.resolve())])

            n = len(images)
            filters = []
            for i in range(n):
                filters.append(
                    f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                    f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}]"
                )
            concat_inputs = "".join(f"[v{i}]" for i in range(n))
            filters.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vout]")
            cmd.extend(["-filter_complex", ";".join(filters), "-map", "[vout]"])
            if has_audio:
                cmd.extend(["-map", f"{n}:a", "-c:a", "aac", "-b:a", "192k", "-shortest"])
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", str(out)])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode == 0 and out.exists() and out.stat().st_size > 10000:
                logger.success("Video ready (simple fallback) → {}", out)
                return out
            logger.error("Fallback also failed: {}", result.stderr[-800:] if result else "")
            return None
        except Exception as e:
            logger.error("Fallback exception: {}", e)
            return None
