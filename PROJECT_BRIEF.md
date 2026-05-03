# Project Brief - Music Tool

Music Tool es una aplicación local de escritorio para macOS Catalina orientada a gestionar una biblioteca musical personal.

## Objetivo

Crear una herramienta estable, ligera y comprensible para:

- convertir canciones o discos entre formatos;
- conservar metadatos originales por defecto;
- editar canciones individuales en fases posteriores;
- generar una forma de onda básica en fases posteriores;
- extraer audio permitido desde URLs usando `yt-dlp` en fases posteriores.

## Restricciones

- Usar Python 3.11 oficial de python.org.
- Usar Tkinter/ttk.
- No usar Electron, React, servidores web ni frameworks pesados.
- No asumir Homebrew.
- Usar ejecutables locales en `bin/` cuando existan.
- Mantener compatibilidad con macOS Catalina.
- No subir `bin/` a Git.

## Fase actual

Fase 1: base estable.

La aplicación implementa conversión a MP3 usando FFmpeg, conserva metadatos con `-map_metadata 0`, evita sobrescritura por defecto y mantiene la interfaz activa mediante `threading.Thread`.

La pestaña Editor ya puede cargar una canción, leer información técnica con `ffprobe`, rellenar los campos de metadatos editables, generar una forma de onda estática con FFmpeg y exportar una versión MP3 editada. La guía visual permite arrastrar inicio, final, fade in y fade out. La exportación usa `-map_metadata 0` y solo añade overrides para metadatos rellenos que hayan cambiado.

La pestaña YouTube / URL ya permite introducir una URL, seleccionar carpeta y ejecutar `yt-dlp` en segundo plano usando el FFmpeg local cuando está disponible. Extrae la mejor pista de audio disponible sin forzar recodificación y muestra una tabla de resultados.

La pestaña Conversión ya soporta MP3, AAC/M4A, FLAC y WAV con opciones de calidad por formato.

## Siguiente fase recomendada

Fase 2: mejorar UX de las tres pestañas sin cambiar la arquitectura ni introducir dependencias.
