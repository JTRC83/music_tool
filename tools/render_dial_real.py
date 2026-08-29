"""Render dial assets at REAL widget size with crisp anti-aliasing.

Geometry exactly matches the user's CSS cw-input:
- 6 notches, notch n at angle (n-1)*60deg measured CLOCKWISE from the RIGHT (3 o'clock).
  (CSS: translate(-50%) rotate((n-1)*60deg) translateX(+38px))
- numbers 1..6 counter-rotated so they stay upright, ~12px past the tick
- indicator: black rounded bar from center pointing at the selected notch.
  CSS dial rotate(index*60deg), 0 = pointing right. Selected option maps to index.
- face: conic-gradient brushed metal (light top-left, dark bottom-right sweep),
  thin concentric rings, dark rim border. ALL opaque, 4x supersampled for AA.

Outputs dial_rt_{i}.png at canvas_size px (opaque, blends into PANEL_FILL).
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path("assets/generated")
WIDGET = 140          # final widget px
SS = 4                # supersample for AA
PANEL_RGB = (244, 244, 244)   # PANEL_FILL #f4f4f4 — opaque bg, no halo


def metal_color(ang_deg):
    """Brushed conic metal: brightness oscillates with angle, plus top-left light."""
    t = (math.cos(math.radians(ang_deg)) + 1) / 2         # 0..1 sweep
    base = 150 + t * 82                                    # 150..232
    # top-left highlight bias: brighter near NW
    return int(base)


def draw_face(d, cx, cy, R):
    # conic sweep via thin pieslices
    for ang in range(0, 360):
        v = metal_color(ang)
        d.pieslice((cx - R, cy - R, cx + R, cy + R), ang, ang + 1, fill=(v, v, min(255, v + 8)))
    # concentric ring highlights (few, thick enough to survive downscale)
    for rr in range(R, 0, -10 * SS):
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 60), width=SS)
    # dark rim border (CSS: 4px solid rgba(0,0,0,0.33))
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(0, 0, 0, 120), width=SS * 2)


def draw_notches_numbers(d, cx, cy, R):
    """6 notches starting at RIGHT (3 o'clock), clockwise; numbers upright outside."""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15 * SS)
    except OSError:
        font = ImageFont.load_default()
    tick_r = R + 2 * SS
    num_r = R + 15 * SS
    for i in range(1, 7):
        ang = math.radians((i - 1) * 60)   # 0deg = right, clockwise (PIL y-down)
        # tick: short light line right at the edge
        x1 = cx + math.cos(ang) * (R - 4 * SS)
        y1 = cy + math.sin(ang) * (R - 4 * SS)
        x2 = cx + math.cos(ang) * tick_r
        y2 = cy + math.sin(ang) * tick_r
        d.line((x1, y1, x2, y2), fill=(255, 255, 255, 220), width=int(1.5 * SS))
        # number, counter-rotated -> upright: just place text at radius
        nx = cx + math.cos(ang) * num_r
        ny = cy + math.sin(ang) * num_r
        d.text((nx, ny), str(i), fill=(60, 60, 60, 255), font=font, anchor="mm")


def draw_pointer(d, cx, cy, R, selected_idx):
    """Black rounded bar from center to the selected notch; points right at idx 0."""
    ang = math.radians(selected_idx * 60)
    tip_x = cx + math.cos(ang) * (R - 8 * SS)
    tip_y = cy + math.sin(ang) * (R - 8 * SS)
    # thick bar + center hub
    d.line((cx, cy, tip_x, tip_y), fill=(15, 15, 15, 235), width=6 * SS)
    d.ellipse((cx - 5 * SS, cy - 5 * SS, cx + 5 * SS, cy + 5 * SS), fill=(15, 15, 15, 235))


def make_state(state_index):
    S = WIDGET * SS
    img = Image.new("RGBA", (S, S), PANEL_RGB + (255,))   # opaque panel color, no halo
    d = ImageDraw.Draw(img)
    cx = cy = S // 2
    R = int(S * 0.30)     # face radius: 30% of canvas, leaves margin for outside numbers
    draw_face(d, cx, cy, R)
    draw_notches_numbers(d, cx, cy, R)
    draw_pointer(d, cx, cy, R, state_index)
    return img.resize((WIDGET, WIDGET), Image.LANCZOS)


if __name__ == "__main__":
    for i in range(6):
        make_state(i).save(OUT / f"dial_rt_{i}.png")
    print("real-time dial states written:", WIDGET, "px, opaque bg")
