"""Render the user's rb-input (keytar) CSS to PNGs with cairosvg, exact CSS.

rb-input container: background black, padding 6px, border-radius 8px, overflow hidden, height 94px, flex row gap 6px.
rb-label: 70x80px cream #e8dcc4, radius 4px, border-top 1px solid #a89878, flex column, text + bottom line.
rb-back-side: flap above the key (rotated 3D), opacity 0 default, opacity 1 when input:checked.
pressed state: transform perspective rotateX(-18deg), inset box-shadow bottom, border-top blue tint, margin-top 6px, radius 0 0 4 4.
text: uppercase, weight 800, 15px black default; pressed color #258ac3 with glow.
rb-bottom-line: 4px tall, #d4c4a0 normal / #c4b490 pressed.

We render 4 PNGs: play_normal, play_pressed, stop_normal, stop_pressed.
"""
from pathlib import Path
import cairosvg

BASE = Path(__file__).parent.parent / "assets" / "generated"
BASE.mkdir(parents=True, exist_ok=True)

RB_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="190" height="94" viewBox="0 0 190 94">
  <!-- black container -->
  <rect x="0" y="0" width="190" height="94" rx="8" fill="#000000"/>
  <!-- play key (left) -->
  {PLAY_KEY}
  <!-- stop key (right) -->
  {STOP_KEY}
</svg>'''

KEY_TEMPLATE = '''<g transform="translate({x}, {y})">
  <!-- back-side flap (visible when pressed) -->
  {FLAP}
  <!-- key body: cream 70x80 radius 4 -->
  <rect x="0" y="0" width="70" height="80" rx="4" fill="#e8dcc4" stroke="#a89878" stroke-width="1"/>
  <!-- pressed lean effect: darker bottom strip -->
  {PRESSED_SHADE}
  <!-- bottom accent line -->
  <rect x="0" y="76" width="70" height="4" rx="2" fill="{BOTTOM_LINE}"/>
  <!-- key label: uppercase bold -->
  <text x="35" y="46" font-family="Helvetica" font-size="15" font-weight="800" text-anchor="middle" fill="{TEXT_COLOR}" transform="uppercase">{LABEL}</text>
</g>'''

FLAP_NORMAL = ''
FLAP_PRESSED = '''<polygon points="0,8 70,8 62,-10 8,-10" fill="#e8dcc4" stroke="#a89878" stroke-width="1" opacity="0.9"/>
'''

PRESSED_NORMAL = '''<rect x="0" y="66" width="70" height="14" rx="0" fill="rgba(0,0,0,0.05)" opacity="0"/>
'''
PRESSED_PRESSED = '''<rect x="0" y="66" width="70" height="14" rx="0" fill="rgba(0,0,0,0.5)"/>
<rect x="0" y="0" width="70" height="1" fill="#2589c362" stroke-width="1"/>
'''

BOTTOM_NORMAL = "#d4c4a0"
BOTTOM_PRESSED = "#c4b490"

TEXT_NORMAL = "#000000"
TEXT_PRESSED = "#258ac3"


def render_bar(play_pressed=False, stop_pressed=False) -> bytes:
    play_key = KEY_TEMPLATE.format(
        x=12, y=7,
        FLAP=FLAP_PRESSED if play_pressed else FLAP_NORMAL,
        PRESSED_SHADE=PRESSED_PRESSED if play_pressed else PRESSED_NORMAL,
        BOTTOM_LINE=BOTTOM_PRESSED if play_pressed else BOTTOM_NORMAL,
        TEXT_COLOR=TEXT_PRESSED if play_pressed else TEXT_NORMAL,
        LABEL="PLAY",
    )
    stop_key = KEY_TEMPLATE.format(
        x=88, y=7,
        FLAP=FLAP_PRESSED if stop_pressed else FLAP_NORMAL,
        PRESSED_SHADE=PRESSED_PRESSED if stop_pressed else PRESSED_NORMAL,
        BOTTOM_LINE=BOTTOM_PRESSED if stop_pressed else BOTTOM_NORMAL,
        TEXT_COLOR=TEXT_PRESSED if stop_pressed else TEXT_NORMAL,
        LABEL="STOP",
    )
    svg = RB_SVG.format(PLAY_KEY=play_key, STOP_KEY=stop_key)
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=190, output_height=94)


if __name__ == "__main__":
    for pp, sp, name in (
        (False, False, "key_bar_normal"),
        (True, False, "key_bar_play_only"),
        (False, True, "key_bar_stop_only"),
        (True, True, "key_bar_both_pressed"),
    ):
        png = render_bar(pp, sp)
        (BASE / f"{name}.png").write_bytes(png)
    print("keytar bar PNGs written")
