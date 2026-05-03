# Music Tool

Music Tool es una aplicación local y ligera para macOS que ayuda a convertir canciones dentro de una biblioteca musical personal.

Esta primera fase crea una base estable en Python 3.11 y Tkinter/ttk, sin Electron, sin servidor web y sin dependencias pesadas.

## Requisitos

- macOS Catalina o superior.
- Python 3.11 oficial de python.org con Tkinter.
- `ffmpeg` en `bin/ffmpeg` o disponible en el `PATH`.

La carpeta `bin/` está pensada para ejecutables locales:

```txt
bin/
├── ffmpeg
├── ffprobe
└── yt-dlp
```

Los binarios no se suben a Git.

## Ejecutar

Desde Terminal:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 app.py
```

En macOS también puedes abrir:

```txt
abrir_music_tool.command
```

## Fase 1 incluida

- Interfaz Tkinter/ttk ligera.
- Pestañas base para Conversión, Editor de canción y YouTube / URL.
- Estética inspirada en iTunes clásico: fondo metálico, cabecera tipo reproductor y paneles redondeados.
- Cabecera simplificada con acciones por icono: `▶` para iniciar y `■` para parar.
- Conversión a MP3, AAC/M4A, FLAC y WAV con calidad/opciones por formato.
- Conservación de metadatos originales con `-map_metadata 0`.
- No sobrescribe archivos por defecto.
- Genera nombres únicos si el destino ya existe.
- Procesa conversiones en un hilo para no bloquear la interfaz.
- Permite cancelar la conversión y detener el FFmpeg activo.
- Muestra peso original, peso final, calidad y estado.
- El Editor puede cargar una canción y leer duración, peso, bitrate y metadatos con `ffprobe`.
- El Editor puede exportar una versión `_editado.mp3` con corte, fade in/out, volumen y metadatos modificados.
- El Editor puede generar y mostrar una forma de onda estática con FFmpeg.
- El Editor muestra una guía visual interactiva: puedes arrastrar inicio, final, fade in y fade out.
- La pestaña YouTube / URL extrae la mejor pista de audio disponible con `yt-dlp`, sin forzar recodificación ni selector de calidad.
- La pestaña YouTube / URL muestra una tabla de resultados.

## Vista previa visual

Durante el desarrollo se puede regenerar una vista previa aproximada de la interfaz:

```bash
python3 tools/render_ui_preview.py
```

La imagen se guarda en:

```txt
docs/ui_preview.svg
```

Esta vista previa no sustituye a la app real, pero ayuda a revisar cambios visuales sin abrir Tkinter.

## Pendiente

- Refinar numeración de playlists y detalles de progreso en la extracción URL.
- Soporte de exportación del Editor a AAC/M4A, FLAC y WAV.
- Pruebas reales en macOS Catalina con los binarios locales finales.
