"""Render the CW dial with explicit geometry so it looks right.

Structure (matches the user's screenshot):
- Face: 60x60px metallic disc (conic-gradient + radial speckles + dark border).
  Rendered to PNG already by cairosvg: assets/generated/dial_cw_face_v2.png
- 6 notches: small white 8x1 lines OUTSIDE the face, pointing outward, at 0/60/.../300 deg.
  Numbers 1..6 sit 12px further out than the notch.
- Indicator: a 26x4 black rounded bar anchored at center, rotated to selected*60deg,
  with transform-origin 2px from its left edge (like the CSS).
- Everything composed on a 4x supersampled canvas so it stays crisp.

We output 6 states: dial_cw_state_0.png .. dial_cw_state_5.png
at size=90px so it has room to breathe in the panel.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).parent.parent / "assets" / "generated"
FACE_SRC = BASE / "dial_cw_face_v2.png"
OUT_SIZE = 90
SS = 4  # supersampling


def make_state(state_index, num_options=6):
    S = OUT_SIZE * SS  # 360x360 working canvas
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S // 2

    # ---- face: the cairosvg-rendered metallic disc, sized to fill most of canvas ----
    face = Image.open(FACE_SRC).convert("RGBA").resize((S - 16 * SS, S - 16 * SS), Image.LANCZOS)
    img.paste(face, (8 * SS, 8 * SS), face)  # 8px margin, leaves room for notches/numbers

    # ---- notches: 6 short 8x1 white lines, each just outside the face ----
    label_r = (S // 2) - 10 * SS  # notches go just outside face radius
    num_r = label_r + 12 * SS  # numbers 12px further out
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14 * SS)
    except OSError:
        font = ImageFont.load_default()
    for i in range(1, 7):
        ang = math.radians((i - 1) * 60 - 90)  # notch i: rotate((i-1)*60deg), 0 is up
        # tick mark: 8px long horizontal white line at (distance+1), pointing outward
        tx = cx + math.cos(ang) * label_r
        ty = cy + math.sin(ang) * label_r
        perp = ang + math.pi / 2
        x1 = tx - math.cos(perp) * 4 * SS
        y1 = ty - math.sin(perp) * 4 * SS
        x2 = tx + math.cos(perp) * 4 * SS
        y2 = ty + math.sin(perp) * 4 * SS
        d.line((x1, y1, x2, y2), fill=(255, 255, 255, 210), width=1 * SS)
        # number label
        nx = cx + math.cos(ang) * num_r
        ny = cy + math.sin(ang) * num_r
        d.text((nx, ny), str(i), fill=(255, 255, 255, 210), font=font, anchor="mm")

    # ---- indicator: 26x4 black bar rotated to selected state ----
    # CSS: width 26px, height 4px, transform-origin 2px 50%, rotate(state*60deg).
    bar_w, bar_h = 26 * SS, 4 * SS
    bar = Image.new("RGBA", (bar_w, bar_h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    bd.rounded_rectangle((0, 0, bar_w, bar_h), radius=bar_h // 2, fill=(0, 0, 0, 186))
    # pivot point: 2px from left edge of the bar
    pivot_x, pivot_y = 2 * SS, bar_h // 2
    # rotate around that pivot: easier is rotate(-deg), then translate
    rot_deg = state_index * 60
    bar = bar.rotate(-rot_deg, center=(pivot_x, pivot_y), expand=True)
    bw, bh = bar.size
    # place pivot at center of canvas
    img.paste(bar, (int(cx - pivot_x), int(cy - pivot_y)), bar)

    return img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)


if __name__ == "__main__":
    for idx in range(6):
        img = make_state(idx)
        img.save(BASE / f"dial_cw_state_{idx}.png")
    print("6 dial states written to", BASE)
