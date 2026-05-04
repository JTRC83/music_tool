#!/usr/bin/env python3
"""Music Tool - utilidad local ligera para convertir audio."""

from __future__ import annotations

import os
import json
import platform
import shutil
import subprocess
import sys
import threading
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
METAL_BG = "#b9b9b9"
METAL_LIGHT = "#d7d7d7"
METAL_DARK = "#8f8f8f"
PANEL_FILL = "#f4f4f4"
DISPLAY_FILL = "#d9dec0"
DISPLAY_BORDER = "#7f8572"
BLUE_SELECTED = "#2f82df"
TEXT_DARK = "#202020"


def base_path() -> Path:
    return Path(__file__).resolve().parent


def find_binary(name: str) -> str | None:
    local = base_path() / "bin" / name
    if local.exists():
        return str(local)
    return shutil.which(name)


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


class RoundedSection(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        title: str = "",
        radius: int = 42,
        padding: int = 18,
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
        foreground: str = "#173317",
    ) -> None:
        self.button_height = 30
        self.button_radius = 60
        super().__init__(
            master,
            width=width,
            height=self.button_height,
            bg=PANEL_FILL,
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
        draw_rounded_rect(
            self,
            1,
            1,
            width - 1,
            self.button_height - 1,
            self.button_radius,
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
        super().__init__(master, height=92, bg=METAL_BG, highlightthickness=0, bd=0)
        self.status_var = status_var
        self.progress_var = progress_var
        self.start_command = start_command
        self.stop_command = stop_command
        self.diagnostics_command = diagnostics_command
        self.logo_photo = self._load_logo()
        self.pressed_tag: str | None = None
        self.button_bounds: dict[str, tuple[int, int, int, int]] = {}
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

    def _load_logo(self) -> tk.PhotoImage | None:
        logo_path = base_path() / "assets" / "logomusictool.png"
        if not logo_path.exists():
            return None
        try:
            source = tk.PhotoImage(file=str(logo_path))
            factor = max(1, (max(source.width(), source.height()) + 73) // 74)
            return source.subsample(factor, factor)
        except tk.TclError:
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

    def _status_changed(self, *_args: object) -> None:
        self._paint(max(self.winfo_width(), 620))

    def _redraw(self, event: tk.Event) -> None:
        self._paint(max(int(event.width), 620))

    def _paint(self, width: int) -> None:
        self.delete("all")

        for y in range(0, 92, 3):
            color = "#c8c8c8" if y % 6 == 0 else "#adadad"
            self.create_line(0, y, width, y, fill=color)

        self.create_text(width // 2, 18, text=APP_NAME, font=("Helvetica", 16, "bold"), fill="#111111")

        display_w = min(440, max(320, width - 640))
        display_x = (width - display_w) // 2
        button_y = 54
        start_x = max(126, display_x - 146)
        stop_x = start_x + 64
        logo_x = start_x - 80
        self.button_bounds = {
            "start_button": (start_x - 28, button_y - 28, start_x + 28, button_y + 28),
            "stop_button": (stop_x - 28, button_y - 28, stop_x + 28, button_y + 28),
        }

        if self.logo_photo:
            self.create_oval(
                logo_x - 38,
                button_y - 38,
                logo_x + 38,
                button_y + 38,
                fill="#f2f2f2",
                outline="#7d7d7d",
                width=2,
                tags="logo",
            )
            self.create_image(logo_x, button_y, image=self.logo_photo, tags="logo")
        else:
            self.create_oval(
                logo_x - 25,
                button_y - 25,
                logo_x + 25,
                button_y + 25,
                fill="#f7f7f7",
                outline="#7d7d7d",
                width=2,
                tags="logo",
            )
            self.create_oval(
                logo_x - 18,
                button_y - 18,
                logo_x + 18,
                button_y + 18,
                fill="#d9dec0",
                outline="#6e7562",
                width=1,
                tags="logo",
            )
            self.create_text(logo_x, button_y - 4, text="MT", font=("Helvetica", 14, "bold"), fill="#25301f")
            self.create_text(logo_x, button_y + 11, text="audio", font=("Helvetica", 7, "bold"), fill="#47503c")

        start_pressed = self.pressed_tag == "start_button"
        self.create_oval(
            start_x - 24,
            button_y - 24,
            start_x + 24,
            button_y + 24,
            fill="#dfe9d7" if start_pressed else "#f8f8f8",
            outline="#7d7d7d",
            width=2,
            tags="start_button",
        )
        self.create_arc(
            start_x - 19,
            button_y - 19,
            start_x + 19,
            button_y + 19,
            start=30,
            extent=120,
            outline="#ffffff",
            width=2,
            style=tk.ARC,
            tags="start_button",
        )
        self.create_text(
            start_x + (2 if start_pressed else 1),
            button_y + (2 if start_pressed else 1),
            text="▶",
            font=("Helvetica", 20, "bold"),
            fill="#202020",
            tags="start_button",
        )

        stop_pressed = self.pressed_tag == "stop_button"
        self.create_oval(
            stop_x - 24,
            button_y - 24,
            stop_x + 24,
            button_y + 24,
            fill="#ead8d8" if stop_pressed else "#eeeeee",
            outline="#7d7d7d",
            width=2,
            tags="stop_button",
        )
        self.create_arc(
            stop_x - 19,
            button_y - 19,
            stop_x + 19,
            button_y + 19,
            start=30,
            extent=120,
            outline="#ffffff",
            width=2,
            style=tk.ARC,
            tags="stop_button",
        )
        self.create_rectangle(
            stop_x - 8 + (1 if stop_pressed else 0),
            button_y - 8 + (1 if stop_pressed else 0),
            stop_x + 8 + (1 if stop_pressed else 0),
            button_y + 8 + (1 if stop_pressed else 0),
            fill="#202020",
            outline="#202020",
            tags="stop_button",
        )

        draw_rounded_rect(
            self,
            display_x,
            30,
            display_x + display_w,
            78,
            26,
            fill=DISPLAY_FILL,
            outline=DISPLAY_BORDER,
            width=2,
            tags="display",
        )
        self.create_text(
            display_x + display_w // 2,
            50,
            text=self.status_var.get(),
            font=("Helvetica", 13, "bold"),
            fill="#1b1b1b",
        )
        progress_x1 = display_x + 72
        progress_x2 = display_x + display_w - 72
        progress_y1 = 62
        progress_y2 = 69
        try:
            progress = max(0.0, min(1.0, float(self.progress_var.get())))
        except (tk.TclError, ValueError):
            progress = 0.0
        progress_end = progress_x1 + int((progress_x2 - progress_x1) * progress)
        self.create_rectangle(progress_x1, progress_y1, progress_x2, progress_y2, fill="#e9edcf", outline="#575c4d")
        if progress > 0:
            self.create_rectangle(progress_x1, progress_y1, progress_end, progress_y2, fill="#303030", outline="")

        search_w = 112
        search_x = width - search_w - 56
        self.button_bounds["diagnostics_button"] = (search_x, 39, search_x + search_w, 69)
        diagnostic_pressed = self.pressed_tag == "diagnostics_button"
        draw_rounded_rect(
            self,
            search_x,
            39,
            search_x + search_w,
            69,
            60,
            fill="#cfe7c8" if not diagnostic_pressed else "#b9dcae",
            outline="#6f9366",
            width=2,
            tags="diagnostics_button",
        )
        self.create_text(
            search_x + search_w // 2,
            55,
            text="Diagnóstico",
            font=("Helvetica", 10, "bold"),
            fill="#173317",
            tags="diagnostics_button",
        )


class MusicToolApp(Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x820")
        self.minsize(1020, 740)

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
            "blue": ("#3667e8", "#2756d4", "#1d47af", "#ffffff"),
            "green": ("#d7ead2", "#bdddb6", "#6f9366", "#173317"),
            "silver": ("#f2f2f2", "#dedede", "#8f8f8f", "#303030"),
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
        root = tk.Frame(self, bg=METAL_BG, padx=12, pady=10)
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

        controls = tk.Frame(self.conversion_tab, bg=METAL_BG)
        controls.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 8))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(3, weight=1)

        songs_panel = RoundedSection(controls, "1. Canciones", min_height=185, min_width=340)
        songs_panel.grid(row=0, column=1, sticky="n", padx=(0, 8))
        songs = songs_panel.content
        songs.columnconfigure(0, weight=1)
        self._action_button(songs, "Añadir canciones", self.add_files, width=190, tone="blue").grid(
            row=0, column=0, padx=4, pady=4
        )
        self._action_button(songs, "Quitar seleccionado", self.remove_selected, width=190, tone="silver").grid(
            row=1, column=0, padx=4, pady=4
        )
        self._action_button(songs, "Vaciar lista", self.clear_files, width=190, tone="silver").grid(
            row=2, column=0, padx=4, pady=4
        )

        output_panel = RoundedSection(controls, "2. Salida", min_height=185, min_width=390)
        output_panel.grid(row=0, column=2, sticky="n", padx=(8, 0))
        output = output_panel.content
        output.columnconfigure(1, weight=1)
        self._action_button(output, "Seleccionar carpeta", self.choose_output_dir, width=190, tone="blue").grid(
            row=0, column=0, columnspan=2, padx=4, pady=4
        )
        ttk.Label(output, text="Formato").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(output, textvariable=self.output_format, values=CONVERSION_FORMATS, width=10, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Label(output, text="Calidad").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.quality_combobox = ttk.Combobox(
            output,
            textvariable=self.quality,
            values=MP3_QUALITIES,
            width=14,
            state="readonly",
        )
        self.quality_combobox.grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Checkbutton(output, text="Sobrescribir existentes", variable=self.overwrite).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=4, pady=4
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
        if hasattr(self, "quality_combobox"):
            self.quality_combobox.configure(values=options)
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

        self.log = tk.Text(log_frame, height=8, wrap=tk.WORD, relief=tk.FLAT, bg="#f7f7f7")
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
        for name in ("ffmpeg", "ffprobe", "yt-dlp"):
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
        if not os.access(path, os.X_OK):
            return [("SIN PERMISO", name, f"{path} - ejecuta chmod +x")]

        version = self._binary_version(name, path)
        return [
            ("OK", name, f"{location} - {path}"),
            ("OK", f"{name} versión", version),
        ]

    def _binary_version(self, name: str, path: str) -> str:
        command = [path, "--version"] if name == "yt-dlp" else [path, "-version"]
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
        header = tk.Frame(window, bg=header_color, padx=18, pady=14)
        header.pack(fill=tk.X, padx=14, pady=(14, 8))
        tk.Label(header, text=header_text, bg=header_color, fg="#1f2a1f", font=("Helvetica", 18, "bold")).pack(anchor=tk.W)
        tk.Label(
            header,
            text="Python, Tkinter, permisos y binarios locales comprobados.",
            bg=header_color,
            fg="#2f3f2f",
            font=("Helvetica", 12),
        ).pack(anchor=tk.W, pady=(4, 0))

        table_frame = tk.Frame(window, bg=METAL_BG, padx=14)
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

        buttons = tk.Frame(window, bg=METAL_BG, padx=14, pady=12)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Cerrar", command=window.destroy).pack(side=tk.RIGHT)

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

        metadata_panel = RoundedSection(self.editor_tab, "2. Metadatos", min_height=260)
        metadata_panel.grid(row=1, column=0, sticky="ew", padx=(4, 8), pady=4)
        metadata = metadata_panel.content
        metadata.columnconfigure(1, weight=1)
        for row, (key, label) in enumerate(METADATA_FIELDS):
            self.editor_metadata_vars[key] = StringVar(value="")
            ttk.Label(metadata, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            entry = ttk.Entry(metadata, textvariable=self.editor_metadata_vars[key], state="disabled")
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
            self.editor_metadata_entries[key] = entry

        edits_panel = RoundedSection(self.editor_tab, "3. Edición y exportación", min_height=292)
        edits_panel.grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=4)
        edits = edits_panel.content
        edits.columnconfigure(1, weight=1)
        edits.columnconfigure(2, weight=0)
        self.editor_start = StringVar(value="")
        self.editor_end = StringVar(value="")
        self.editor_fade_in = StringVar(value="")
        self.editor_fade_out = StringVar(value="")
        self.editor_volume = StringVar(value="1.0")
        edit_rows = (
            ("Inicio", self.editor_start),
            ("Final", self.editor_end),
            ("Fade in", self.editor_fade_in),
            ("Fade out", self.editor_fade_out),
            ("Volumen", self.editor_volume),
        )
        for row, (label, variable) in enumerate(edit_rows):
            ttk.Label(edits, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
            ttk.Entry(edits, textvariable=variable, state="normal").grid(row=row, column=1, sticky="ew", padx=4, pady=3)
            variable.trace_add("write", self._redraw_editor_visual)
        ttk.Label(edits, text="Formato").grid(row=5, column=0, sticky="w", padx=4, pady=(8, 3))
        ttk.Combobox(edits, textvariable=self.editor_output_format, values=EDITOR_OUTPUT_FORMATS, width=10, state="readonly").grid(
            row=5, column=1, sticky="ew", padx=4, pady=(8, 3)
        )
        ttk.Label(edits, text="Calidad").grid(row=6, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(edits, textvariable=self.editor_quality, values=MP3_QUALITIES, width=10, state="readonly").grid(
            row=6, column=1, sticky="ew", padx=4, pady=3
        )
        self._action_button(edits, "Seleccionar carpeta", self.choose_editor_output_dir, width=145, tone="silver").grid(
            row=0, column=2, sticky="e", padx=(14, 4), pady=4
        )
        self._action_button(edits, "Generar forma", self.start_waveform_generation, width=135, tone="blue").grid(
            row=1, column=2, sticky="e", padx=(14, 4), pady=4
        )
        self._action_button(edits, "Exportar editada", self.start_editor_export, width=135, tone="green").grid(
            row=2, column=2, sticky="e", padx=(14, 4), pady=4
        )
        ttk.Checkbutton(edits, text="Sobrescribir", variable=self.editor_overwrite).grid(
            row=7, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 3)
        )
        ttk.Label(edits, textvariable=self.editor_output_dir, anchor=tk.W).grid(
            row=8, column=0, columnspan=3, sticky="ew", padx=4, pady=(3, 3)
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
        draw_rounded_rect(canvas, left, top, right, bottom, 16, fill="#ffffff", outline="#a1a1a1", tags="visual")

        duration = self.editor_duration_seconds if self.editor_duration_seconds and self.editor_duration_seconds > 0 else 240.0
        try:
            start = parse_time_value(self.editor_start.get()) or 0.0
            end = parse_time_value(self.editor_end.get()) or duration
            fade_in = parse_optional_float(self.editor_fade_in.get(), "Fade in") or 0.0
            fade_out = parse_optional_float(self.editor_fade_out.get(), "Fade out") or 0.0
            volume = parse_optional_float(self.editor_volume.get(), "Volumen") or 1.0
        except ValueError:
            canvas.create_text(left + 12, mid + 4, text="Valores de edición pendientes de corregir", anchor=tk.W, fill="#9a3b2f")
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
        canvas.create_line(x_start, base_y, x_end, base_y, fill="#b4b4b4", dash=(4, 4))
        canvas.create_line(x_start, volume_y, x_end, volume_y, fill="#202020", width=2)
        canvas.create_text(x_start + 8, volume_y - 6, text=f"vol {volume:g}", anchor=tk.W, font=("Helvetica", 9), fill="#202020")

        self._draw_timeline_marker(canvas, x_start, top, bottom, "inicio", "#2f82df")
        self._draw_timeline_marker(canvas, x_end, top, bottom, "final", "#2f82df")
        self._draw_timeline_handle(canvas, fade_in_x, mid, "fade in", "#315f9c")
        self._draw_timeline_handle(canvas, fade_out_x, mid, "fade out", "#64469c")
        canvas.create_text(left, bottom + 14, text="0:00", anchor=tk.W, font=("Helvetica", 9), fill="#555555")
        canvas.create_text(right, bottom + 14, text=format_duration(duration), anchor=tk.E, font=("Helvetica", 9), fill="#555555")

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
        if not os.access(yt_dlp, os.X_OK):
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
        self.log_message("Modo: extraer la mejor pista de audio disponible y convertirla a MP3")
        self.log_message(f"Carpeta de salida: {output_dir}")
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
        command = [
            yt_dlp,
            "-f",
            "bestaudio/best",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
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
            command.insert(1, "--no-check-certificates")
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
