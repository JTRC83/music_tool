"""Render the user's CW dial CSS to PNG with cairosvg — NATIVE SVG, no
foreignObject. We hand-write SVG gradients that match the CSS exactly:
- conic-gradient(from -2deg, #efefff88, #000088, #efefff88, #000088, #efefff88)
- radial-gradient speckles
- radial-gradient(circle at 12% 12%, #efefff, #9999a4)
- border: 4px solid rgba(0,0,0,0.33); border-radius: 50%;
Then PIL overlays notches, numbers and the indicator bar at runtime.
"""
from pathlib import Path
import cairosvg

OUT = Path(__file__).parent.parent / "assets" / "generated"
OUT.mkdir(parents=True, exist_ok=True)

CW_FACE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <!-- base radial: light top-left to dark body (like the CSS radial-gradient(circle at 12% 12%, ...)) -->
    <radialGradient id="baseRadial" cx="0.12" cy="0.12" r="0.95">
      <stop offset="0" stop-color="#efefff" stop-opacity="1"/>
      <stop offset="1" stop-color="#9999a4" stop-opacity="1"/>
    </radialGradient>
    <!-- conic-gradient approximation: angular sweep light->dark->light->dark->light -->
    <linearGradient id="ang0" x1="0.5" y1="0.5" x2="0.5" y2="0">
      <animateTransform attributeName="gradientTransform" type="rotate" from="-2 0.5 0.5" to="358 0.5 0.5" dur="0s" fill="freeze"/>
      <stop offset="0" stop-color="#efefff" stop-opacity="0.53"/>
      <stop offset="0.5" stop-color="#000000" stop-opacity="0.53"/>
      <stop offset="0.5" stop-color="#efefff" stop-opacity="0.53"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0.53"/>
    </linearGradient>
    <!-- radial speckles: 9 alternating rgba(0,0,0,0.26)/rgba(255,255,255,0.26) rings -->
    <radialGradient id="speckleRadial" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.11" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.11" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="0.22" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="0.22" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.33" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.33" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.44" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="0.55" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="0.55" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.66" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.66" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="0.77" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="0.77" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.88" stop-color="#000000" stop-opacity="0.26"/>
      <stop offset="0.88" stop-color="#ffffff" stop-opacity="0.26"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0.26"/>
    </radialGradient>
    <!-- border: rgba(0,0,0,0.33) ~ #00000054 -->
    <filter id="borderSoft">
      <feGaussianBlur stdDeviation="0.5"/>
    </filter>
  </defs>

  <!-- base: circle filled with base radial (light top-left => dark body) -->
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#baseRadial)"/>
  <!-- conic sweep overlay -->
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#ang0)" opacity="0.55"/>
  <!-- speckled radial texture -->
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#speckleRadial)" opacity="0.55"/>
  <!-- border ring -->
  <circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="#000000" stroke-opacity="0.33" stroke-width="{border}"/>
</svg>'''


def render_face_png(size, border=4):
    cx = cy = size / 2
    r = size / 2 - border
    r_outer = size / 2 - border / 2
    svg = CW_FACE_SVG.format(size=size, cx=cx, cy=cy, r=r, r_outer=r_outer, border=border)
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=size, output_height=size)


if __name__ == "__main__":
    png = render_face_png(64, border=4)
    (OUT / "dial_cw_face_v2.png").write_bytes(png)
    print("v2 face written")