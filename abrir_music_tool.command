#!/bin/bash
cd "$(dirname "$0")"

# Music Tool needs Python 3.10+ with Tkinter.
# Prefer the python.org 3.11 build the project targets (iMac/Catalina),
# then fall back to any Homebrew/system Python that ships Tkinter so the
# app also runs on newer machines where only 3.10/3.13/3.14 are installed.
PY_CANDIDATES=(
  "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
  "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3.10"
  "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"
  "python3.11"
  "python3.10"
  "python3.13"
  "python3.14"
  "python3"
)

for candidate in "${PY_CANDIDATES[@]}"; do
  if command -v "$candidate" >/dev/null 2>&1 || [ -x "$candidate" ]; then
    if "$candidate" -c "import tkinter" >/dev/null 2>&1; then
      exec "$candidate" app.py
    fi
  fi
done

echo "No se ha encontrado Python 3.10+ con Tkinter."
echo "Instala Python 3.11 desde https://www.python.org/downloads/ y vuelve a intentarlo."
exit 1