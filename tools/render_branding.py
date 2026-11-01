"""Render canonical SVG brand sources to Home Assistant's PNG variants.

Run: uv run --with cairosvg==2.9.1 python tools/render_branding.py
Only needed when the editable SVG artwork changes, not at install time.
"""
from pathlib import Path
import cairosvg

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "light_routines" / "brand"
for name in ("icon", "dark_icon"):
    for suffix, size in (("", 256), ("@2x", 512)):
        cairosvg.svg2png(url=str(BRAND / f"{name}.svg"),
                        write_to=str(BRAND / f"{name}{suffix}.png"),
                        output_width=size, output_height=size)
