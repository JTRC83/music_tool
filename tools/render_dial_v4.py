"""Final CW dial asset generator, matching the user's reference screenshot exactly.

The user's dial: a metallic circular face with:
- numbers 1..6 spread INSIDE the circle (not outside), around the perimeter
- a thick black horizontal indicator bar that rotates 60deg per selection
- dark border around the face
- small tick marks between numbers

We render 6 states at 96x96, with each state = indicator rotated by idx*60deg from up.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent.parent / "assets" / "generated"
FACE = OUT / "dial_cw_face_v2.png"  # 64x64 metallic face from exact CSS
SIZE = 96
SS = 4


def build_state(idx):
    S = SIZE * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S // 2

    # face: 70% of widget, centered
    face_r = int(S * 0.70) // 2
    face = Image.open(FACE).convert("RGBA").resize((face_r * 2, face_r * 2), Image.LANCZOS)
    img.paste(face, (cx - face_r, cy - face_r), face)

    # numbers INSIDE the circle, at radius face_r - 8px, evenly spaced 60deg apart,
    # starting at top (angle = -90 for position 1, then 60deg steps clockwise)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14 * SS)
    except OSError:
        try:
            font = ImageFont.truetype("Helvetica.ttc", 14 * SS)
        except OSError:
            font = ImageFont.load_default()
    for i in range(1, 7):
        ang = math.radians((i - 1) * 60 - 90)
        tx = cx + math.cos(ang) * (face_r - 8 * SS)
        ty = cy + math.sin(ang) * (face_r - 8 * SS)
        d.text((tx, ty), str(i), fill=(255, 255, 255, 255), font=font, anchor="mm")

    # indicator bar: thick horizontal bar from center pointing right (position 1 default).
    # Rotates by idx*60deg around center. CSS: 26x4, transform-origin 2px left, so we
    # draw a rounded rect that extends right from center.
    bar_len = face_r - 6 * SS
    bar_h = 4 * SS
    bar = Image.new("RGBA", (bar_len + 6 * SS, bar_h + 6 * SS), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    # bar anchored at 6px from left edge so it pivots around center nicely
    bd.rounded_rectangle((3 * SS, 3 * SS, 3 * SS + bar_len, 3 * SS + bar_h), radius=bar_h, fill=(0, 0, 0, 186))
    # rotate around the bar's left-center point
    rot = idx * 60
    bar = bar.rotate(-rot, center=(3 * SS + 2 * SS, 3 * SS + bar_h // 2), expand=True)
    bw, bh = bar.size
    # place so the pivot (2px from left) is at the circle center
    img.paste(bar, (int(cx - bw // 2), int(cy - bh // 2)), bar)

    return img.resize((SIZE, SIZE), Image.LANCZOS)


for i in range(6):
    im = build_state(i)
    im.save(OUT / f"dial_cw_v4_{i}.png")
print("v4 dials written")
