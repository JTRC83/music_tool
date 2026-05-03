#!/usr/bin/env python3
"""Genera vistas previas SVG aproximadas de la interfaz.

Es una ayuda visual de desarrollo: no forma parte de la app real ni añade
dependencias. Tkinter sigue siendo la interfaz verdadera.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WIDTH = 1120
HEIGHT = 820
METAL_DARK = "#8f8f8f"
PANEL_FILL = "#f4f4f4"
DISPLAY_FILL = "#d9dec0"
BLUE = "#2f82df"


def text(x: int, y: int, value: str, size: int = 14, weight: str = "400", color: str = "#1f2933") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{escape(value)}</text>'
    )


def rect(x: int, y: int, w: int, h: int, fill: str, stroke: str = "#c9c9c9", radius: int = 4) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def button(x: int, y: int, w: int, label: str, center: bool = False) -> str:
    tx = x + (w // 2) - 5 if center else x + 12
    return "\n".join(
        [
            rect(x, y, w, 30, "#f9f9f9", "#8f8f8f", 14),
            text(tx, y + 20, label, 14 if center else 13, "700" if center else "500", "#222"),
        ]
    )


def field(x: int, y: int, w: int, label: str = "") -> str:
    return "\n".join(
        [
            rect(x, y, w, 28, "#ffffff", "#a1a1a1", 11),
            text(x + 10, y + 19, label, 12, "400", "#69727d"),
        ]
    )


def group(x: int, y: int, w: int, h: int, title: str) -> str:
    return "\n".join(
        [
            rect(x, y, w, h, PANEL_FILL, METAL_DARK, 30),
            f'<line x1="{x + 18}" y1="{y + 3}" x2="{x + w - 18}" y2="{y + 3}" stroke="#ffffff"/>',
            text(x + 20, y + 5, title, 13, "600", "#2e3338"),
        ]
    )


def header_button(x: int, y: int, w: int, label: str) -> str:
    return "\n".join(
        [
            rect(x, y, w, 36, "url(#buttonChrome)", "#7f7f7f", 18),
            text(x + (w // 2) - 6, y + 24, label, 16, "700", "#2f2f2f"),
        ]
    )


def round_header_button(cx: int, cy: int, label: str) -> str:
    return "\n".join(
        [
            f'<circle cx="{cx}" cy="{cy}" r="24" fill="url(#buttonChrome)" stroke="#7f7f7f" stroke-width="2"/>',
            text(cx - 6, cy + 7, label, 18, "700", "#2f2f2f"),
        ]
    )


def defs() -> list[str]:
    return [
        "<defs>",
        '<linearGradient id="metal" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#d6d6d6"/><stop offset="0.5" stop-color="#b4b4b4"/><stop offset="1" stop-color="#d0d0d0"/></linearGradient>',
        '<linearGradient id="buttonChrome" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="0.52" stop-color="#c8c8c8"/><stop offset="1" stop-color="#f1f1f1"/></linearGradient>',
        '<linearGradient id="tableHeader" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f9f9f9"/><stop offset="1" stop-color="#bdbdbd"/></linearGradient>',
        "</defs>",
    ]


def chrome(active: str) -> list[str]:
    tabs = [("conversion", "Conversion", 52, 128), ("editor", "Editor de cancion", 192, 152), ("url", "YouTube / URL", 360, 132)]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        *defs(),
        rect(0, 0, WIDTH, HEIGHT, "url(#metal)", "#a0a0a0", 0),
        *[f'<line x1="0" y1="{y}" x2="{WIDTH}" y2="{y}" stroke="#eeeeee" opacity="0.28"/>' for y in range(3, HEIGHT, 6)],
        text(532, 28, "Music Tool", 18, "700", "#111111"),
        '<circle cx="212" cy="54" r="24" fill="#dde3c7" stroke="#767c68" stroke-width="2"/>',
        text(202, 55, "MT", 14, "700", "#1d2218"),
        text(201, 68, "audio", 7, "700", "#47503c"),
        round_header_button(284, 54, "▶"),
        '<circle cx="348" cy="54" r="24" fill="url(#buttonChrome)" stroke="#7f7f7f" stroke-width="2"/>',
        '<rect x="340" y="46" width="16" height="16" rx="2" fill="#202020"/>',
        rect(338, 40, 444, 56, DISPLAY_FILL, "#7f8572", 28),
        text(526, 59, "Music Tool", 14, "700", "#1b1b1b"),
        text(506, 75, "Listo", 13, "400", "#1b1b1b"),
        rect(420, 82, 280, 7, "#edf0d5", "#4f5447", 1),
        rect(420, 82, 112, 7, "#2f2f2f", "#2f2f2f", 1),
        rect(846, 39, 192, 42, "#cfe7c8", "#6f9366", 21),
        text(882, 65, "✓", 16, "700", "#2f6e2c"),
        text(916, 65, "Diagnostico", 12, "700", "#173317"),
        rect(42, 112, 1036, 38, "#d4d4d4", "#8d8d8d", 14),
    ]
    for key, label, x, w in tabs:
        if key == active:
            parts.append(rect(x, 118, w, 26, "#f8f8f8", "#8d8d8d", 12))
            color = "#222"
            weight = "600"
        else:
            color = "#444"
            weight = "500"
        parts.append(text(x + 24, 136, label, 13, weight, color))
    return parts


def table(x: int, y: int, w: int, h: int) -> str:
    cols = [("Cancion", 360), ("Formato", 90), ("Peso original", 130), ("Peso final", 120), ("Calidad", 90), ("Estado", 170)]
    out = [rect(x, y, w, h, "#ffffff", METAL_DARK, 18), rect(x, y, w, 32, "url(#tableHeader)", METAL_DARK, 18)]
    cx = x
    for label, col_w in cols:
        out.append(text(cx + 10, y + 21, label, 12, "600", "#333"))
        out.append(f'<line x1="{cx + col_w}" y1="{y}" x2="{cx + col_w}" y2="{y + h}" stroke="#e2e2e2"/>')
        cx += col_w
    rows = [
        ("song_01.flac", "FLAC", "35.4 MB", "-", "320k", "Pendiente"),
        ("song_02.flac", "FLAC", "42.1 MB", "-", "320k", "Pendiente"),
        ("song_03.wav", "WAV", "51.6 MB", "-", "320k", "Pendiente"),
    ]
    for index, row in enumerate(rows):
        yy = y + 58 + (index * 30)
        if index == 1:
            out.append(rect(x + 2, yy - 34, w - 4, 26, BLUE, BLUE, 2))
        out.append(f'<line x1="{x}" y1="{yy - 20}" x2="{x + w}" y2="{yy - 20}" stroke="#eeeeee"/>')
        cx = x
        for value, (_, col_w) in zip(row, cols):
            color = "#ffffff" if index == 1 else "#2f3740"
            out.append(text(cx + 10, yy, value, 12, "400", color))
            cx += col_w
    return "\n".join(out)


def render_conversion() -> str:
    parts = chrome("conversion")
    parts += [
        group(42, 168, 500, 204, "1. Canciones"),
        button(62, 198, 432, "Anadir canciones"),
        button(62, 236, 432, "Quitar seleccionado"),
        button(62, 274, 432, "Vaciar lista"),
        group(578, 168, 500, 204, "2. Salida"),
        button(598, 198, 280, "Seleccionar carpeta"),
        text(598, 246, "Formato", 12, "500"),
        field(698, 226, 160, "AAC/M4A"),
        text(598, 282, "Calidad", 12, "500"),
        field(698, 262, 160, "256k"),
        text(890, 246, "MP3 · AAC/M4A · FLAC · WAV", 12, "400"),
        text(890, 282, "Sobrescribir existentes", 12, "400"),
        table(42, 398, 1036, 196),
        text(50, 624, "Carpeta de salida: sin seleccionar", 12, "400", "#3b3b3b"),
        *log_and_status(),
        "</svg>",
    ]
    return "\n".join(parts)


def render_editor() -> str:
    parts = chrome("editor")
    parts += [
        group(42, 168, 1036, 84, "1. Cancion"),
        button(62, 196, 132, "Cargar cancion"),
        text(220, 216, "song_01.flac", 13, "500"),
        text(62, 238, "Duracion: 4:01 | Peso: 35.4 MB | Bitrate: 911 kbps", 12, "400", "#3b3b3b"),
        group(42, 276, 500, 292, "2. Metadatos"),
        *metadata_fields(64, 306),
        group(578, 276, 500, 292, "3. Edicion y exportacion"),
        *edit_fields(600, 306),
        group(42, 584, 1036, 132, "Edicion visual"),
        rect(64, 614, 992, 44, "#ffffff", "#a1a1a1", 16),
        *wave_lines(84, 646),
        rect(64, 672, 992, 34, "#ffffff", "#a1a1a1", 16),
        rect(64, 674, 130, 30, "#d9d9d9", "#d9d9d9", 8),
        rect(902, 674, 154, 30, "#d9d9d9", "#d9d9d9", 8),
        rect(130, 674, 772, 30, "#eef5ff", "#eef5ff", 8),
        '<polygon points="130,704 240,674 240,704" fill="#c7ddff"/>',
        '<polygon points="792,674 902,704 792,704" fill="#d9c7ff"/>',
        '<line x1="130" y1="688" x2="902" y2="688" stroke="#202020" stroke-width="3"/>',
        text(138, 668, "inicio", 9, "500", "#2f82df"),
        text(838, 668, "fade out", 9, "500", "#64469c"),
        *log_and_status(),
        "</svg>",
    ]
    return "\n".join(parts)


def metadata_fields(x: int, y: int) -> list[str]:
    labels = ["Titulo", "Artista / Grupo", "Album", "Ano", "Genero", "Compositor", "Numero de pista"]
    values = ["Blue Orchid", "The White Stripes", "Get Behind Me Satan", "2005", "Alternative", "", "1"]
    parts: list[str] = []
    for index, (label, value) in enumerate(zip(labels, values)):
        yy = y + (index * 34)
        parts.append(text(x, yy + 19, label, 12, "500"))
        parts.append(field(x + 140, yy, 300, value))
    return parts


def edit_fields(x: int, y: int) -> list[str]:
    rows = [("Inicio", ""), ("Final", ""), ("Fade in", "2"), ("Fade out", "3"), ("Volumen", "1.0"), ("Formato", "MP3"), ("Calidad", "320k")]
    parts: list[str] = []
    for index, (label, value) in enumerate(rows):
        yy = y + (index * 32)
        parts.append(text(x, yy + 19, label, 12, "500"))
        parts.append(field(x + 120, yy, 132, value))
    parts.append(button(x + 286, y, 160, "Seleccionar carpeta"))
    parts.append(button(x + 286, y + 42, 160, "Generar forma"))
    parts.append(button(x + 286, y + 84, 160, "Exportar editada"))
    return parts


def wave_lines(x: int, y: int) -> list[str]:
    parts = []
    heights = [8, 18, 10, 28, 20, 34, 18, 26, 12, 30, 16, 24, 36, 14, 22, 10, 26, 18, 30, 12]
    for index, h in enumerate(heights * 5):
        xx = x + (index * 9)
        parts.append(f'<line x1="{xx}" y1="{y - h // 2}" x2="{xx}" y2="{y + h // 2}" stroke="#111111" stroke-width="3"/>')
    return parts


def render_url() -> str:
    parts = chrome("url")
    parts += [
        group(42, 168, 1036, 88, "1. URL"),
        text(66, 218, "URL", 12, "500"),
        field(122, 198, 910, "https://www.youtube.com/watch?v=..."),
        group(42, 282, 1036, 160, "2. Extraccion de audio"),
        button(66, 312, 170, "Seleccionar carpeta"),
        text(260, 332, "/Users/JoanToni/Music/Descargas", 12, "400", "#3b3b3b"),
        button(66, 364, 190, "Extraer audio"),
        group(42, 468, 1036, 136, "Resultados"),
        rect(64, 500, 992, 32, "url(#tableHeader)", "#8f8f8f", 14),
        text(82, 521, "Archivo", 12, "600", "#333"),
        text(612, 521, "Formato", 12, "600", "#333"),
        text(738, 521, "Peso", 12, "600", "#333"),
        text(858, 521, "Estado", 12, "600", "#333"),
        text(82, 562, "01 - Blue Orchid.m4a", 12, "400", "#2f3740"),
        text(612, 562, "M4A", 12, "400", "#2f3740"),
        text(738, 562, "7.8 MB", 12, "400", "#2f3740"),
        text(858, 562, "Listo", 12, "400", "#2f3740"),
        group(42, 626, 1036, 72, "Uso previsto"),
        text(66, 668, "Funcion pensada para uso personal y local: material propio, con permiso, o contenido que tengas derecho a guardar.", 12, "400", "#333333"),
        *log_and_status(),
        "</svg>",
    ]
    return "\n".join(parts)


def log_and_status() -> list[str]:
    return [
        group(42, 716, 1036, 64, "Registro global"),
        text(58, 750, "Listo. Los procesos y errores apareceran aqui.", 12, "400", "#313941"),
        rect(42, 790, 1036, 22, "#d4d4d4", "#969696", 11),
        text(58, 806, "Listo", 11, "500", "#222"),
    ]


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    files = {
        "ui_preview_conversion.svg": render_conversion(),
        "ui_preview_editor.svg": render_editor(),
        "ui_preview_url.svg": render_url(),
    }
    for name, content in files.items():
        (DOCS / name).write_text(content, encoding="utf-8")
    (DOCS / "ui_preview.svg").write_text(files["ui_preview_conversion.svg"], encoding="utf-8")
    for name in files:
        print(DOCS / name)


if __name__ == "__main__":
    main()
