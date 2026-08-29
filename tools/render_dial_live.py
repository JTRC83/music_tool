"""Live-render the dial with REAL option labels around it (not numbers 1-6).

The dial face is metallic conic; around it we place the actual option strings
("MP3", "AAC/M4A", ... / "128k", "192k", ...) rotated to stay upright. The
needle points to the selected option. This is a one-off preview to verify the
look before integrating into the app.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path("assets/generated")
WIDGET = 170   # bigger so labels like "AAC/M4A" fit around the face
SS = 4
PANEL_RGB = (244, 244, 244)


def metal_color(ang_deg):
    t = (math.cos(math.radians(ang_deg)) + 1) / 2
    return int(150 + t * 82)


def render_dial_live(options, selected_index, widget=WIDGET, label=""):
    S = widget * SS
    img = Image.new("RGBA", (S, S), PANEL_RGB + (255,))
    d = ImageDraw.Draw(img)
    cx = cy = S // 2
    R = int(S * 0.28)

    # metallic face (conic + rings + rim)
    for ang in range(0, 360):
        v = metal_color(ang)
        d.pieslice((cx - R, cy - R, cx + R, cy + R), ang, ang + 1, fill=(v, v, min(255, v + 8)))
    for rr in range(R, 0, -12 * SS):
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 60), width=SS)
    d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(0, 0, 0, 120), width=SS * 2)

    # option labels around the face, evenly spaced starting at RIGHT, clockwise
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12 * SS)
    except OSError:
        font = ImageFont.load_default()
    n = max(len(options), 1)
    label_r = R + 22 * SS
    for i, opt in enumerate(options):
        ang = math.radians(i * (360.0 / n))   # 0deg = right, clockwise
        nx = cx + math.cos(ang) * label_r
        ny = cy + math.sin(ang) * label_r
        sel = (i == selected_index)
        d.text((nx, ny), opt,
               fill=(20, 20, 20, 255) if sel else (90, 90, 90, 255),
               font=font, anchor="mm")

    # needle to selected option
    ang = math.radians(selected_index * (360.0 / n))
    tip_x = cx + math.cos(ang) * (R - 6 * SS)
    tip_y = cy + math.sin(ang) * (R - 6 * SS)
    d.line((cx, cy, tip_x, tip_y), fill=(15, 15, 15, 235), width=6 * SS)
    d.ellipse((cx - 5 * SS, cy - 5 * SS, cx + 5 * SS, cy + 5 * SS), fill=(15, 15, 15, 235))

    # label above the face if requested
    if label:
        try:
            lfont = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14 * SS)
        except OSError:
            lfont = ImageFont.load_default()
        d.text((cx, 18 * SS), label, fill=(30, 30, 30, 255), font=lfont, anchor="mm")

    return img.resize((widget, widget), Image.LANCZOS)


if __name__ == "__main__":
    render_dial_live(("MP3", "AAC/M4A", "FLAC", "WAV"), 0, label="Formato").save(OUT / "dial_live_formato.png")
    render_dial_live(("128k", "192k", "256k", "320k"), 3, label="Calidad").save(OUT / "dial_live_calidad.png")
    # dynamic cases
    render_dial_live(("128k", "182k", "256k"), 1, label="Calidad").save(OUT / "dial_live_aac.png")
    render_dial_live(("Compresión 0", "Compresión 4", "Compresión 5", "Compresión 8"), 2, label="Calidad").save(OUT / "dial_live_flac.png")
    render_dial_live(("Sin compresión",), 0, label="Calidad").save(OUT / "dial_live_wav.png")
    print("live dial previews written")