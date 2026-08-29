"""Build the final CW dial PNG: cairosvg-rendered face + PIL notches/numbers/bar.

The face comes from the exact cw-input CSS. We add:
- 6 notches (60deg apart) OUTSIDE the circle face, with numbers 1..6
- indicator bar 26x4 at center, rotated to selected*60deg

All on 4x supersampling, downscaled to `size`.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).parent.parent / "assets" / "generated"
FACE = BASE / "dial_cw_face_v2.png"


def build_dial(size=64, num_options=6, selected_index=0):
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    face = Image.open(FACE).convert("RGBA").resize((S, S), Image.LANCZOS)
    img.paste(face, (0, 0), face)
    cx = cy = S // 2
    R = S // 2 - 4 * 4  # face radius (minus border)

    # notches + numbers 1..6, outside the face (like position absolute outside circle)
    for i in range(1, 7):
        a_deg = (i - 1) * 60
        a = math.radians(a_deg - 90)
        # tick line just outside the circle
        t1x = cx + math.cos(a) * (R + 2 * 4)
        t1y = cy + math.sin(a) * (R + 2 * 4)
        t2x = cx + math.cos(a) * (R + 8 * 4)
        t2y = cy + math.sin(a) * (R + 8 * 4)
        d.line((t1x, t1y, t2x, t2y), fill=(255, 255, 255, 220), width=1 * 4)
        # number further out
        nx = cx + math.cos(a) * (R + 12 * 4)
        ny = cy + math.sin(a) * (R + 12 * 4)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14 * 4)
        except OSError:
            try:
                font = ImageFont.truetype("Helvetica.ttc", 14 * 4)
            except OSError:
                font = ImageFont.load_default()
        d.text((nx, ny), str(i), fill=(255, 255, 255, 220), font=font, anchor="mm")

    # indicator bar: 26x4, transform-origin 2px from left, centered, rotated
    bar_w, bar_h = 26 * 4, 4 * 4
    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rounded_rectangle((0, 0, bar_w, bar_h), radius=bar_h // 2, fill=(0, 0, 0, 186))
    rot = selected_index * (360.0 / num_options)
    bar = bar.rotate(-rot, center=(2 * 4, bar_h // 2), expand=True)
    bw, bh = bar.size
    img.paste(bar, (int(cx - bw // 2), int(cy - bh // 2)), bar)

    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    for idx in range(6):
        img = build_dial(90, 6, idx)
        img.save(BASE / f"dial_cw_90_{idx}.png")
    print("90px overlay dials written")