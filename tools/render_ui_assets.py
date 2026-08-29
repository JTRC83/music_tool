"""Generate ALL dial assets for every (format, quality) combination.

The app loads these PNGs with ImageTk and swaps them when the dial rotates.
No Canvas drawing: pure image compositing, which guarantees the look stays
identical to the user's reference screenshot.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent.parent / "assets" / "generated"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONVERSION_FORMATS = ("MP3", "AAC/M4A", "FLAC", "WAV")
QUALITY_OPTIONS = {
    "MP3": ("128k", "192k", "256k", "320k"),
    "AAC/M4A": ("128k", "182k", "256k"),
    "FLAC": ("Compresión 0", "Compresión 4", "Compresión 5", "Compresión 8"),
    "WAV": ("Sin compresión",),
}


def lerp(a, b, t):
    return int(a + (b - a) * t)


def conic_color(deg):
    t = math.cos(math.radians(deg))
    lo, hi = (158, 158, 166), (232, 232, 240)
    return tuple(lerp(lo[i], hi[i], (t + 1) / 2) for i in range(3))


def make_dial_image(size, options, selected_index, label):
    S = size * 4
    img = Image.new("RGBA", (S, S), (240, 240, 240, 255))
    d = ImageDraw.Draw(img)
    cx = cy = S // 2
    R = S // 2 - 12 * 4
    for ang in range(0, 360, 2):
        c = conic_color(ang)
        d.pieslice((cx - R, cy - R, cx + R, cy + R), ang - 2, ang + 1, fill=c)
    for rr in range(R, 4 * 4, -4 * 4):
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(205, 205, 215, 255), width=2)
    d.ellipse((cx - 10 * 4, cy - 10 * 4, cx + 10 * 4, cy + 10 * 4), fill=(40, 40, 40, 255), outline=(20, 20, 20, 255), width=4)
    n = max(len(options), 1)
    step = 360.0 / n
    label_r = R + 10 * 4
    for i, opt in enumerate(options):
        a = math.radians(i * step - 90)
        x1 = cx + math.cos(a) * (R - 2 * 4)
        y1 = cy + math.sin(a) * (R - 2 * 4)
        x2 = cx + math.cos(a) * (R + 4 * 4)
        y2 = cy + math.sin(a) * (R + 4 * 4)
        d.line((x1, y1, x2, y2), fill=(250, 250, 250, 255), width=3 * 4)
        nx = cx + math.cos(a) * label_r
        ny = cy + math.sin(a) * label_r
        sel = (i == selected_index)
        try:
            font = ImageFont.truetype("Helvetica.ttc", 16 * (5 if sel else 4))
        except OSError:
            font = ImageFont.load_default()
        d.text((nx, ny), str(i + 1), fill=(10, 10, 10, 255) if sel else (70, 70, 70, 255),
               font=font, anchor="mm")
    a = math.radians(selected_index * step - 90)
    tip_x = cx + math.cos(a) * (R - 16 * 4)
    tip_y = cy + math.sin(a) * (R - 16 * 4)
    d.line((cx, cy, tip_x, tip_y), fill=(18, 18, 18, 255), width=7 * 4)
    d.ellipse((cx - 6 * 4, cy - 6 * 4, cx + 6 * 4, cy + 6 * 4), fill=(18, 18, 18, 255))
    img = img.resize((size, size), Image.LANCZOS)
    if label:
        strip = Image.new("RGBA", (size, 26), (240, 240, 240, 255))
        sd = ImageDraw.Draw(strip)
        try:
            lbl_font = ImageFont.truetype("Helvetica.ttc", 15)
        except OSError:
            lbl_font = ImageFont.load_default()
        sd.text((size // 2, 13), label, fill=(20, 20, 20, 255), font=lbl_font, anchor="mm")
        combined = Image.new("RGBA", (size, size + 26), (240, 240, 240, 255))
        combined.paste(strip, (0, 0))
        combined.paste(img, (0, 26))
        return combined
    return img


def make_key_image(label, pressed):
    S = 96 * 4
    img = Image.new("RGBA", (S, S), (10, 10, 10, 255))
    d = ImageDraw.Draw(img)
    kw, kh = 84 * 4, 80 * 4
    x1, y1 = (S - kw) // 2, (S - kh) // 2
    y_off = 6 * 4 if pressed else 0
    x2, y2 = x1 + kw, y1 + kh - y_off
    face = (216, 204, 180) if pressed else (232, 220, 196)
    accent = (168, 152, 120)
    d.rounded_rectangle((x1, y1, x2, y2), radius=4 * 4, fill=face, outline=accent, width=3 * 4)
    if pressed:
        d.polygon([(x1 + 8, y2 - 18 * 4), (x2 - 8, y2 - 18 * 4), (x2 - 8, y2 - 8 * 4), (x1 + 8, y2 - 8 * 4)],
                  fill=(184, 172, 148, 255))
        d.polygon([(x1 + 8, y1 + 8), (x2 - 8, y1 + 8), (x2 - 18, y1 - 10), (x1 + 18, y1 - 10)],
                  fill=(222, 210, 186, 255), outline=accent)
        text_col = (37, 138, 195, 255)
    else:
        text_col = (20, 20, 20, 255)
    try:
        font = ImageFont.truetype("Helvetica.ttc", 30 * 4)
    except OSError:
        font = ImageFont.load_default()
    d.text(((x1 + x2) // 2, (y1 + y2) // 2), label, fill=text_col, font=font, anchor="mm")
    d.rectangle((x1, y2 - 6 * 4, x2, y2 - 2 * 4),
                fill=(196, 180, 144, 255) if pressed else (212, 196, 160, 255))
    return img.resize((96 + (6 if pressed else 0), 96), Image.LANCZOS)


def normalize_name(s):
    return s.replace("/", "_").replace(" ", "_").replace("ó", "o").lower()


if __name__ == "__main__":
    for idx, fmt in enumerate(CONVERSION_FORMATS):
        img = make_dial_image(210, CONVERSION_FORMATS, idx, "Formato")
        img.save(OUT_DIR / f"dial_formato_{idx}.png")
    for fmt, qualities in QUALITY_OPTIONS.items():
        fmt_dir = normalize_name(fmt)
        for q_idx, q in enumerate(qualities):
            img = make_dial_image(210, qualities, q_idx, "Calidad")
            img.save(OUT_DIR / f"dial_calidad__{fmt_dir}__{q_idx}.png")
    for label, pressed, name in (
        ("play", False, "play_normal"),
        ("play", True, "play_pressed"),
        ("stop", False, "stop_normal"),
        ("stop", True, "stop_pressed"),
    ):
        img = make_key_image(label, pressed)
        img.save(OUT_DIR / f"key_{name}.png")
    print(f"Generated in {OUT_DIR}")