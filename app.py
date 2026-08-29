#!/usr/bin/env python3
"""Music Tool - utilidad local ligera para convertir audio."""

from __future__ import annotations

import os
import json
import math
import platform
import shutil
import subprocess
import sys
import threading
from PIL import Image, ImageDraw, ImageFont, ImageTk
from pathlib import Path
from tkinter import BooleanVar, DoubleVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk
import tkinter as tk


APP_NAME = "Music Tool"
SUPPORTED_INPUTS = (".flac", ".mp3", ".wav", ".m4a", ".aac")
MP3_QUALITIES = ("128k", "192k", "256k", "320k")
BITRATE_QUALITIES = ("128k", "192k", "256k", "320k")
FLAC_QUALITIES = ("Compresión 0", "Compresión 4", "Compresión 5", "Compresión 8")
WAV_QUALITIES = ("Sin compresión",)
CONVERSION_FORMATS = ("MP3", "AAC/M4A", "FLAC", "WAV")
EDITOR_OUTPUT_FORMATS = ("MP3",)
QUALITY_OPTIONS = {
    "MP3": MP3_QUALITIES,
    "AAC/M4A": BITRATE_QUALITIES,
    "FLAC": FLAC_QUALITIES,
    "WAV": WAV_QUALITIES,
}
AUDIO_RESULT_EXTENSIONS = (".mp3", ".m4a", ".aac", ".opus", ".ogg", ".webm", ".wav", ".flac")
METADATA_FIELDS = (
    ("title", "Título"),
    ("artist", "Artista / Grupo"),
    ("album", "Álbum"),
    ("date", "Año"),
    ("genre", "Género"),
    ("composer", "Compositor"),
    ("track", "Número de pista"),
)
METAL_BG = "#d0d0d0"
METAL_LIGHT = "#e0e0e0"
METAL_DARK = "#b8b8b8"
PANEL_FILL = "#ececec"
DISPLAY_FILL = "#d9dec0"
DISPLAY_BORDER = "#b8c0a8"
BLUE_SELECTED = "#2f82df"
TEXT_DARK = "#505050"


def base_path() -> Path:
    return Path(__file__).resolve().parent


def find_binary(name: str) -> str | None:
    local = base_path() / "bin" / name
    if local.exists():
        return str(local)
    return shutil.which(name)


def yt_dlp_command_prefix(path: str) -> list[str]:
    """Run local yt-dlp Python bundles with the same Python that runs the app."""
    candidate = Path(path)
    if candidate.is_dir():
        return [sys.executable, str(candidate)]

    try:
        header = candidate.read_bytes()[:256]
    except OSError:
        return [path]

    if header.startswith(b"PK"):
        return [sys.executable, str(candidate)]

    if header.startswith(b"#!"):
        first_line = header.splitlines()[0].decode("utf-8", errors="ignore").lower()
        if "python" in first_line:
            return [sys.executable, str(candidate)]

    mach_o_headers = (b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe")
    if header.startswith(mach_o_headers):
        return [path]

    return [path]


def js_runtime_flags() -> list[str]:
    """Build yt-dlp --js-runtimes flags for an available JavaScript runtime.

    YouTube extraction without a JS runtime is deprecated and returns
    HTTP 403 for several formats. Deno is the lightest option and ships as
    a single binary, which suits old machines. Node/phantomjs are also
    accepted by yt-dlp if present on PATH.
    """
    deno = find_binary("deno")
    if deno and os.access(deno, os.X_OK):
        return ["--js-runtimes", f"deno:{deno}"]

    node = shutil.which("node")
    if node and os.access(node, os.X_OK):
        return ["--js-runtimes", f"node:{node}"]

    return []


def js_runtime_label() -> str:
    """Short human label for the detected JS runtime, for diagnostics/logs."""
    deno = find_binary("deno")
    if deno and os.access(deno, os.X_OK):
        return f"deno ({deno})"
    node = shutil.which("node")
    if node and os.access(node, os.X_OK):
        return f"node ({node})"
    return "ninguno (YouTube puede devolver 403)"


def format_size(path: str | Path) -> str:
    size = Path(path).stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def size_change_percent(original: str | Path, final: str | Path) -> str:
    original_size = Path(original).stat().st_size
    final_size = Path(final).stat().st_size
    if original_size <= 0:
        return "0.0%"
    change = (1 - (final_size / original_size)) * 100
    return f"{change:.1f}%"


def format_duration(seconds_value: str | float | int | None) -> str:
    try:
        total = int(float(seconds_value or 0))
    except (TypeError, ValueError):
        return "-"
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_bitrate(value: str | int | None) -> str:
    try:
        bitrate = int(value or 0)
    except (TypeError, ValueError):
        return "-"
    if bitrate <= 0:
        return "-"
    return f"{bitrate // 1000} kbps"


def parse_time_value(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            minutes, seconds = parts
            return (int(minutes) * 60) + float(seconds)
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    except ValueError as exc:
        raise ValueError(f"Formato de tiempo no válido: {value}") from exc
    raise ValueError(f"Formato de tiempo no válido: {value}")


def parse_optional_float(value: str, label: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{label} debe ser numérico.") from exc


def compact_seconds(value: float) -> str:
    if abs(value - round(value)) < 0.01:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def conversion_extension(format_name: str) -> str:
    return {
        "MP3": ".mp3",
        "AAC/M4A": ".m4a",
        "FLAC": ".flac",
        "WAV": ".wav",
    }.get(format_name, ".mp3")


def flac_compression_value(label: str) -> str:
    return label.replace("Compresión", "").strip() or "5"


def read_audio_info(path: str) -> dict[str, object]:
    ffprobe = find_binary("ffprobe")
    if not ffprobe:
        raise RuntimeError("No se ha encontrado ffprobe. Añádelo a bin/ o al PATH.")
    if not os.access(ffprobe, os.X_OK):
        raise RuntimeError(f"ffprobe no tiene permisos de ejecución:\n{ffprobe}")

    command = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"No se pudo ejecutar ffprobe: {exc}") from exc

    if result.returncode != 0:
        error = result.stderr.strip() or "FFprobe falló sin mensaje de error."
        raise RuntimeError(error)

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"FFprobe devolvió datos no válidos: {exc}") from exc

    audio_stream = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "audio"), {})
    file_format = data.get("format", {})
    tags = file_format.get("tags", {}) or {}

    return {
        "duration": file_format.get("duration") or audio_stream.get("duration"),
        "bitrate": file_format.get("bit_rate") or audio_stream.get("bit_rate"),
        "tags": {str(key).lower(): str(value) for key, value in tags.items()},
    }


def draw_rounded_rect(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    *,
    fill: str,
    outline: str,
    width: int = 1,
    tags: str = "panel",
) -> None:
    radius = max(2, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = (
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    )
    canvas.create_polygon(points, smooth=True, fill=fill, outline=outline, width=width, tags=tags)


def draw_capsule(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    fill: str,
    outline: str,
    width: int = 1,
    tags: str = "pill",
) -> None:
    height = max(2, y2 - y1)
    radius = height // 2
    left_x2 = x1 + height
    right_x1 = x2 - height

    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, fill=fill, outline="", tags=tags)
    canvas.create_oval(x1, y1, left_x2, y2, fill=fill, outline="", tags=tags)
    canvas.create_oval(right_x1, y1, x2, y2, fill=fill, outline="", tags=tags)

    canvas.create_arc(x1, y1, left_x2, y2, start=90, extent=180, style=tk.ARC, outline=outline, width=width, tags=tags)
    canvas.create_arc(right_x1, y1, x2, y2, start=-90, extent=180, style=tk.ARC, outline=outline, width=width, tags=tags)
    canvas.create_line(x1 + radius, y1, x2 - radius, y1, fill=outline, width=width, tags=tags)
    canvas.create_line(x1 + radius, y2, x2 - radius, y2, fill=outline, width=width, tags=tags)


class RoundedSection(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        title: str = "",
        radius: int = 36,
        padding: int = 20,
        min_height: int = 120,
        min_width: int | None = None,
    ) -> None:
        super().__init__(master, bg=METAL_BG, highlightthickness=0, bd=0)
        self.title = title
        self.radius = radius
        self.padding = padding
        canvas_options: dict[str, object] = {
            "bg": METAL_BG,
            "height": min_height,
            "highlightthickness": 0,
            "bd": 0,
        }
        if min_width is not None:
            canvas_options["width"] = min_width
        self.canvas = tk.Canvas(self, **canvas_options)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.content = tk.Frame(self.canvas, bg=PANEL_FILL, highlightthickness=0, bd=0)
        self.window_id = self.canvas.create_window(0, 0, window=self.content, anchor=tk.NW)
        self.canvas.bind("<Configure>", self._redraw)

    def _redraw(self, event: tk.Event) -> None:
        width = max(int(event.width), 24)
        height = max(int(event.height), 24)
        title_height = 24 if self.title else 10
        self.canvas.delete("panel")

        draw_rounded_rect(
            self.canvas,
            2,
            8,
            width - 2,
            height - 2,
            self.radius,
            fill=PANEL_FILL,
            outline=METAL_DARK,
            width=1,
        )
        self.canvas.create_line(20, 10, width - 22, 10, fill="#ffffff", tags="panel")
        if self.title:
            self.canvas.create_text(
                18,
                18,
                text=self.title,
                anchor=tk.W,
                font=("Helvetica", 12, "bold"),
                fill=TEXT_DARK,
                tags="panel",
            )
        self.canvas.tag_lower("panel")

        x = self.padding
        y = title_height + 4
        self.canvas.coords(self.window_id, x, y)
        self.canvas.itemconfigure(
            self.window_id,
            width=max(width - (self.padding * 2), 20),
            height=max(height - y - self.padding, 20),
        )


class PillButton(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        text: str,
        command: object,
        *,
        width: int = 180,
        fill: str = "#d8e8fb",
        active_fill: str = "#b9d5f3",
        outline: str = "#7da8d6",
        foreground: str = "#809880",
    ) -> None:
        self.button_height = 30
        self.button_radius = 60
        try:
            background = str(master.cget("bg"))
        except tk.TclError:
            background = PANEL_FILL
        super().__init__(
            master,
            width=width,
            height=self.button_height,
            bg=background,
            highlightthickness=0,
            bd=0,
            cursor="pointinghand",
        )
        self.text = text
        self.command = command
        self.fill = fill
        self.active_fill = active_fill
        self.outline = outline
        self.foreground = foreground
        self.is_pressed = False
        self.bind("<Configure>", self._redraw)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Leave>", self._leave)

    def _redraw(self, _event: tk.Event | None = None) -> None:
        width = max(int(self.winfo_width()), 40)
        fill = self.active_fill if self.is_pressed else self.fill
        self.delete("all")
        draw_capsule(
            self,
            1,
            1,
            width - 1,
            self.button_height - 1,
            fill=fill,
            outline=self.outline,
            width=1,
            tags="pill",
        )
        self.create_text(
            width // 2,
            self.button_height // 2,
            text=self.text,
            font=("Helvetica", 10, "bold"),
            fill=self.foreground,
            tags="pill",
        )

    def _press(self, _event: tk.Event) -> None:
        self.is_pressed = True
        self._redraw()

    def _release(self, event: tk.Event) -> None:
        was_pressed = self.is_pressed
        self.is_pressed = False
        self._redraw()
        if was_pressed and 0 <= int(event.x) <= int(self.winfo_width()) and 0 <= int(event.y) <= self.button_height:
            self.command()

    def _leave(self, _event: tk.Event) -> None:
        if self.is_pressed:
            self.is_pressed = False
            self._redraw()


