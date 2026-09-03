"""Export the complete semifinal PPT as a visually faithful submission PDF."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "方案PPT" / "保险经营归因Agent-复赛完整答辩版.pptx"
OUT = ROOT / "复赛比赛交付包-v12" / "01_更新版项目方案" / "复赛升级方案-v12.pdf"
DEFAULT_RENDERER = Path(
    "/Users/lege/.codex/plugins/cache/openai-primary-runtime/"
    "presentations/26.819.11345/skills/presentations/container_tools/render_slides.py"
)


def build() -> None:
    renderer = Path(os.environ.get("RENDER_SLIDES_SCRIPT", DEFAULT_RENDERER))
    runtime_node = os.environ.get("RUNTIME_NODE")
    if not renderer.is_file():
        raise RuntimeError(f"render_slides.py not found: {renderer}")
    if not runtime_node:
        raise RuntimeError("RUNTIME_NODE is required for the PPT renderer")
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source PPT not found: {SOURCE}")

    with tempfile.TemporaryDirectory(prefix="goai-ppt-pdf-") as directory:
        render_dir = Path(directory) / "slides"
        env = os.environ.copy()
        subprocess.run(
            [
                sys.executable,
                str(renderer),
                str(SOURCE),
                "--output_dir",
                str(render_dir),
            ],
            check=True,
            env=env,
        )
        paths = sorted(
            render_dir.glob("slide-*.png"),
            key=lambda path: int(path.stem.split("-")[-1]),
        )
        if not paths:
            raise RuntimeError("PPT renderer produced no slide images")
        images = [Image.open(path).convert("RGB") for path in paths]
        try:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            images[0].save(
                OUT,
                "PDF",
                save_all=True,
                append_images=images[1:],
                resolution=144.0,
            )
        finally:
            for image in images:
                image.close()
    print(OUT)


if __name__ == "__main__":
    build()
