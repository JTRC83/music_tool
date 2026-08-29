"""Render the user's CW dial CSS to PNG with cairosvg.

This uses the exact CSS/HTML the user sent — no interpretation, no shortcut.
The dial is rendered for a given number of options (the app will use N
positions = len(options), so we generate one PNG per option index).
"""
from pathlib import Path
import cairosvg

OUT = Path(__file__).parent.parent / "assets" / "generated"
OUT.mkdir(parents=True, exist_ok=True)

DIAL_BASE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <style>
      .cw-input {{
        width: {size}px;
        height: {size}px;
        --cw-a: rgba(0,0,0,0.26), rgba(255,255,255,0.26);
        --cw-b: var(--cw-a), var(--cw-a), var(--cw-a);
        --cw-c: var(--cw-b), var(--cw-b), var(--cw-b);
        background:
          conic-gradient(from -2deg, #efefff88, #00000088, #efefff88, #00000088, #efefff88),
          radial-gradient(var(--cw-c), var(--cw-c)),
          radial-gradient(circle at 12% 12%, #efefff, #9999a4);
        border: {border}px solid rgba(0,0,0,0.33);
        border-radius: 50%;
      }}
      .cw-dial {{
        width: 26px; height: 4px; border-radius: 99px;
        background-color: rgba(0,0,0,0.73);
        top: 50%; left: 50%;
        transform-origin: 2px 50%;
        transform: rotate({rotation}deg);
      }}
      .cw-notch {{
        width: 8px; height: 1px; background: rgba(255,255,255,0.8);
        transform: translate(-50%) rotate(calc((var(--cw-n) - 1) * 60deg)) translateX(38px);
      }}
      .cw-notch::before {{ content: counter(section); counter-set: section var(--cw-n);
        transform: translate(12px, -50%) rotate(calc((var(--cw-n) - 1) * -60deg));
        font-size: 12px; color: rgba(255,255,255,0.8);
      }}
    </style>
  </defs>
  <foreignObject width="{size}" height="{size}">
    <div xmlns="http://www.w3.org/1999/xhtml" class="cw-input">
      <div class="cw-notch" style="--cw-n:1"></div>
      <div class="cw-notch" style="--cw-n:2"></div>
      <div class="cw-notch" style="--cw-n:3"></div>
      <div class="cw-notch" style="--cw-n:4"></div>
      <div class="cw-notch" style="--cw-n:5"></div>
      <div class="cw-notch" style="--cw-n:6"></div>
      <div class="cw-dial"></div>
    </div>
  </foreignObject>
</svg>'''


def render_dial_css_png(size, num_options=6, selected_index=0, label=""):
    """Rasterize the user's cw-input CSS to a PNG. selected_index rotates the cw-dial bar."""
    rotation = selected_index * (360.0 / num_options)
    svg = DIAL_BASE_SVG.format(size=size, border=4 if size >= 60 else 2, rotation=rotation)
    return svg


if __name__ == "__main__":
    # Dial PNGs: 6 options, indexes 0..5
    for idx in range(6):
        svg = render_dial_css_png(64, num_options=6, selected_index=idx)
        png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=64, output_height=64)
        (OUT / f"dial_cw_{idx}.png").write_bytes(png)
    print(f"CW dial PNGs written to {OUT}")