def _normalize_asset_name(s: str) -> str:
    return (
        s.replace("/", "_")
        .replace(" ", "_")
        .replace("ó", "o")
        .lower()
    )


def _dial_asset_path(prefix: str, category: str, index: int) -> Path:
    """Resolve a dial PNG: assets/generated/dial_{prefix}[__{category}]__{index}.png
    For Formato: prefix='formato', category='', index=0..3.
    For Calidad: prefix='calidad', category=normalized(fmt), index=0..len(qualities)-1."""
    if category:
        return base_path() / "assets" / "generated" / f"dial_{prefix}__{category}__{index}.png"
    return base_path() / "assets" / "generated" / f"dial_{prefix}_{index}.png"


class DialButton(tk.Canvas):
    """Rotary dial that renders itself on the fly with REAL option labels.

    Around the metallic face we show the actual options ("MP3", "AAC/M4A", ... /
    "128k", "192k", ...) evenly spaced, with the selected one in bold. A needle
    points at the selection. No prefabricated PNGs — every state is rendered
    with PIL at 4x supersampling so the text stays crisp at any size.
    """

    WIDGET = 170        # canvas px
    SS = 4               # supersampling factor
    FACE_RATIO = 0.28   # face radius as fraction of canvas

    def __init__(
        self,
        master: tk.Widget,
        options: tuple[str, ...],
        variable: StringVar,
        *,
        asset_prefix: str = "",
        asset_category: str = "",
        label: str = "",
    ) -> None:
        self.label_text = label
        try:
            background = str(master.cget("bg"))
        except tk.TclError:
            background = PANEL_FILL
        super().__init__(
            master, width=self.WIDGET, height=self.WIDGET + 18, bg=background,
            highlightthickness=0, bd=0, cursor="pointinghand",
        )
        self.options = tuple(options)
        self.variable = variable
        self.cx = self.WIDGET // 2
        self.cy = self.WIDGET // 2 + 9   # leave room for the label on top
        self._photo: ImageTk.PhotoImage | None = None
        self.variable.trace_add("write", lambda *_args: self._redraw())
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._handle_click)
        self.bind("<B1-Motion>", self._handle_click)
        self._redraw()

    def _index_of(self, val: str) -> int:
        try:
            return self.options.index(val)
        except ValueError:
            return 0

    def set_options(self, options: tuple[str, ...], *, category: str = "") -> None:
        self.options = tuple(options)
        self._redraw()

    def _metal_color(self, ang_deg: float) -> tuple[int, int, int]:
        t = (math.cos(math.radians(ang_deg)) + 1) / 2
        v = int(150 + t * 82)
        return (v, v, min(255, v + 8))

    def _render(self, selected_index: int) -> ImageTk.PhotoImage:
        S = self.WIDGET * self.SS
        img = Image.new("RGBA", (S, S), (244, 244, 244, 255))
        d = ImageDraw.Draw(img)
        cx = cy = S // 2
        R = int(S * self.FACE_RATIO)
        # metallic face: conic sweep
        for ang in range(0, 360):
            d.pieslice((cx - R, cy - R, cx + R, cy + R), ang, ang + 1, fill=self._metal_color(ang))
        # concentric rings
        for rr in range(R, 0, -12 * self.SS):
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 60), width=self.SS)
        # rim
        d.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(0, 0, 0, 120), width=self.SS * 2)

        # option labels around the face, starting at RIGHT, clockwise
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12 * self.SS)
        except OSError:
            font = ImageFont.load_default()
        n = max(len(self.options), 1)
        label_r = R + 22 * self.SS
        for i, opt in enumerate(self.options):
            ang = math.radians(i * (360.0 / n))
            nx = cx + math.cos(ang) * label_r
            ny = cy + math.sin(ang) * label_r
            sel = (i == selected_index)
            d.text((nx, ny), opt,
                   fill=(20, 20, 20, 255) if sel else (90, 90, 90, 255),
                   font=font, anchor="mm")

        # needle: a short dash from the OUTER edge inward (~35% of radius length)
        if self.options:
            ang = math.radians(selected_index * (360.0 / n))
            outer_r = R - 4 * self.SS
            inner_r = int(R * 0.65)
            x1 = cx + math.cos(ang) * outer_r
            y1 = cy + math.sin(ang) * outer_r
            x2 = cx + math.cos(ang) * inner_r
            y2 = cy + math.sin(ang) * inner_r
            d.line((x1, y1, x2, y2), fill=(40, 40, 40, 240), width=5 * self.SS)
            d.ellipse((cx - 4 * self.SS, cy - 4 * self.SS, cx + 4 * self.SS, cy + 4 * self.SS),
                      fill=(40, 40, 40, 240))

        img = img.resize((self.WIDGET, self.WIDGET), Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    def _handle_click(self, event: tk.Event) -> None:
        dx = int(event.x) - self.cx
        dy = int(event.y) - self.cy
        dist = math.hypot(dx, dy)
        # face radius in widget coords: ~28% of 170 = 48px; clicks inside do nothing
        if dist <= 50:
            return
        angle = math.degrees(math.atan2(dy, dx))
        n = max(len(self.options), 1)
        step = 360.0 / n
        idx = int(round(angle / step)) % n
        self.variable.set(self.options[idx])

    def _redraw(self) -> None:
        self.delete("all")
        if not self.options:
            return
        current = self.variable.get()
        idx = self._index_of(current)
        # re-render every time the selection changes (cheap at 170px)
        self._photo = self._render(idx)
        self.create_image(self.cx, self.cy, image=self._photo, anchor=tk.CENTER, tags="dial")
        # label above the dial
        if self.label_text:
            self.create_text(
                self.cx, 10, text=self.label_text,
                font=("Helvetica", 10, "bold"), fill=TEXT_DARK, tags="dial",
            )
        # value text under the dial so the user always sees what's selected
        if current:
            self.create_text(
                self.cx, self.WIDGET + 12, text=current,
                font=("Helvetica", 10, "bold"), fill="#aaaaaa", tags="dial",
            )


class ITunesHeader(tk.Canvas):
    def __init__(
        self,
        master: tk.Widget,
        status_var: StringVar,
        progress_var: DoubleVar,
        start_command: object,
        stop_command: object,
        diagnostics_command: object,
    ) -> None:
        super().__init__(master, height=200, bg=METAL_BG, highlightthickness=0, bd=0)
        self.status_var = status_var
        self.progress_var = progress_var
        self.start_command = start_command
        self.stop_command = stop_command
        self.diagnostics_command = diagnostics_command
        self.logo_photo = self._load_logo()
        self.pressed_tag: str | None = None
        self.button_bounds: dict[str, tuple[int, int, int, int]] = {}
        self._stripe_offset = 0          # animated stripe offset for the loader
        self._stripe_anim_id: str | None = None
        self.status_var.trace_add("write", self._status_changed)
        self.progress_var.trace_add("write", self._status_changed)
        self.bind("<Configure>", self._redraw)
        self.bind("<ButtonRelease-1>", self._release_pressed)
        self.tag_bind("start_button", "<ButtonPress-1>", lambda _event: self._press("start_button"))
        self.tag_bind("stop_button", "<ButtonPress-1>", lambda _event: self._press("stop_button"))
        self.tag_bind("diagnostics_button", "<ButtonPress-1>", lambda _event: self._press("diagnostics_button"))
        self.tag_bind("start_button", "<Enter>", lambda _event: self.configure(cursor="pointinghand"))
        self.tag_bind("stop_button", "<Enter>", lambda _event: self.configure(cursor="pointinghand"))
        self.tag_bind("diagnostics_button", "<Enter>", lambda _event: self.configure(cursor="pointinghand"))
        self.tag_bind("start_button", "<Leave>", lambda _event: self._leave_button())
        self.tag_bind("stop_button", "<Leave>", lambda _event: self._leave_button())
        self.tag_bind("diagnostics_button", "<Leave>", lambda _event: self._leave_button())

    def _load_logo(self) -> ImageTk.PhotoImage | None:
        logo_path = base_path() / "assets" / "app_icon.png"

        if not logo_path.exists():
            return None

        try:
            target_size = 150

            image = Image.open(logo_path).convert("RGBA")

            # Recorta márgenes transparentes
            alpha = image.getchannel("A")
            bbox = alpha.getbbox()

            if bbox:
                image = image.crop(bbox)

            # Redimensionado de alta calidad
            image = image.resize(
                (target_size, target_size),
                Image.Resampling.LANCZOS
            )

            return ImageTk.PhotoImage(image)

        except Exception as exc:
            print(exc)
            return None

    def _press(self, tag: str) -> None:
        self.pressed_tag = tag
        self._paint(max(self.winfo_width(), 620))

    def _release_pressed(self, event: tk.Event) -> None:
        tag = self.pressed_tag
        if not tag:
            return
        self.pressed_tag = None
        run_command = self._point_inside_button(tag, int(event.x), int(event.y))
        self._paint(max(self.winfo_width(), 620))
        if not run_command:
            return
        if tag == "start_button":
            self.start_command()
        elif tag == "stop_button":
            self.stop_command()
        elif tag == "diagnostics_button":
            self.diagnostics_command()

    def _point_inside_button(self, tag: str, x: int, y: int) -> bool:
        bounds = self.button_bounds.get(tag)
        if not bounds:
            return False
        x1, y1, x2, y2 = bounds
        return x1 <= x <= x2 and y1 <= y <= y2

    def _leave_button(self) -> None:
        self.configure(cursor="")

    def _animate_stripes(self) -> None:
        """Move the white diagonal stripes on the loader bar, iTunes style."""
        self._stripe_offset = (self._stripe_offset + 3) % 36
        self._stripe_anim_id = self.after(50, self._animate_stripes)
        self._paint(max(self.winfo_width(), 620))

    def _status_changed(self, *_args: object) -> None:
        self._paint(max(self.winfo_width(), 620))

    def _redraw(self, event: tk.Event) -> None:
        self._paint(max(int(event.width), 620))

    def _paint(self, width: int) -> None:
        self.delete("all")

        for y in range(0, 200, 3):
            color = "#d8d8d8" if y % 6 == 0 else "#c0c0c0"
            self.create_line(0, y, width, y, fill=color)

        header_center_y = 103

        self.create_text(
            width // 2,
            34,
            text=APP_NAME,
            font=("Helvetica", 16, "bold"),
            fill="#a0a0a0",
        )

        display_w = min(470, max(340, width - 700))
        display_x = (width - display_w) // 2

        button_y = header_center_y
        # Buttons sit to the LEFT of the display, like the original layout.
        start_x = display_x - 150
        stop_x = start_x + 76
        logo_x = start_x - 145

        start_pressed = self.pressed_tag == "start_button"
        stop_pressed = self.pressed_tag == "stop_button"

        def draw_round_button(cx: int, pressed: bool, tag: str, icon: str) -> None:
            """Round metallic button with real 3D bevel and drop shadow."""
            r = 32
            oy = 2 if pressed else 0   # vertical offset when pressed (sinks in)
            # 1. drop shadow (soft, only when not pressed)
            if not pressed:
                self.create_oval(
                    cx - r + 3, button_y - r + 4, cx + r + 3, button_y + r + 4,
                    fill="#c8c8c8", outline="", tags=tag,
                )
            # 2. outer rim (light grey, not dark)
            self.create_oval(
                cx - r, button_y - r + oy, cx + r, button_y + r + oy,
                fill="#c0c0c0", outline="#c0c0c0", width=1, tags=tag,
            )
            # 3. metallic ring (lighter, inset 3px)
            self.create_oval(
                cx - r + 3, button_y - r + 3 + oy, cx + r - 3, button_y + r - 3 + oy,
                fill="#e0e0e0" if not pressed else "#d0d0d0",
                outline="#c8c8c8", width=1, tags=tag,
            )
            # 4. inner face (pale, inset 6px)
            face_fill = "#f8f8f6" if not pressed else "#e8e8e6"
            self.create_oval(
                cx - r + 6, button_y - r + 6 + oy, cx + r - 6, button_y + r - 6 + oy,
                fill=face_fill, outline="#c0c0c0", width=1, tags=tag,
            )
            # 5. top highlight arc (glossy reflection, top-left only)
            self.create_arc(
                cx - r + 8, button_y - r + 8 + oy, cx + r - 8, button_y + r - 8 + oy,
                start=20, extent=130, outline="#ffffff", width=3, style=tk.ARC, tags=tag,
            )
            # 6. icon drawn as a polygon (play triangle) or rectangle (stop square),
            #    both geometrically centered on (cx, button_y) — no font offsets.
            if icon == "■":
                # stop: square 22x22 centered
                hs = 11
                self.create_rectangle(
                    cx - hs, button_y - hs + oy, cx + hs, button_y + hs + oy,
                    fill="#1a1a1a", outline="#1a1a1a", width=1, tags=tag,
                )
            else:
                # play: equilateral-ish triangle pointing right, centered
                # vertices: left-center, top-right, bottom-right
                tw = 14   # half-width
                th = 13   # half-height
                self.create_polygon(
                    cx - tw + 1, button_y - th + oy,   # top-left
                    cx - tw + 1, button_y + th + oy,   # bottom-left
                    cx + tw, button_y + oy,             # right point
                    fill="#1a1a1a", outline="#1a1a1a", smooth=False, tags=tag,
                )
            self.button_bounds[tag] = (cx - r, button_y - r, cx + r, button_y + r)

        draw_round_button(start_x, start_pressed, "start_button", "▶")
        draw_round_button(stop_x, stop_pressed, "stop_button", "■")

        if self.logo_photo:
            self.create_image(logo_x, button_y, image=self.logo_photo, tags="logo")

        draw_rounded_rect(
            self,
            display_x,
            56,
            display_x + display_w,
            148,
            26,
            fill=DISPLAY_FILL,
            outline=DISPLAY_BORDER,
            width=2,
            tags="display",
        )
        self.create_text(
            display_x + display_w // 2,
            78,
            text=self.status_var.get(),
            font=("Helvetica", 13, "bold"),
            fill="#909090",
        )
        # ----- iTunes-style loader bar (replaces the old green progress bar) -----
        # Dark rounded background (#212121) only shown when there IS progress,
        # orange-to-yellow gradient fill grows with progress_var, animated white
        # diagonal stripes on top. Bigger border radius on the ends.
        try:
            progress = max(0.0, min(1.0, float(self.progress_var.get())))
        except (tk.TclError, ValueError):
            progress = 0.0

        lb_y1 = 112
        lb_y2 = 138
        lb_x1 = display_x + 30
        lb_x2 = display_x + display_w - 30
        lb_h = lb_y2 - lb_y1
        lb_r = lb_h // 2 + 4   # extra border radius on the ends

        # dark rounded background — always visible (empty bar at idle, fills when working)
        draw_rounded_rect(
            self, lb_x1, lb_y1, lb_x2, lb_y2, lb_r,
            fill="#212121", outline="#909090", width=1, tags="loader",
        )

        # gradient fill: orange (#de4a0f) bottom → yellow (#f9c74f) top
        fill_w = int((lb_x2 - lb_x1 - 10) * progress)
        if fill_w > 4:
            fill_x1 = lb_x1 + 5
            fill_y1 = lb_y1 + 5
            fill_x2 = fill_x1 + fill_w
            fill_y2 = lb_y2 - 5
            fill_r = (fill_y2 - fill_y1) // 2
            # simulate vertical gradient with horizontal strips
            for gy in range(fill_y1, fill_y2):
                t = (gy - fill_y1) / max(fill_y2 - fill_y1, 1)
                r = int(222 + (249 - 222) * t)
                g = int(74 + (199 - 74) * t)
                b = int(15 + (79 - 15) * t)
                self.create_line(fill_x1, gy, fill_x2, gy, fill=f"#{r:02x}{g:02x}{b:02x}", tags="loader")
            # round the fill ends
            draw_rounded_rect(
                self, fill_x1, fill_y1, fill_x2, fill_y2, fill_r,
                fill="", outline="", width=0, tags="loader",
            )
            # animated white diagonal stripes (3 stripes, moving right)
            stripe_w = 8
            stripe_gap = 18
            for i in range(-1, (fill_w // stripe_gap) + 2):
                sx = fill_x1 + (i * stripe_gap + self._stripe_offset) % (fill_w + stripe_gap)
                if sx + stripe_w > fill_x1 and sx < fill_x2:
                    self.create_polygon(
                        sx, fill_y1, sx + stripe_w, fill_y1,
                        sx + stripe_w - 12, fill_y2, sx - 12, fill_y2,
                        fill="#ffffff", outline="", tags="loader",
                    )
                    self.create_polygon(
                        sx, fill_y1, sx + stripe_w, fill_y1,
                        sx + stripe_w - 12, fill_y2, sx - 12, fill_y2,
                        fill="", outline="", tags="loader",
                    )
            # clip stripes to the rounded fill with a mask outline
            draw_rounded_rect(
                self, fill_x1, fill_y1, fill_x2, fill_y2, fill_r,
                fill="", outline="#212121", width=2, tags="loader",
            )

        # start / continue the stripe animation when progress > 0
        if progress > 0 and self._stripe_anim_id is None:
            self._animate_stripes()
        elif progress <= 0 and self._stripe_anim_id is not None:
            self.after_cancel(self._stripe_anim_id)
            self._stripe_anim_id = None

        search_w = 112
        search_x = width - search_w - 56
        self.button_bounds["diagnostics_button"] = (search_x, 72, search_x + search_w, 102)
        diagnostic_pressed = self.pressed_tag == "diagnostics_button"
        draw_capsule(
            self,
            search_x,
            72,
            search_x + search_w,
            102,
            fill="#cfe7c8" if not diagnostic_pressed else "#b9dcae",
            outline="#6f9366",
            width=2,
            tags="diagnostics_button",
        )
        self.create_text(
            search_x + search_w // 2,
            88,
            text="Diagnóstico",
            font=("Helvetica", 10, "bold"),
            fill="#809880",
            tags="diagnostics_button",
        )


class MusicToolApp(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1280x980")
        self.minsize(1180, 900) 

        self.files: list[str] = []
        self.output_dir = StringVar(value="")
        self.output_format = StringVar(value="MP3")
        self.quality = StringVar(value="320k")
        self.overwrite = BooleanVar(value=False)
        self.status = StringVar(value="Listo")
        self.progress = DoubleVar(value=0.0)
        self.is_converting = False
        self.cancel_requested = threading.Event()
        self.current_process = None
        self.editor_path: str | None = None
        self.editor_duration_seconds: float | None = None
        self.editor_output_dir = StringVar(value="")
        self.editor_overwrite = BooleanVar(value=False)
        self.is_exporting_editor = False
        self.is_generating_waveform = False
        self.waveform_photo = None
        self.waveform_label = None
        self.edit_visual_canvas = None
        self.editor_drag_target = None
        self.editor_visual_handles: dict[str, int] = {}
        self.editor_visual_geometry: tuple[int, int, float] | None = None
        self.editor_file = StringVar(value="Sin canción cargada")
        self.editor_info = StringVar(value="Duración: - | Peso: - | Bitrate: -")
        self.editor_output_format = StringVar(value="MP3")
        self.editor_quality = StringVar(value="320k")
        self.editor_metadata_vars: dict[str, StringVar] = {}
        self.editor_metadata_entries: dict[str, ttk.Entry] = {}
        self.original_editor_metadata: dict[str, str] = {}
        self.url_value = StringVar(value="")
        self.url_output_dir = StringVar(value="")
        self.url_results_table = None
        self.is_extracting_url = False

        self._configure_style()
        self._build_ui()
        self.output_format.trace_add("write", self._on_conversion_format_change)
        self._update_conversion_quality_options()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
        style.configure("TFrame", background=METAL_BG, padding=8)
        style.configure("TLabel", background=PANEL_FILL, foreground=TEXT_DARK)
        style.configure("TCheckbutton", background=PANEL_FILL, foreground=TEXT_DARK)
        style.configure("TButton", padding=(10, 5))
        style.configure("Status.TLabel", background=METAL_LIGHT, foreground=TEXT_DARK, padding=(10, 5))
        style.configure("TNotebook", background=METAL_BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 6))
        style.configure("Treeview", rowheight=24, fieldbackground="#ffffff", background="#ffffff")
        style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
        style.configure("TEntry", fieldbackground="#ffffff", borderwidth=0, padding=4)
        style.configure("TCombobox", fieldbackground="#ffffff", background=PANEL_FILL, borderwidth=0, padding=4)

    def _action_button(
        self,
        master: tk.Widget,
        text: str,
        command: object,
        *,
        width: int = 180,
        tone: str = "blue",
    ) -> PillButton:
        colors = {
            "blue": ("#3667e8", "#4070d0", "#4070d0", "#ffffff"),
            "green": ("#d7ead2", "#bdddb6", "#6f9366", "#809880"),
            "silver": ("#f2f2f2", "#dedede", "#b8b8b8", "#b0b0b0"),
        }
        fill, active_fill, outline, fg = colors.get(tone, colors["blue"])
        return PillButton(
            master,
            text=text,
            command=command,
            width=width,
            fill=fill,
            active_fill=active_fill,
            outline=outline,
            foreground=fg,
        )

    def _configure_table_stripes(self, table: ttk.Treeview) -> None:
        table.tag_configure("stripe_even", background="#ffffff")
        table.tag_configure("stripe_odd", background="#edf4ff")

    def _apply_table_stripes(self, table: ttk.Treeview) -> None:
        for index, item in enumerate(table.get_children()):
            tag = "stripe_odd" if index % 2 else "stripe_even"
            table.item(item, tags=(tag,))

    def _build_ui(self) -> None:
        self.configure(bg=METAL_BG)
        root = tk.Frame(self, bg=METAL_BG, padx=12, pady=10, highlightthickness=0, bd=0)
        root.pack(fill=tk.BOTH, expand=True)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)

        self.header = ITunesHeader(root, self.status, self.progress, self.start_conversion, self.cancel_conversion, self.show_diagnostics)
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        notebook = ttk.Notebook(root)
        notebook.grid(row=1, column=0, sticky="nsew")

        self.conversion_tab = ttk.Frame(notebook)
        self.editor_tab = ttk.Frame(notebook)
        self.url_tab = ttk.Frame(notebook)

        notebook.add(self.conversion_tab, text="Conversión")
        notebook.add(self.editor_tab, text="Editor de canción")
        notebook.add(self.url_tab, text="YouTube / URL")

        self._build_conversion_tab()
        self._build_editor_tab()
        self._build_url_tab()

        self._build_global_log(root)

        ttk.Label(root, textvariable=self.status, style="Status.TLabel", anchor=tk.W).grid(
            row=3, column=0, sticky="ew", pady=(6, 0)
        )

    def _build_conversion_tab(self) -> None:
        self.conversion_tab.columnconfigure(0, weight=1)
        self.conversion_tab.rowconfigure(1, weight=1)

        controls = tk.Frame(self.conversion_tab, bg=METAL_BG, highlightthickness=0, bd=0)
        controls.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 8))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(3, weight=1)

        songs_panel = RoundedSection(controls, "1. Canciones", min_height=230, min_width=340)
        songs_panel.grid(row=0, column=1, sticky="n", padx=(0, 8))
        songs = songs_panel.content
        # Center content vertically: spacer rows absorb the empty space the
        # user flagged, so the three buttons sit in the middle of the panel.
        songs.columnconfigure(0, weight=1)
        songs.rowconfigure(0, weight=1)
        songs.rowconfigure(4, weight=1)
        self._action_button(songs, "Añadir canciones", self.add_files, width=190, tone="blue").grid(
            row=1, column=0, padx=4, pady=(6, 2), sticky="ew"
        )
        self._action_button(songs, "Quitar seleccionado", self.remove_selected, width=190, tone="silver").grid(
            row=2, column=0, padx=4, pady=2, sticky="ew"
        )
        self._action_button(songs, "Vaciar lista", self.clear_files, width=190, tone="silver").grid(
            row=3, column=0, padx=4, pady=(2, 6), sticky="ew"
        )

        output_panel = RoundedSection(controls, "2. Salida", min_height=230, min_width=410)
        output_panel.grid(row=0, column=2, sticky="n", padx=(8, 0))
        output = output_panel.content
        # Dial A = Formato, Dial B = Calidad. Each has its own row so the two
        # sit side by side inside the panel; spacing matches the songs panel.
        dials_row = tk.Frame(output, bg=PANEL_FILL, highlightthickness=0, bd=0)
        dials_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(6, 4))
        dials_row.columnconfigure(0, weight=1)
        dials_row.columnconfigure(1, weight=1)

        self.format_dial = DialButton(dials_row, CONVERSION_FORMATS, self.output_format, asset_prefix="formato", label="Formato")
        self.format_dial.grid(row=0, column=0, padx=(0, 10), pady=0)

        self.quality_dial = DialButton(
            dials_row, MP3_QUALITIES, self.quality, asset_prefix="calidad", asset_category="MP3", label="Calidad"
        )
        self.quality_dial.grid(row=0, column=1, padx=(10, 0), pady=0)

        self._action_button(output, "Seleccionar carpeta", self.choose_output_dir, width=190, tone="blue").grid(
            row=1, column=0, columnspan=2, padx=4, pady=(8, 4), sticky="ew"
        )
        ttk.Checkbutton(output, text="Sobrescribir existentes", variable=self.overwrite).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 6)
        )

        self.output_label = ttk.Label(self.conversion_tab, text="Carpeta de salida: sin seleccionar", anchor=tk.W)
        self.output_label.grid(row=2, column=0, sticky="ew", padx=8, pady=(6, 0))

        table_panel = RoundedSection(self.conversion_tab, "Canciones cargadas", min_height=360)
        table_panel.grid(row=1, column=0, sticky="nsew", padx=4)
        table_frame = table_panel.content
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("song", "format", "original_size", "final_size", "quality", "status")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        headings = {
            "song": "Canción",
            "format": "Formato",
            "original_size": "Peso original",
            "final_size": "Peso final",
            "quality": "Calidad",
            "status": "Estado",
        }
        widths = {
            "song": 420,
            "format": 90,
            "original_size": 120,
            "final_size": 120,
            "quality": 100,
            "status": 180,
        }
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor=tk.W)
        self._configure_table_stripes(self.table)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def _on_conversion_format_change(self, *_args: object) -> None:
        self._update_conversion_quality_options()

    def _update_conversion_quality_options(self) -> None:
        options = QUALITY_OPTIONS.get(self.output_format.get(), MP3_QUALITIES)
        if hasattr(self, "quality_dial"):
            self.quality_dial.set_options(options, category=self.output_format.get())
        if self.quality.get() not in options:
            self.quality.set(options[0])
        for item in self.table.get_children() if hasattr(self, "table") else ():
            self.update_row(item, quality=self.quality.get())

    def _build_global_log(self, root: ttk.Frame) -> None:
        log_panel = RoundedSection(root, "Registro global", min_height=170)
        log_panel.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        log_frame = log_panel.content
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, height=8, wrap=tk.WORD, relief=tk.FLAT, bg="#fafafa",
                          bd=0, highlightthickness=0, padx=10, pady=8, font=("Menlo", 11),
                          borderwidth=0)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=log_scrollbar.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scrollbar.grid(row=0, column=1, sticky="ns")

    def show_diagnostics(self) -> None:
        items = self._build_diagnostics_items()
        self.log_message("")
        self.log_message("=== Diagnóstico del sistema ===")
        for status, label, detail in items:
            self.log_message(f"{status}: {label} - {detail}")
        self.set_status("Diagnóstico completado")
        self._show_diagnostics_window(items)

    def _build_diagnostics_items(self) -> list[tuple[str, str, str]]:
        app_dir = base_path()
        bin_dir = app_dir / "bin"
        command_file = app_dir / "abrir_music_tool.command"
        items = [
            ("OK", "Python", f"{platform.python_version()} - {sys.executable}"),
            ("OK", "Tkinter", f"Tk {tk.TkVersion} / Tcl {tk.TclVersion}"),
            ("OK", "Sistema", platform.platform()),
            ("OK" if app_dir.exists() else "FALTA", "Carpeta app", str(app_dir)),
            ("OK" if bin_dir.exists() else "FALTA", "Carpeta bin", str(bin_dir)),
            ("OK" if os.access(app_dir, os.W_OK) else "SIN PERMISO", "Permiso escritura app", str(app_dir)),
            self._file_diagnostic("Lanzador .command", command_file),
        ]
        for name in ("ffmpeg", "ffprobe", "yt-dlp", "deno"):
            items.extend(self._binary_diagnostics(name))
        return items

    def _file_diagnostic(self, label: str, path: Path) -> tuple[str, str, str]:
        if not path.exists():
            return ("FALTA", label, str(path))
        if not os.access(path, os.X_OK):
            return ("SIN PERMISO", label, f"{path} - ejecuta chmod +x")
        return ("OK", label, str(path))

    def _binary_diagnostics(self, name: str) -> list[tuple[str, str, str]]:
        path = find_binary(name)
        if not path:
            return [("FALTA", name, f"añade {name} a bin/ o al PATH")]

        binary_path = Path(path)
        location = "bin" if binary_path.parent == base_path() / "bin" else "PATH"
        command_prefix = yt_dlp_command_prefix(path) if name == "yt-dlp" else [path]
        if command_prefix == [path] and not os.access(path, os.X_OK):
            return [("SIN PERMISO", name, f"{path} - ejecuta chmod +x")]

        version = self._binary_version(name, path)
        detail = f"{location} - {path}"
        if name == "yt-dlp" and command_prefix != [path]:
            detail = f"{location} - {path} usando {command_prefix[0]}"
        return [
            ("OK", name, detail),
            ("OK", f"{name} versión", version),
        ]

    def _binary_version(self, name: str, path: str) -> str:
        command = [*yt_dlp_command_prefix(path), "--version"] if name == "yt-dlp" else [path, "-version"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"no se pudo leer ({exc})"
        first_line = (result.stdout or result.stderr).splitlines()
        if not first_line:
            return "sin salida de versión"
        return first_line[0][:160]

    def _show_diagnostics_window(self, items: list[tuple[str, str, str]]) -> None:
        all_ok = all(status == "OK" for status, _label, _detail in items)
        window = tk.Toplevel(self)
        window.title("Diagnóstico de Music Tool")
        window.geometry("760x520")
        window.minsize(640, 420)
        window.transient(self)
        window.configure(bg=METAL_BG)

        header_color = "#d8ead2" if all_ok else "#f0dfc4"
        header_text = "Todo está listo" if all_ok else "Hay puntos a revisar"
        header = tk.Frame(window, bg=header_color, padx=18, pady=14, highlightthickness=0, bd=0)
        header.pack(fill=tk.X, padx=14, pady=(14, 8))
        tk.Label(header, text=header_text, bg=header_color, fg="#809080", font=("Helvetica", 18, "bold")).pack(anchor=tk.W)
        tk.Label(
            header,
            text="Python, Tkinter, permisos y binarios locales comprobados.",
            bg=header_color,
            fg="#90a890",
            font=("Helvetica", 12),
        ).pack(anchor=tk.W, pady=(4, 0))

        table_frame = tk.Frame(window, bg=METAL_BG, padx=14, highlightthickness=0, bd=0)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("status", "item", "detail")
        table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        table.heading("status", text="Estado")
        table.heading("item", text="Comprobación")
        table.heading("detail", text="Detalle")
        table.column("status", width=110, anchor=tk.CENTER)
        table.column("item", width=170, anchor=tk.W)
        table.column("detail", width=440, anchor=tk.W)
        table.tag_configure("ok", background="#edf7ea")
        table.tag_configure("warn", background="#fff4d8")
        table.tag_configure("error", background="#f8dddd")
        for status, label, detail in items:
            tag = "ok" if status == "OK" else "error" if status == "FALTA" else "warn"
            table.insert("", tk.END, values=(status, label, detail), tags=(tag,))
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        buttons = tk.Frame(window, bg=METAL_BG, padx=14, pady=12, highlightthickness=0, bd=0)
        buttons.pack(fill=tk.X)
        PillButton(
            buttons,
            text="Cerrar",
            command=window.destroy,
            width=110,
            fill="#f2f2f2",
            active_fill="#dedede",
            outline="#b8b8b8",
            foreground="#b0b0b0",
        ).pack(side=tk.RIGHT)

    def _build_editor_tab(self) -> None:
        self.editor_tab.columnconfigure(0, weight=1)
        self.editor_tab.columnconfigure(1, weight=1)
        self.editor_tab.rowconfigure(1, weight=0)
        self.editor_tab.rowconfigure(2, weight=0)

        load_panel = RoundedSection(self.editor_tab, "1. Canción", min_height=92)
        load_panel.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 8))
        load = load_panel.content
        load.columnconfigure(1, weight=1)
        self._action_button(load, "Cargar canción", self.load_editor_song, width=140, tone="blue").grid(
            row=0, column=0, padx=4, pady=4
        )
        ttk.Label(load, textvariable=self.editor_file, anchor=tk.W).grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        ttk.Label(load, textvariable=self.editor_info, anchor=tk.W).grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=4)

        metadata_panel = RoundedSection(self.editor_tab, "2. Metadatos", min_height=300)
        metadata_panel.grid(row=1, column=0, sticky="ew", padx=(4, 8), pady=4)
        metadata = metadata_panel.content
        metadata.columnconfigure(1, weight=1)
        metadata.columnconfigure(3, weight=1)
        # Layout: Título, Artista, Álbum (una por fila), luego Año+Género en
        # la misma fila, luego Compositor y Número de pista.
        full_rows = METADATA_FIELDS[:3]   # Título, Artista, Álbum
        for row, (key, label) in enumerate(full_rows):
            self.editor_metadata_vars[key] = StringVar(value="")
            ttk.Label(metadata, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            entry = ttk.Entry(metadata, textvariable=self.editor_metadata_vars[key], state="disabled")
            entry.grid(row=row, column=1, columnspan=3, sticky="ew", padx=4, pady=3)
            self.editor_metadata_entries[key] = entry
        # Año + Género en la misma fila
        row += 1
        for col, (key, label) in enumerate((METADATA_FIELDS[3], METADATA_FIELDS[4])):
            self.editor_metadata_vars[key] = StringVar(value="")
            ttk.Label(metadata, text=label).grid(row=row, column=col * 2, sticky="w", padx=4, pady=3)
            entry = ttk.Entry(metadata, textvariable=self.editor_metadata_vars[key], state="disabled")
            entry.grid(row=row, column=col * 2 + 1, sticky="ew", padx=4, pady=3)
            self.editor_metadata_entries[key] = entry
        # Compositor y Número de pista
        for row_off, (key, label) in enumerate(METADATA_FIELDS[5:], start=1):
            r = row + row_off
            self.editor_metadata_vars[key] = StringVar(value="")
            ttk.Label(metadata, text=label).grid(row=r, column=0, sticky="w", padx=4, pady=3)
            entry = ttk.Entry(metadata, textvariable=self.editor_metadata_vars[key], state="disabled")
            entry.grid(row=r, column=1, columnspan=3, sticky="ew", padx=4, pady=3)
            self.editor_metadata_entries[key] = entry

        edits_panel = RoundedSection(self.editor_tab, "3. Edición y exportación", min_height=300)
        edits_panel.grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=4)
        edits = edits_panel.content
        edits.columnconfigure(1, weight=1)
        edits.columnconfigure(2, weight=0)
        self.editor_start = StringVar(value="")
        self.editor_end = StringVar(value="")
        self.editor_fade_in = StringVar(value="")
        self.editor_fade_out = StringVar(value="")
        self.editor_volume = StringVar(value="1.0")
        # Filas 0-3: Inicio, Final, Fade in, Fade out (una por fila, col 0-1)
        edit_rows = (
            ("Inicio", self.editor_start),
            ("Final", self.editor_end),
            ("Fade in", self.editor_fade_in),
            ("Fade out", self.editor_fade_out),
        )
        for row, (label, variable) in enumerate(edit_rows):
            ttk.Label(edits, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(edits, textvariable=variable, state="normal").grid(row=row, column=1, sticky="ew", padx=4, pady=3)
            variable.trace_add("write", self._redraw_editor_visual)
        # Fila 4: Volumen (misma columna que las anteriores, col 0-1)
        ttk.Label(edits, text="Volumen").grid(row=4, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(edits, textvariable=self.editor_volume, state="normal").grid(row=4, column=1, sticky="ew", padx=4, pady=3)
        self.editor_volume.trace_add("write", self._redraw_editor_visual)
        # Fila 5: Formato (misma columna, col 0-1)
        ttk.Label(edits, text="Formato").grid(row=5, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(edits, textvariable=self.editor_output_format, values=EDITOR_OUTPUT_FORMATS, width=10, state="readonly").grid(
            row=5, column=1, sticky="ew", padx=4, pady=3
        )
        # Fila 6: Calidad (misma columna, col 0-1)
        ttk.Label(edits, text="Calidad").grid(row=6, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(edits, textvariable=self.editor_quality, values=MP3_QUALITIES, width=10, state="readonly").grid(
            row=6, column=1, sticky="ew", padx=4, pady=3
        )
        # Botones a la derecha (col 2-3)
        self._action_button(edits, "Seleccionar carpeta", self.choose_editor_output_dir, width=145, tone="silver").grid(
            row=0, column=2, columnspan=2, sticky="e", padx=(14, 4), pady=4
        )
        self._action_button(edits, "Generar forma", self.start_waveform_generation, width=135, tone="blue").grid(
            row=1, column=2, columnspan=2, sticky="e", padx=(14, 4), pady=4
        )
        self._action_button(edits, "Exportar editada", self.start_editor_export, width=135, tone="green").grid(
            row=2, column=2, columnspan=2, sticky="e", padx=(14, 4), pady=4
        )
        ttk.Checkbutton(edits, text="Sobrescribir", variable=self.editor_overwrite).grid(
            row=7, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 3)
        )
        ttk.Label(edits, textvariable=self.editor_output_dir, anchor=tk.W).grid(
            row=8, column=0, columnspan=4, sticky="ew", padx=4, pady=(3, 3)
        )

        waveform_panel = RoundedSection(self.editor_tab, "Edición visual", min_height=320)
        waveform_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4))
        waveform = waveform_panel.content
        waveform.columnconfigure(0, weight=1)
        waveform.rowconfigure(0, weight=1)
        self.waveform_label = ttk.Label(waveform, text="Pendiente de generar", anchor=tk.CENTER)
        self.waveform_label.grid(
            row=0, column=0, sticky="ew", padx=8, pady=14
        )
        self.edit_visual_canvas = tk.Canvas(waveform, height=180, bg=PANEL_FILL, highlightthickness=0, bd=0)
        self.edit_visual_canvas.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 10))
        self.edit_visual_canvas.bind("<Configure>", self._redraw_editor_visual)
        self.edit_visual_canvas.bind("<Button-1>", self._start_editor_visual_drag)
        self.edit_visual_canvas.bind("<B1-Motion>", self._drag_editor_visual_handle)
        self.edit_visual_canvas.bind("<ButtonRelease-1>", self._stop_editor_visual_drag)
        self._redraw_editor_visual()

    def _build_url_tab(self) -> None:
        self.url_tab.columnconfigure(0, weight=1)
        self.url_tab.rowconfigure(2, weight=0)

        source_panel = RoundedSection(self.url_tab, "1. URL", min_height=88)
        source_panel.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 8))
        source = source_panel.content
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text="URL").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(source, textvariable=self.url_value).grid(row=0, column=1, sticky="ew", padx=4, pady=4)

        options_panel = RoundedSection(self.url_tab, "2. Extracción de audio", min_height=150)
        options_panel.grid(row=1, column=0, sticky="new", padx=4, pady=4)
        options = options_panel.content
        options.columnconfigure(1, weight=1)
        self._action_button(options, "Seleccionar carpeta", self.choose_url_output_dir, width=150, tone="blue").grid(
            row=0, column=0, sticky="w", padx=4, pady=4
        )
        self.url_output_label = ttk.Label(options, text="Sin carpeta seleccionada", anchor=tk.W)
        self.url_output_label.grid(row=0, column=1, sticky="ew", padx=8, pady=4)
        self._action_button(options, "Extraer MP3", self.start_url_extraction, width=150, tone="green").grid(
            row=1, column=0, sticky="w", padx=4, pady=(12, 4)
        )

        results_panel = RoundedSection(self.url_tab, "Resultados", min_height=220)
        results_panel.grid(row=2, column=0, sticky="ew", padx=4, pady=(8, 4))
        results = results_panel.content
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        columns = ("file", "format", "size", "status")
        self.url_results_table = ttk.Treeview(results, columns=columns, show="headings", height=6)
        for column, heading, width in (
            ("file", "Archivo", 560),
            ("format", "Formato", 120),
            ("size", "Peso", 120),
            ("status", "Estado", 180),
        ):
            self.url_results_table.heading(column, text=heading)
            self.url_results_table.column(column, width=width, anchor=tk.W)
        self._configure_table_stripes(self.url_results_table)
        url_scrollbar = ttk.Scrollbar(results, orient=tk.VERTICAL, command=self.url_results_table.yview)
        self.url_results_table.configure(yscrollcommand=url_scrollbar.set)
        self.url_results_table.grid(row=0, column=0, sticky="nsew")
        url_scrollbar.grid(row=0, column=1, sticky="ns")

        note_panel = RoundedSection(self.url_tab, "Uso previsto", min_height=70)
        note_panel.grid(row=3, column=0, sticky="ew", padx=4, pady=(8, 4))
        note = note_panel.content
        note.columnconfigure(0, weight=1)
        ttk.Label(
            note,
            text="Función pensada para uso personal y local: material propio, con permiso, o contenido que tengas derecho a guardar.",
            wraplength=900,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=8)

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleccionar canciones",
            filetypes=(
                ("Audio", "*.flac *.mp3 *.wav *.m4a *.aac"),
                ("Todos los archivos", "*.*"),
            ),
        )
        for path in paths:
            if not path.lower().endswith(SUPPORTED_INPUTS):
                self.log_message(f"Formato no soportado, omitido: {path}")
                continue
            if path in self.files:
                continue
            self.files.append(path)
            self.table.insert(
                "",
                tk.END,
                iid=path,
                values=(
                    Path(path).name,
                    Path(path).suffix.replace(".", "").upper(),
                    format_size(path),
                    "-",
                    self.quality.get(),
                    "Pendiente",
                ),
            )
        if paths:
            self._apply_table_stripes(self.table)
            self.set_status(f"{len(self.files)} canción(es) cargada(s)")

    def remove_selected(self) -> None:
        for item in self.table.selection():
            if item in self.files:
                self.files.remove(item)
            self.table.delete(item)
        self._apply_table_stripes(self.table)
        self.set_status("Selección eliminada")

    def clear_files(self) -> None:
        self.files.clear()
        for item in self.table.get_children():
            self.table.delete(item)
        self._apply_table_stripes(self.table)
        self.set_status("Lista vacía")

    def choose_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if path:
            self.output_dir.set(path)
            self.output_label.configure(text=f"Carpeta de salida: {path}")
            self.set_status("Carpeta de salida seleccionada")

    def choose_editor_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if path:
            self.editor_output_dir.set(path)
            self.set_status("Carpeta de salida del editor seleccionada")

    def choose_url_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if path:
            self.url_output_dir.set(path)
            self.url_output_label.configure(text=path)
            self.set_status("Carpeta de salida URL seleccionada")

    def load_editor_song(self) -> None:
        path = filedialog.askopenfilename(
            title="Cargar canción",
            filetypes=(
                ("Audio", "*.flac *.mp3 *.wav *.m4a *.aac"),
                ("Todos los archivos", "*.*"),
            ),
        )
        if not path:
            return
        if not path.lower().endswith(SUPPORTED_INPUTS):
            self.show_error("Formato de audio no soportado.")
            return

        ffprobe = find_binary("ffprobe")
        if not ffprobe:
            self.show_error("No se ha encontrado ffprobe. Añádelo a bin/ o al PATH.")
            return
        if not os.access(ffprobe, os.X_OK):
            self.show_error(f"ffprobe no tiene permisos de ejecución:\n{ffprobe}")
            return

        self.editor_path = path
        self.editor_file.set(Path(path).name)
        self.editor_info.set(f"Duración: leyendo... | Peso: {format_size(path)} | Bitrate: leyendo...")
        self.set_status("Leyendo canción...")
        self.log_message(f"Leyendo metadatos: {path}")
        self._set_metadata_entries_state("disabled")
        threading.Thread(target=self._load_editor_song_info, args=(path,), daemon=True).start()

    def _load_editor_song_info(self, path: str) -> None:
        try:
            info = read_audio_info(path)
        except RuntimeError as exc:
            self.after(0, lambda: self._handle_editor_load_error(str(exc)))
            return
        self.after(0, lambda: self._apply_editor_song_info(path, info))

    def _apply_editor_song_info(self, path: str, info: dict[str, object]) -> None:
        tags = info.get("tags", {})
        if not isinstance(tags, dict):
            tags = {}

        metadata = self._normalize_editor_metadata(tags)
        try:
            self.editor_duration_seconds = float(info.get("duration") or 0)
        except (TypeError, ValueError):
            self.editor_duration_seconds = None
        self.original_editor_metadata = metadata.copy()
        for key, _label in METADATA_FIELDS:
            self.editor_metadata_vars[key].set(metadata.get(key, ""))

        self.editor_file.set(Path(path).name)
        self.editor_info.set(
            f"Duración: {format_duration(info.get('duration'))} | "
            f"Peso: {format_size(path)} | "
            f"Bitrate: {format_bitrate(info.get('bitrate'))}"
        )
        self._set_metadata_entries_state("normal")
        self.log_message("Metadatos cargados correctamente.")
        self.set_status("Canción cargada")
        self._redraw_editor_visual()

    def _handle_editor_load_error(self, message: str) -> None:
        self.log_message(f"Error leyendo canción: {message}")
        self.set_status("Error leyendo canción")
        messagebox.showerror(APP_NAME, message)

    def _normalize_editor_metadata(self, tags: dict[str, str]) -> dict[str, str]:
        return {
            "title": tags.get("title", ""),
            "artist": tags.get("artist", "") or tags.get("album_artist", ""),
            "album": tags.get("album", ""),
            "date": tags.get("date", "") or tags.get("year", ""),
            "genre": tags.get("genre", ""),
            "composer": tags.get("composer", ""),
            "track": tags.get("track", "") or tags.get("tracknumber", ""),
        }

    def _set_metadata_entries_state(self, state: str) -> None:
        for entry in self.editor_metadata_entries.values():
            entry.configure(state=state)

    def _redraw_editor_visual(self, *_args: object) -> None:
        canvas = self.edit_visual_canvas
        if not canvas:
            return
        width = max(canvas.winfo_width(), 640)
        height = max(canvas.winfo_height(), 150)
        canvas.delete("all")

        left = 24
        right = width - 24
        top = 32
        bottom = height - 42
        mid = (top + bottom) // 2
        draw_rounded_rect(canvas, left, top, right, bottom, 16, fill="#ffffff", outline="#c0c0c0", tags="visual")

        duration = self.editor_duration_seconds if self.editor_duration_seconds and self.editor_duration_seconds > 0 else 240.0
        try:
            start = parse_time_value(self.editor_start.get()) or 0.0
            end = parse_time_value(self.editor_end.get()) or duration
            fade_in = parse_optional_float(self.editor_fade_in.get(), "Fade in") or 0.0
            fade_out = parse_optional_float(self.editor_fade_out.get(), "Fade out") or 0.0
            volume = parse_optional_float(self.editor_volume.get(), "Volumen") or 1.0
        except ValueError:
            canvas.create_text(left + 12, mid + 4, text="Valores de edición pendientes de corregir", anchor=tk.W, fill="#c08070")
            return

        start = max(0.0, min(start, duration))
        end = max(start, min(end, duration))
        x_start = self._timeline_x(start, duration, left, right)
        x_end = self._timeline_x(end, duration, left, right)
        segment_duration = max(end - start, 0.1)
        fade_in_display = fade_in if fade_in > 0 else min(5.0, segment_duration * 0.12)
        fade_out_display = fade_out if fade_out > 0 else min(5.0, segment_duration * 0.12)
        fade_in_x = self._timeline_x(min(start + fade_in_display, end), duration, left, right)
        fade_out_x = self._timeline_x(max(start, end - fade_out_display), duration, left, right)
        self.editor_visual_geometry = (left, right, duration)
        self.editor_visual_handles = {
            "start": x_start,
            "end": x_end,
            "fade_in": fade_in_x,
            "fade_out": fade_out_x,
        }

        canvas.create_rectangle(left + 2, top + 2, x_start, bottom - 2, fill="#d9d9d9", outline="")
        canvas.create_rectangle(x_end, top + 2, right - 2, bottom - 2, fill="#d9d9d9", outline="")
        canvas.create_rectangle(x_start, top + 2, x_end, bottom - 2, fill="#eef5ff", outline="")

        if fade_in_display > 0:
            canvas.create_polygon(x_start, bottom - 3, fade_in_x, top + 4, fade_in_x, bottom - 3, fill="#c7ddff", outline="")
            canvas.create_text((x_start + fade_in_x) // 2, top - 4, text="fade in", font=("Helvetica", 9), fill="#315f9c")

        if fade_out_display > 0:
            canvas.create_polygon(fade_out_x, top + 4, x_end, bottom - 3, fade_out_x, bottom - 3, fill="#d9c7ff", outline="")
            canvas.create_text((fade_out_x + x_end) // 2, top - 4, text="fade out", font=("Helvetica", 9), fill="#64469c")

        base_y = bottom - 8
        volume_y = max(top + 6, min(bottom - 8, base_y - ((volume - 1.0) * 24)))
        canvas.create_line(x_start, base_y, x_end, base_y, fill="#d0d0d0", dash=(4, 4))
        canvas.create_line(x_start, volume_y, x_end, volume_y, fill="#909090", width=2)
        canvas.create_text(x_start + 8, volume_y - 6, text=f"vol {volume:g}", anchor=tk.W, font=("Helvetica", 9), fill="#909090")

        self._draw_timeline_marker(canvas, x_start, top, bottom, "inicio", "#2f82df")
        self._draw_timeline_marker(canvas, x_end, top, bottom, "final", "#2f82df")
        self._draw_timeline_handle(canvas, fade_in_x, mid, "fade in", "#315f9c")
        self._draw_timeline_handle(canvas, fade_out_x, mid, "fade out", "#64469c")
        canvas.create_text(left, bottom + 14, text="0:00", anchor=tk.W, font=("Helvetica", 9), fill="#b0b0b0")
        canvas.create_text(right, bottom + 14, text=format_duration(duration), anchor=tk.E, font=("Helvetica", 9), fill="#b0b0b0")

    def _timeline_x(self, seconds: float, duration: float, left: int, right: int) -> int:
        if duration <= 0:
            return left
        return int(left + ((right - left) * (seconds / duration)))

    def _draw_timeline_marker(self, canvas: tk.Canvas, x: int, top: int, bottom: int, label: str, color: str) -> None:
        canvas.create_line(x, top - 4, x, bottom + 4, fill=color, width=2)
        canvas.create_oval(x - 5, top - 9, x + 5, top + 1, fill=color, outline="#ffffff")
        canvas.create_text(x + 4, bottom + 13, text=label, anchor=tk.W, font=("Helvetica", 9), fill=color)

    def _draw_timeline_handle(self, canvas: tk.Canvas, x: int, y: int, label: str, color: str) -> None:
        canvas.create_oval(x - 6, y - 6, x + 6, y + 6, fill=color, outline="#ffffff", width=1)
        canvas.create_text(x + 8, y - 8, text=label, anchor=tk.W, font=("Helvetica", 9), fill=color)

    def _start_editor_visual_drag(self, event: tk.Event) -> None:
        if not self.editor_visual_handles:
            return
        nearest = min(self.editor_visual_handles.items(), key=lambda item: abs(item[1] - event.x))
        if abs(nearest[1] - event.x) <= 18:
            self.editor_drag_target = nearest[0]
            if self.edit_visual_canvas:
                self.edit_visual_canvas.configure(cursor="sb_h_double_arrow")

    def _drag_editor_visual_handle(self, event: tk.Event) -> None:
        if not self.editor_drag_target or not self.editor_visual_geometry:
            return
        left, right, duration = self.editor_visual_geometry
        seconds = self._seconds_from_timeline_x(event.x, duration, left, right)
        try:
            start = parse_time_value(self.editor_start.get()) or 0.0
            end = parse_time_value(self.editor_end.get()) or duration
        except ValueError:
            return

        if self.editor_drag_target == "start":
            new_start = max(0.0, min(seconds, end - 0.1))
            self.editor_start.set(compact_seconds(new_start))
        elif self.editor_drag_target == "end":
            new_end = max(start + 0.1, min(seconds, duration))
            self.editor_end.set(compact_seconds(new_end))
        elif self.editor_drag_target == "fade_in":
            new_fade = max(0.0, min(seconds - start, max(end - start, 0.0)))
            self.editor_fade_in.set(compact_seconds(new_fade))
        elif self.editor_drag_target == "fade_out":
            new_fade = max(0.0, min(end - seconds, max(end - start, 0.0)))
            self.editor_fade_out.set(compact_seconds(new_fade))

    def _stop_editor_visual_drag(self, _event: tk.Event) -> None:
        self.editor_drag_target = None
        if self.edit_visual_canvas:
            self.edit_visual_canvas.configure(cursor="")

    def _seconds_from_timeline_x(self, x: int, duration: float, left: int, right: int) -> float:
        x = max(left, min(x, right))
        if right <= left:
            return 0.0
        return ((x - left) / (right - left)) * duration

    def start_editor_export(self) -> None:
        if self.is_exporting_editor:
            messagebox.showinfo(APP_NAME, "Ya hay una exportación del editor en curso.")
            return
        if not self.editor_path:
            self.show_error("No hay canción cargada en el editor.")
            return
        if not self.editor_output_dir.get():
            self.show_error("No se ha seleccionado carpeta de salida para el editor.")
            return

        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            self.show_error("No se ha encontrado ffmpeg. Añádelo a bin/ o al PATH.")
            return
        if not os.access(ffmpeg, os.X_OK):
            self.show_error(f"ffmpeg no tiene permisos de ejecución:\n{ffmpeg}")
            return

        try:
            self._validate_editor_export_options()
        except ValueError as exc:
            self.show_error(str(exc))
            return

        self.cancel_requested.clear()
        self.is_exporting_editor = True
        self.set_status("Exportando canción editada...")
        self.set_progress(0.15)
        threading.Thread(target=self.export_editor_song, daemon=True).start()

    def _validate_editor_export_options(self) -> None:
        start = parse_time_value(self.editor_start.get())
        end = parse_time_value(self.editor_end.get())
        if start is not None and start < 0:
            raise ValueError("El inicio no puede ser negativo.")
        if end is not None and end < 0:
            raise ValueError("El final no puede ser negativo.")
        if start is not None and end is not None and end <= start:
            raise ValueError("El tiempo final debe ser mayor que el inicio.")

        fade_in = parse_optional_float(self.editor_fade_in.get(), "Fade in")
        fade_out = parse_optional_float(self.editor_fade_out.get(), "Fade out")
        volume = parse_optional_float(self.editor_volume.get(), "Volumen")
        if fade_in is not None and fade_in < 0:
            raise ValueError("Fade in no puede ser negativo.")
        if fade_out is not None and fade_out < 0:
            raise ValueError("Fade out no puede ser negativo.")
        if volume is not None and volume <= 0:
            raise ValueError("Volumen debe ser mayor que 0.")

    def export_editor_song(self) -> None:
        assert self.editor_path is not None
        source = Path(self.editor_path)
        output = Path(self.editor_output_dir.get()) / f"{source.stem}_editado.mp3"
        if not self.editor_overwrite.get():
            output = unique_output_path(output)

        try:
            command = self._build_editor_export_command(source, output)
        except ValueError as exc:
            self.after(0, lambda: self._handle_editor_export_error(str(exc)))
            return

        self.log_message("")
        self.log_message("=== Exportación desde editor ===")
        self.log_message(f"Canción: {source.name}")
        self.log_message(f"Calidad: MP3 {self.editor_quality.get()}")
        self.log_message(f"Destino: {output}")

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.current_process = process
            _stdout, stderr = process.communicate()
        except OSError as exc:
            self.after(0, lambda: self._handle_editor_export_error(f"No se pudo ejecutar ffmpeg: {exc}"))
            return
        finally:
            self.current_process = None

        if self.cancel_requested.is_set():
            self.log_message("Exportación del editor cancelada por el usuario.")
            self.after(0, lambda: self.set_status("Exportación cancelada"))
            self.after(0, self._finish_editor_export)
            return

        if process.returncode != 0:
            error = stderr.strip() or "FFmpeg falló sin mensaje de error."
            self.after(0, lambda: self._handle_editor_export_error(error))
            return

        self.log_message(f"Tamaño final: {format_size(output)}")
        self.log_message("Canción editada exportada correctamente.")
        self.after(0, lambda: self.set_progress(1.0))
        self.after(0, lambda: self.set_status("Canción editada exportada"))
        self.after(0, self._finish_editor_export)

    def _build_editor_export_command(self, source: Path, output: Path) -> list[str]:
        ffmpeg = find_binary("ffmpeg")
        assert ffmpeg is not None
        command = [
            ffmpeg,
            "-hide_banner",
            "-y" if self.editor_overwrite.get() else "-n",
            "-i",
            str(source),
            "-vn",
            "-map_metadata",
            "0",
        ]

        filters = self._build_editor_audio_filters()
        if filters:
            command.extend(["-af", ",".join(filters)])

        command.extend(
            [
                "-codec:a",
                "libmp3lame",
                "-b:a",
                self.editor_quality.get(),
                "-id3v2_version",
                "3",
            ]
        )
        command.extend(self._metadata_override_args())
        command.append(str(output))
        return command

    def _build_editor_audio_filters(self) -> list[str]:
        filters: list[str] = []
        start = parse_time_value(self.editor_start.get())
        end = parse_time_value(self.editor_end.get())
        if start is not None or end is not None:
            parts = ["atrim"]
            if start is not None:
                parts.append(f"start={start}")
            if end is not None:
                parts.append(f"end={end}")
            filters.append(":".join(parts))
            filters.append("asetpts=PTS-STARTPTS")

        fade_in = parse_optional_float(self.editor_fade_in.get(), "Fade in")
        if fade_in and fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={fade_in}")

        fade_out = parse_optional_float(self.editor_fade_out.get(), "Fade out")
        if fade_out and fade_out > 0:
            output_duration = self._editor_output_duration(start, end)
            if output_duration is None:
                raise ValueError("Para usar fade out hace falta conocer la duración de la canción.")
            fade_start = max(0, output_duration - fade_out)
            filters.append(f"afade=t=out:st={fade_start}:d={fade_out}")

        volume = parse_optional_float(self.editor_volume.get(), "Volumen")
        if volume is not None and volume != 1.0:
            filters.append(f"volume={volume}")
        return filters

    def _editor_output_duration(self, start: float | None, end: float | None) -> float | None:
        source_duration = self.editor_duration_seconds
        if end is not None:
            return end - (start or 0)
        if source_duration is not None and source_duration > 0:
            return source_duration - (start or 0)
        return None

    def _metadata_override_args(self) -> list[str]:
        args: list[str] = []
        for key, _label in METADATA_FIELDS:
            value = self.editor_metadata_vars[key].get().strip()
            original = self.original_editor_metadata.get(key, "").strip()
            if value and value != original:
                args.extend(["-metadata", f"{key}={value}"])
                self.log_message(f"Metadato actualizado: {key} = {value}")
        return args

    def _handle_editor_export_error(self, message: str) -> None:
        self.log_message(f"Error exportando canción: {message}")
        self.set_progress(0.0)
        self.set_status("Error exportando canción")
        self._finish_editor_export()
        messagebox.showerror(APP_NAME, message)

    def _finish_editor_export(self) -> None:
        self.is_exporting_editor = False

    def start_waveform_generation(self) -> None:
        if self.is_generating_waveform:
            messagebox.showinfo(APP_NAME, "Ya se está generando la forma de onda.")
            return
        if not self.editor_path:
            self.show_error("No hay canción cargada en el editor.")
            return

        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            self.show_error("No se ha encontrado ffmpeg. Añádelo a bin/ o al PATH.")
            return
        if not os.access(ffmpeg, os.X_OK):
            self.show_error(f"ffmpeg no tiene permisos de ejecución:\n{ffmpeg}")
            return

        self.cancel_requested.clear()
        self.is_generating_waveform = True
        self.set_status("Generando forma de onda...")
        self.set_progress(0.25)
        if self.waveform_label:
            self.waveform_label.configure(text="Generando forma de onda...", image="")
        threading.Thread(target=self.generate_waveform, daemon=True).start()

    def generate_waveform(self) -> None:
        assert self.editor_path is not None
        source = Path(self.editor_path)
        output = base_path() / "waveform_editor.png"
        ffmpeg = find_binary("ffmpeg")
        assert ffmpeg is not None
        command = [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            "aformat=channel_layouts=mono,showwavespic=s=900x180:colors=black",
            "-frames:v",
            "1",
            str(output),
        ]

        self.log_message("")
        self.log_message("=== Forma de onda ===")
        self.log_message(f"Generando waveform: {source.name}")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.current_process = process
            _stdout, stderr = process.communicate()
        except OSError as exc:
            self.after(0, lambda: self._handle_waveform_error(f"No se pudo ejecutar ffmpeg: {exc}"))
            return
        finally:
            self.current_process = None

        if self.cancel_requested.is_set():
            self.log_message("Generación de forma de onda cancelada por el usuario.")
            self.after(0, self._finish_waveform_cancel)
            return

        if process.returncode != 0:
            error = stderr.strip() or "FFmpeg falló sin mensaje de error."
            self.after(0, lambda: self._handle_waveform_error(error))
            return

        self.log_message(f"Forma de onda guardada en: {output}")
        self.after(0, lambda: self._show_waveform(output))

    def _show_waveform(self, path: Path) -> None:
        try:
            self.waveform_photo = tk.PhotoImage(file=str(path))
        except tk.TclError as exc:
            self._handle_waveform_error(f"No se pudo mostrar la imagen PNG: {exc}")
            return
        if self.waveform_label:
            self.waveform_label.configure(image=self.waveform_photo, text="")
        self.is_generating_waveform = False
        self.set_progress(1.0)
        self.set_status("Forma de onda generada")

    def _finish_waveform_cancel(self) -> None:
        if self.waveform_label:
            self.waveform_label.configure(text="Forma de onda cancelada", image="")
        self.is_generating_waveform = False
        self.set_progress(0.0)
        self.set_status("Forma de onda cancelada")

    def _handle_waveform_error(self, message: str) -> None:
        self.log_message(f"Error generando forma de onda: {message}")
        if self.waveform_label:
            self.waveform_label.configure(text="No se pudo generar la forma de onda", image="")
        self.is_generating_waveform = False
        self.set_progress(0.0)
        self.set_status("Error generando forma de onda")
        messagebox.showerror(APP_NAME, message)

    def start_url_extraction(self) -> None:
        if self.is_extracting_url:
            messagebox.showinfo(APP_NAME, "Ya hay una extracción URL en curso.")
            return

        url = self.url_value.get().strip()
        if not url:
            self.show_error("No se ha introducido ninguna URL.")
            return
        if not self.url_output_dir.get():
            self.show_error("No se ha seleccionado carpeta de salida para la URL.")
            return

        yt_dlp = find_binary("yt-dlp")
        if not yt_dlp:
            self.show_error("No se ha encontrado yt-dlp. Añádelo a bin/ o al PATH.")
            return
        yt_dlp_prefix = yt_dlp_command_prefix(yt_dlp)
        if yt_dlp_prefix == [yt_dlp] and not os.access(yt_dlp, os.X_OK):
            self.show_error(f"yt-dlp no tiene permisos de ejecución:\n{yt_dlp}")
            return

        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            self.show_error("No se ha encontrado ffmpeg. Añádelo a bin/ o al PATH.")
            return
        if not os.access(ffmpeg, os.X_OK):
            self.show_error(f"ffmpeg no tiene permisos de ejecución:\n{ffmpeg}")
            return

        self.cancel_requested.clear()
        self.is_extracting_url = True
        self.set_status("Extrayendo audio desde URL...")
        self.set_progress(0.15)
        self._clear_url_results()
        self._add_url_status("Procesando URL...", "En curso")
        threading.Thread(target=self.extract_url_audio, daemon=True).start()

    def extract_url_audio(self) -> None:
        url = self.url_value.get().strip()
        output_dir = Path(self.url_output_dir.get())
        before_files = self._audio_files_in_folder(output_dir)
        command = self._build_url_extraction_command(url, output_dir)

        self.log_message("")
        self.log_message("=== YouTube / URL ===")
        self.log_message(f"URL: {url}")
        self.log_message("Modo: extraer solo el vídeo indicado, ignorar playlists/radio y convertir a MP3")
        self.log_message(f"Carpeta de salida: {output_dir}")
        self.log_message(f"Runtime JS: {js_runtime_label()}")
        self.after(0, lambda: self.set_progress(0.35))

        try:
            returncode, stdout, stderr = self._run_url_command(command)
            if returncode != 0 and self._is_ssl_certificate_error(stdout, stderr):
                self.log_message(
                    "Certificados SSL del sistema antiguos o incompletos. Reintentando en modo compatibilidad SSL."
                )
                self.after(0, lambda: self.set_status("Reintentando YouTube por SSL..."))
                self.after(0, lambda: self.set_progress(0.45))
                retry_command = self._build_url_extraction_command(url, output_dir, skip_certificate_check=True)
                returncode, stdout, stderr = self._run_url_command(retry_command)
        except OSError as exc:
            self.after(0, lambda: self._handle_url_error(f"No se pudo ejecutar yt-dlp: {exc}"))
            return

        if self.cancel_requested.is_set():
            self.log_message("Extracción URL cancelada por el usuario.")
            self.after(0, lambda: self.set_status("Extracción URL cancelada"))
            self.after(0, self._finish_url_extraction)
            return

        if returncode != 0:
            error = stderr.strip() or stdout.strip() or "yt-dlp falló sin mensaje de error."
            self.after(0, lambda: self._handle_url_error(error))
            return

        after_files = self._audio_files_in_folder(output_dir)
        generated = sorted(after_files - before_files)
        finished_status = "Audio extraído correctamente"
        if generated:
            self.log_message("Archivos generados:")
            for path in generated:
                self.log_message(f"- {path.name} ({format_size(path)})")
                self.after(0, lambda p=path: self._add_url_result(p, "Listo"))
        else:
            self.log_message("yt-dlp finalizó correctamente. No se detectaron archivos de audio nuevos en la carpeta.")
            self.after(0, lambda: self._add_url_status("Sin archivos nuevos detectados", "Finalizado"))
            if stdout.strip():
                self.log_message(stdout.strip())
            if stderr.strip():
                self.log_message(stderr.strip())
            finished_status = "Extracción finalizada sin archivos nuevos"

        self.after(0, lambda: self.set_progress(1.0))
        self.after(0, lambda status=finished_status: self.set_status(status))
        self.after(0, self._finish_url_extraction)

    def _run_url_command(self, command: list[str]) -> tuple[int, str, str]:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.current_process = process
        try:
            stdout, stderr = process.communicate()
        finally:
            self.current_process = None
        return process.returncode, stdout, stderr

    def _build_url_extraction_command(
        self,
        url: str,
        output_dir: Path,
        *,
        skip_certificate_check: bool = False,
    ) -> list[str]:
        yt_dlp = find_binary("yt-dlp")
        ffmpeg = find_binary("ffmpeg")
        assert yt_dlp is not None
        assert ffmpeg is not None
        output_template = str(output_dir / "%(title)s [%(id)s].%(ext)s")
        yt_dlp_prefix = yt_dlp_command_prefix(yt_dlp)
        js_flags = js_runtime_flags()
        command = [
            *yt_dlp_prefix,
            *js_flags,
            "-f",
            "bestaudio/best",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "--no-playlist",
            "--no-overwrites",
            "--restrict-filenames",
            "--embed-metadata",
            "--add-metadata",
            "--ffmpeg-location",
            str(Path(ffmpeg).parent),
            "-o",
            output_template,
            url,
        ]
        if skip_certificate_check:
            # Insert after the yt-dlp prefix and any js-runtimes flags so
            # --no-check-certificates stays a yt-dlp option, not a runtime arg.
            insert_at = len(yt_dlp_prefix) + len(js_flags)
            command.insert(insert_at, "--no-check-certificates")
        return command

    def _is_ssl_certificate_error(self, stdout: str, stderr: str) -> bool:
        return "CERTIFICATE_VERIFY_FAILED" in f"{stdout}\n{stderr}"

    def _friendly_url_error(self, message: str) -> str:
        if "CERTIFICATE_VERIFY_FAILED" in message:
            return (
                "YouTube no se ha podido abrir porque macOS/Python no encuentra certificados SSL válidos.\n\n"
                "La app ya ha probado el modo de compatibilidad SSL. Si sigue fallando, revisa en el iMac:\n"
                "1. Que la fecha y hora del sistema sean correctas.\n"
                "2. Que el binario bin/yt-dlp esté actualizado.\n"
                "3. Que la conexión a internet no esté bloqueando YouTube.\n\n"
                "El detalle técnico completo queda guardado en el registro."
            )
        if "unsupported version of Python" in message or "Only Python versions 3.10 and above" in message:
            return (
                "yt-dlp se ha intentado ejecutar con un Python antiguo del sistema.\n\n"
                "Music Tool debe abrirse con Python 3.11 y ahora intenta lanzar el yt-dlp local usando ese mismo Python.\n"
                "Actualiza la app con git pull, abre Music Tool.app o abrir_music_tool.command, y vuelve a probar.\n\n"
                "El detalle técnico completo queda guardado en el registro."
            )
        if "HTTP Error 403" in message or "Sign in" in message:
            return (
                "YouTube ha rechazado esta descarga. Puede ser un vídeo restringido, privado, con edad limitada o bloqueado.\n\n"
                "Prueba otro vídeo o actualiza bin/yt-dlp. El detalle técnico completo queda en el registro."
            )
        return f"No se pudo extraer el audio.\n\nDetalle:\n{message[:700]}"

    def _audio_files_in_folder(self, folder: Path) -> set[Path]:
        return {
            path.resolve()
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_RESULT_EXTENSIONS
        }

    def _add_url_result(self, path: Path, status: str) -> None:
        if not self.url_results_table:
            return
        self.url_results_table.insert(
            "",
            tk.END,
            values=(path.name, path.suffix.replace(".", "").upper(), format_size(path), status),
        )
        self._apply_table_stripes(self.url_results_table)

    def _add_url_status(self, message: str, status: str) -> None:
        if not self.url_results_table:
            return
        self.url_results_table.insert("", tk.END, values=(message, "-", "-", status))
        self._apply_table_stripes(self.url_results_table)

    def _clear_url_results(self) -> None:
        if not self.url_results_table:
            return
        for item in self.url_results_table.get_children():
            self.url_results_table.delete(item)
        self._apply_table_stripes(self.url_results_table)

    def _handle_url_error(self, message: str) -> None:
        self.log_message(f"Error extrayendo URL: {message}")
        self.set_progress(0.0)
        self.set_status("Error extrayendo URL")
        self._finish_url_extraction()
        messagebox.showerror(APP_NAME, self._friendly_url_error(message))

    def _finish_url_extraction(self) -> None:
        self.is_extracting_url = False

    def start_conversion(self) -> None:
        if self.is_converting:
            messagebox.showinfo(APP_NAME, "Ya hay una conversión en curso.")
            return
        if not self.files:
            self.show_error("No hay canciones cargadas.")
            return
        if not self.output_dir.get():
            self.show_error("No se ha seleccionado carpeta de salida.")
            return
        ffmpeg = find_binary("ffmpeg")
        if not ffmpeg:
            self.show_error("No se ha encontrado ffmpeg. Añádelo a bin/ o al PATH.")
            return
        if not os.access(ffmpeg, os.X_OK):
            self.show_error(f"ffmpeg no tiene permisos de ejecución:\n{ffmpeg}")
            return

        self.cancel_requested.clear()
        self.is_converting = True
        self.set_status("Convirtiendo canciones...")
        self.set_progress(0.0)
        threading.Thread(target=self.convert_files, daemon=True).start()

    def cancel_conversion(self) -> None:
        if (
            not self.is_converting
            and not self.is_exporting_editor
            and not self.is_generating_waveform
            and not self.is_extracting_url
        ):
            self.set_status("No hay proceso en curso")
            return

        self.cancel_requested.set()
        process = self.current_process
        if process and process.poll() is None:
            try:
                process.terminate()
            except OSError as exc:
                self.log_message(f"No se pudo detener el proceso: {exc}")
        self.log_message("Cancelación solicitada.")
        self.set_status("Cancelando proceso...")
        self.set_progress(0.0)

    def convert_files(self) -> None:
        try:
            self.log_message("=== Conversión de formatos ===")
            self.log_message(f"Formato de salida: {self.output_format.get()}")
            self.log_message(f"Calidad: {self.quality.get()}")

            files = list(self.files)
            total = max(1, len(files))
            for index, path in enumerate(files):
                if self.cancel_requested.is_set():
                    self.log_message("Conversión cancelada por el usuario.")
                    self.after(0, lambda: self.set_progress(0.0))
                    self.after(0, lambda: self.set_status("Conversión cancelada"))
                    return
                self.after(0, lambda value=index / total: self.set_progress(value))
                self.convert_one_file(path)
                self.after(0, lambda value=(index + 1) / total: self.set_progress(value))

            if self.cancel_requested.is_set():
                self.log_message("Conversión cancelada por el usuario.")
                self.after(0, lambda: self.set_progress(0.0))
                self.after(0, lambda: self.set_status("Conversión cancelada"))
                return

            self.log_message("Conversión finalizada.")
            self.after(0, lambda: self.set_progress(1.0))
            self.after(0, lambda: self.set_status("Conversión finalizada"))
        finally:
            self.after(0, self._finish_conversion)

    def convert_one_file(self, source_path: str) -> None:
        source = Path(source_path)
        output_folder = Path(self.output_dir.get())
        format_name = self.output_format.get()
        output = output_folder / f"{source.stem}{conversion_extension(format_name)}"
        if not self.overwrite.get():
            output = unique_output_path(output)

        self.after(0, lambda: self.update_row(source_path, final_size="-", status="Convirtiendo..."))
        self.log_message("")
        self.log_message(f"Convirtiendo: {source.name}")
        self.log_message(f"Formato/calidad: {format_name} {self.quality.get()}")
        self.log_message(f"Tamaño original: {format_size(source)}")

        command = self._build_conversion_command(source, output, format_name, self.quality.get())

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.current_process = process
            _stdout, stderr = process.communicate()
        except OSError as exc:
            error = f"No se pudo ejecutar ffmpeg: {exc}"
            self.log_message(f"Error: {error}")
            self.after(0, lambda: self.update_row(source_path, status="Error"))
            self.after(0, lambda: messagebox.showerror(APP_NAME, error))
            return
        finally:
            self.current_process = None

        if self.cancel_requested.is_set():
            self.log_message(f"Cancelado: {source.name}")
            self.after(0, lambda: self.update_row(source_path, status="Cancelado"))
            return

        if process.returncode != 0:
            error = stderr.strip() or "FFmpeg falló sin mensaje de error."
            self.log_message(f"Error: {error}")
            self.after(0, lambda: self.update_row(source_path, status="Error"))
            self.after(0, lambda: messagebox.showerror(APP_NAME, f"Error convirtiendo {source.name}:\n\n{error}"))
            return

        final_size = format_size(output)
        difference = size_change_percent(source, output)
        self.log_message(f"Tamaño final: {final_size}")
        self.log_message(f"Diferencia aproximada: {difference}")
        self.log_message(f"Guardado en: {output}")
        self.after(
            0,
            lambda: self.update_row(
                source_path,
                final_size=final_size,
                quality=self.quality.get(),
                status="Listo",
            ),
        )

    def _build_conversion_command(self, source: Path, output: Path, format_name: str, quality: str) -> list[str]:
        ffmpeg = find_binary("ffmpeg")
        assert ffmpeg is not None
        command = [
            ffmpeg,
            "-hide_banner",
            "-y" if self.overwrite.get() else "-n",
            "-i",
            str(source),
            "-vn",
            "-map_metadata",
            "0",
        ]
        if format_name == "MP3":
            command.extend(["-codec:a", "libmp3lame", "-b:a", quality, "-id3v2_version", "3"])
        elif format_name == "AAC/M4A":
            command.extend(["-codec:a", "aac", "-b:a", quality])
        elif format_name == "FLAC":
            command.extend(["-codec:a", "flac", "-compression_level", flac_compression_value(quality)])
        elif format_name == "WAV":
            command.extend(["-codec:a", "pcm_s16le"])
        else:
            command.extend(["-codec:a", "libmp3lame", "-b:a", quality, "-id3v2_version", "3"])
        command.append(str(output))
        return command

    def update_row(
        self,
        item: str,
        *,
        final_size: str | None = None,
        quality: str | None = None,
        status: str | None = None,
    ) -> None:
        if not self.table.exists(item):
            return
        values = list(self.table.item(item, "values"))
        if final_size is not None:
            values[3] = final_size
        if quality is not None:
            values[4] = quality
        if status is not None:
            values[5] = status
        self.table.item(item, values=values)

    def _finish_conversion(self) -> None:
        self.is_converting = False
        self.current_process = None

    def log_message(self, message: str) -> None:
        def append() -> None:
            self.log.insert(tk.END, message + "\n")
            self.log.see(tk.END)

        self.after(0, append)

    def set_status(self, message: str) -> None:
        self.status.set(message)

    def set_progress(self, value: float) -> None:
        self.progress.set(max(0.0, min(1.0, value)))

    def show_error(self, message: str) -> None:
        self.log_message(f"Error: {message}")
        self.set_progress(0.0)
        self.set_status("Error")
        messagebox.showerror(APP_NAME, message)

    def not_ready(self) -> None:
        message = "Esta función se activará en la siguiente fase."
        self.log_message(message)
        self.set_status(message)
        messagebox.showinfo(APP_NAME, message)


def main() -> None:
    app = MusicToolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
