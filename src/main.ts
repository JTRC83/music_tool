/**
 * Music Tool — Entry point
 * Vanilla TypeScript, sin framework. Controla tabs, diales, API calls.
 */
import './styles/itunes.css';
import './styles/amp.css';
import './styles/onoff-btn.css';
import './styles/button.css';

// ── Types ───────────────────────────────────────────────

interface SongRow {
  path: string;
  name: string;
  format: string;
  originalSize: string;
  finalSize: string;
  quality: string;
  status: string;
}

// ── State ───────────────────────────────────────────────

const state = {
  files: [] as string[],
  outputDir: '',
  format: 'MP3',
  quality: '320k',
  overwrite: false,
  editorOutputDir: '',
  editorFilePath: '',
  editorDuration: 0,
  urlOutputDir: '',
  isConverting: false,
};

const CONVERSION_FORMATS = ['MP3', 'AAC/M4A', 'FLAC', 'WAV'];
const QUALITY_OPTIONS: Record<string, string[]> = {
  'MP3': ['128k', '192k', '256k', '320k'],
  'AAC/M4A': ['128k', '182k', '256k'],
  'FLAC': ['Compresión 0', 'Compresión 4', 'Compresión 5', 'Compresión 8'],
  'WAV': ['Sin compresión'],
};

// ── API helpers ─────────────────────────────────────────

async function api(path: string, body?: unknown) {
  const res = await fetch(`/api/${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

// ── Log ─────────────────────────────────────────────────

function log(message: string) {
  const el = document.getElementById('log-output')!;
  el.textContent += message + '\n';
  el.scrollTop = el.scrollHeight;
}

function setStatus(message: string) {
  document.getElementById('status-text')!.textContent = message;
}

function setProgress(value: number) {
  const fill = document.getElementById('loader-fill')!;
  fill.style.width = `${Math.round(value * 100)}%`;
  if (value > 0) fill.classList.add('active');
  else fill.classList.remove('active');
}

// ── Tabs ────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tabId = btn.getAttribute('data-tab')!;
    document.getElementById(`tab-${tabId}`)!.classList.add('active');
  });
});

// ── Dial widget ─────────────────────────────────────────

function createDial(container: HTMLElement, options: string[], initial: string, onChange: (val: string) => void) {
  // Clone the container to remove old event listeners that accumulate on rebuild
  const newContainer = container.cloneNode(false) as HTMLElement;
  container.parentNode?.replaceChild(newContainer, container);
  container = newContainer;
  // Restore the id so getElementById still works
  const oldId = newContainer.getAttribute('id') || '';

  const wrapper = container.closest('.dial-wrapper') as HTMLElement;
  if (wrapper) wrapper.querySelectorAll('.cw-dial-label').forEach(l => l.remove());

  const n = options.length;
  const labels: HTMLElement[] = [];

  // notches + dial indicator go inside the .cw-input disc
  const notches = document.createElement('div');
  notches.className = 'cw-notches';

  const dial = document.createElement('div');
  dial.className = 'cw-dial';
  dial.style.zIndex = '10';

  options.forEach((opt, i) => {
    // notch tick inside the disc, at this option's angle
    const notch = document.createElement('div');
    notch.className = 'cw-notch';
    const angle = i * (360 / n);
    const rad = (angle - 90) * Math.PI / 180;
    const tickR = 26;
    const tx = Math.cos(rad) * tickR;
    const ty = Math.sin(rad) * tickR;
    notch.style.transform = `translate(calc(-50% + ${tx}px), calc(-50% + ${ty}px)) rotate(${angle}deg)`;
    notches.appendChild(notch);

    // label OUTSIDE the disc, positioned relative to .dial-wrapper (140x140)
    // disc center is at (70, 90) within the wrapper (60px disc centered horizontally, 60px from top)
    const label = document.createElement('div');
    label.className = 'cw-dial-label';
    label.textContent = opt;
    const labelR = 62;
    const cx = 70, cy = 90;
    const lx = cx + Math.cos(rad) * labelR;
    const ly = cy + Math.sin(rad) * labelR;
    label.style.left = `${lx}px`;
    label.style.top = `${ly}px`;
    if (wrapper) wrapper.appendChild(label);
    else container.appendChild(label);
    labels.push(label);
  });

  container.appendChild(notches);
  container.appendChild(dial);

  function update(selected: string) {
    const idx = options.indexOf(selected);
    if (idx < 0) return;
    // -90 offset so idx=0 points up (matching where labels start)
    const rotation = idx * (360 / n) - 90;
    dial.style.transform = `rotate(${rotation}deg)`;
    labels.forEach((l, i) => {
      l.style.fontWeight = i === idx ? '700' : '400';
      l.style.color = i === idx ? 'var(--text)' : 'var(--text-light)';
    });
    onChange(selected);
  }

  // click on the disc cycles to next option
  container.addEventListener('click', (e) => {
    if ((e.target as HTMLElement).classList.contains('cw-dial-label')) return;
    const rot = parseFloat(dial.style.transform.match(/rotate\(([\d.]+)deg\)/)?.[1] || '-90');
    // undo the -90 offset to get the real index
    const currentIdx = Math.round((rot + 90) / (360 / n)) % n;
    const next = ((currentIdx < 0 ? 0 : currentIdx) + 1) % n;
    update(options[next]);
  });

  // click on a label selects that option directly
  labels.forEach((label, i) => {
    label.addEventListener('click', (e) => {
      e.stopPropagation();
      update(options[i]);
    });
  });

  update(initial);
  return { update, setOptions: (newOptions: string[], newInitial: string) => {
    createDial(document.getElementById(oldId) as HTMLElement, newOptions, newInitial, onChange);
  }};
}

// ── Folder browser modal ─────────────────────────────────
// Reusable dialog that navigates real filesystem folders via /api/browse.

let currentBrowsePath = '';

async function browseFolder(title: string): Promise<string | null> {
  return new Promise((resolveFn) => {
    const overlay = document.createElement('div');
    overlay.className = 'browse-overlay';
    const modal = document.createElement('div');
    modal.className = 'browse-modal';
    const header = document.createElement('div');
    header.className = 'browse-header';
    header.innerHTML = `<span>${title}</span>`;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'browse-close';
    closeBtn.textContent = '✕';
    closeBtn.onclick = () => { overlay.remove(); resolveFn(null); };
    header.appendChild(closeBtn);
    const pathDisplay = document.createElement('div');
    pathDisplay.className = 'browse-path';
    const list = document.createElement('div');
    list.className = 'browse-list';
    const selectBtn = document.createElement('button');
    selectBtn.className = 'browse-select-btn';
    selectBtn.textContent = 'Seleccionar esta carpeta';
    selectBtn.disabled = true;
    modal.appendChild(header);
    modal.appendChild(pathDisplay);
    modal.appendChild(list);
    modal.appendChild(selectBtn);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    let selectedPath: string | null = null;

    async function loadDir(path: string) {
      currentBrowsePath = path;
      pathDisplay.textContent = path;
      selectedPath = path;
      selectBtn.disabled = false;
      try {
        const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (data.error) { list.innerHTML = `<div class="browse-error">${data.error}</div>`; return; }
        list.innerHTML = '';
        if (data.parent) {
          const parentItem = document.createElement('div');
          parentItem.className = 'browse-item browse-parent';
          parentItem.innerHTML = '📁 ..';
          parentItem.onclick = () => loadDir(data.parent);
          list.appendChild(parentItem);
        }
        for (const folder of data.folders || []) {
          const item = document.createElement('div');
          item.className = 'browse-item browse-folder';
          item.innerHTML = `📁 ${folder}`;
          item.onclick = () => loadDir(join(data.current, folder));
          list.appendChild(item);
        }
        for (const file of data.audioFiles || []) {
          const item = document.createElement('div');
          item.className = 'browse-item browse-file';
          item.innerHTML = `🎵 ${file}`;
          list.appendChild(item);
        }
      } catch (err) { list.innerHTML = `<div class="browse-error">Error: ${err}</div>`; }
    }
    function join(base: string, name: string): string { return base.endsWith('/') ? base + name : base + '/' + name; }
    selectBtn.onclick = () => { if (selectedPath) { overlay.remove(); resolveFn(selectedPath); } };
    overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.remove(); resolveFn(null); } });
    loadDir('');
  });
}

// ── Folder + file picker modal ───────────────────────────

async function browseAndPickFiles(title: string): Promise<string[] | null> {
  return new Promise(async (resolveFn) => {
    const overlay = document.createElement('div');
    overlay.className = 'browse-overlay';
    const modal = document.createElement('div');
    modal.className = 'browse-modal browse-modal-wide';
    const header = document.createElement('div');
    header.className = 'browse-header';
    header.innerHTML = `<span>${title}</span>`;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'browse-close';
    closeBtn.textContent = '✕';
    closeBtn.onclick = () => { overlay.remove(); resolveFn(null); };
    header.appendChild(closeBtn);
    const pathDisplay = document.createElement('div');
    pathDisplay.className = 'browse-path';
    const list = document.createElement('div');
    list.className = 'browse-list browse-list-tall';
    const selectBtn = document.createElement('button');
    selectBtn.className = 'browse-select-btn';
    selectBtn.textContent = 'Añadir seleccionadas';
    selectBtn.disabled = true;
    modal.appendChild(header);
    modal.appendChild(pathDisplay);
    modal.appendChild(list);
    modal.appendChild(selectBtn);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const selectedFiles: Set<string> = new Set();

    async function loadDir(path: string) {
      currentBrowsePath = path;
      pathDisplay.textContent = path;
      try {
        const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
        const data = await res.json();
        if (data.error) { list.innerHTML = `<div class="browse-error">${data.error}</div>`; return; }
        list.innerHTML = '';
        if (data.parent) {
          const parentItem = document.createElement('div');
          parentItem.className = 'browse-item browse-parent';
          parentItem.innerHTML = '📁 ..';
          parentItem.onclick = () => loadDir(data.parent);
          list.appendChild(parentItem);
        }
        for (const folder of data.folders || []) {
          const item = document.createElement('div');
          item.className = 'browse-item browse-folder';
          item.innerHTML = `📁 ${folder}`;
          item.onclick = () => loadDir(join(data.current, folder));
          list.appendChild(item);
        }
        for (const file of data.audioFiles || []) {
          const fullPath = join(data.current, file);
          const item = document.createElement('div');
          item.className = 'browse-item browse-file browse-file-selectable';
          item.innerHTML = `🎵 ${file}`;
          if (selectedFiles.has(fullPath)) item.classList.add('browse-file-selected');
          item.onclick = (e) => {
            e.stopPropagation();
            if (selectedFiles.has(fullPath)) { selectedFiles.delete(fullPath); item.classList.remove('browse-file-selected'); }
            else { selectedFiles.add(fullPath); item.classList.add('browse-file-selected'); }
            selectBtn.disabled = selectedFiles.size === 0;
          };
          list.appendChild(item);
        }
      } catch (err) { list.innerHTML = `<div class="browse-error">Error: ${err}</div>`; }
    }
    function join(base: string, name: string): string { return base.endsWith('/') ? base + name : base + '/' + name; }
    selectBtn.onclick = () => { if (selectedFiles.size > 0) { overlay.remove(); resolveFn(Array.from(selectedFiles)); } };
    overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.remove(); resolveFn(null); } });
    loadDir('');
  });
}

async function browseAndPickOneFile(title: string): Promise<string | null> {
  const files = await browseAndPickFiles(title);
  if (files && files.length > 0) return files[0];
  return null;
}

// ── Conversion tab ──────────────────────────────────────

// Calidad dial must be created FIRST so the formato callback can reference it
const dialCalidad = createDial(
  document.getElementById('dial-calidad')!,
  QUALITY_OPTIONS['MP3'],
  '320k',
  (val) => {
    state.quality = val;
  }
);

const dialFormato = createDial(
  document.getElementById('dial-formato')!,
  CONVERSION_FORMATS,
  'MP3',
  (val) => {
    state.format = val;
    // update quality dial with new options
    const qualities = QUALITY_OPTIONS[val] || ['128k'];
    state.quality = qualities[0];
    dialCalidad.setOptions(qualities, state.quality);
  }
);

document.getElementById('btn-add-files')!.addEventListener('click', async () => {
  const files = await browseAndPickFiles('Selecciona canciones');
  if (!files || files.length === 0) return;
  files.forEach(p => {
    const name = p.split('/').pop() || p;
    state.files.push(p);
    addSongRow(p, name);
  });
  log(`Añadidas ${files.length} canciones`);
});

function addSongRow(path: string, name: string) {
  const tbody = document.querySelector('#songs-table tbody')!;
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${name}</td><td>${state.format}</td><td>-</td><td>-</td><td>${state.quality}</td><td>Pendiente</td>`;
  tr.dataset.path = path;
  tbody.appendChild(tr);
}

document.getElementById('btn-remove-selected')!.addEventListener('click', () => {
  const selected = document.querySelector('#songs-table tbody tr.selected');
  if (selected) {
    const path = selected.getAttribute('data-path')!;
    state.files = state.files.filter(f => f !== path);
    selected.remove();
    log('Canción quitada de la lista');
  }
});

document.getElementById('btn-clear-files')!.addEventListener('click', () => {
  state.files = [];
  document.querySelector('#songs-table tbody')!.innerHTML = '';
  log('Lista vaciada');
});

document.getElementById('btn-output-dir')!.addEventListener('click', async () => {
  const dir = await browseFolder('Selecciona carpeta de salida');
  if (dir) {
    state.outputDir = dir;
    document.getElementById('output-label')!.textContent = `Carpeta de salida: ${dir}`;
    log(`Carpeta de salida: ${dir}`);
  }
});

document.getElementById('chk-overwrite')!.addEventListener('change', (e) => {
  state.overwrite = (e.target as HTMLInputElement).checked;
});

// ── Amp power control ──────────────────────────────────

function ampPower(on: boolean) {
  const checkbox = document.getElementById('vx-pwr') as HTMLInputElement;
  if (checkbox) checkbox.checked = on;
  const playBtn = document.getElementById('btn-play')!;
  if (on) playBtn.classList.add('onoff-btn-active');
  else playBtn.classList.remove('onoff-btn-active');
}

document.getElementById('btn-play')!.addEventListener('click', async () => {
  if (state.isConverting || state.files.length === 0) return;
  if (!state.outputDir) { log('Selecciona una carpeta de salida'); return; }

  state.isConverting = true;
  setStatus('Convirtiendo...');
  setProgress(0.1);
  ampPower(true);

  const tbody = document.querySelector('#songs-table tbody')!;
  const rows = tbody.querySelectorAll('tr');
  const total = rows.length;

  for (let i = 0; i < total; i++) {
    if (!state.isConverting) break;
    const row = rows[i];
    const path = row.getAttribute('data-path')!;
    row.cells[5].textContent = 'Convirtiendo...';

    const result = await api('convert', {
      files: [path],
      outputDir: state.outputDir,
      format: state.format,
      quality: state.quality,
      overwrite: state.overwrite,
    });

    if (result.results?.[0]?.status === 'OK') {
      row.cells[3].textContent = formatBytes(result.results[0].outputSize);
      row.cells[5].textContent = 'OK';
    } else {
      row.cells[5].textContent = 'Error';
    }
    setProgress(0.1 + (0.9 * (i + 1) / total));
  }

  setStatus('Conversión completada');
  setProgress(1);
  ampPower(false);
  setTimeout(() => setProgress(0), 2000);
  state.isConverting = false;
});

document.getElementById('btn-stop')!.addEventListener('click', () => {
  state.isConverting = false;
  setStatus('Detenido');
  setProgress(0);
  ampPower(false);
  log('Conversión cancelada por el usuario');
});

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Diagnostics ─────────────────────────────────────────

document.getElementById('btn-diag')!.addEventListener('click', async () => {
  const data = await api('diagnostics');
  if (!data.items) return;

  const modal = document.createElement('div');
  modal.className = 'diag-modal';
  modal.innerHTML = `
    <div class="diag-modal-content">
      <h2>Diagnóstico de Music Tool</h2>
      <table class="diag-table">
        ${data.items.map((item: any) => `
          <tr>
            <td style="font-weight:700;color:${item.status === 'OK' ? 'green' : 'red'}">${item.status}</td>
            <td>${item.label}</td>
            <td style="color:var(--text-light)">${item.detail}</td>
          </tr>
        `).join('')}
      </table>
      <button class="diag-modal-close">Cerrar</button>
    </div>
  `;
  document.body.appendChild(modal);
  modal.querySelector('.diag-modal-close')!.addEventListener('click', () => modal.remove());
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
});

// ── URL tab ─────────────────────────────────────────────

document.getElementById('btn-url-output-dir')!.addEventListener('click', async () => {
  const defaultDir = '/Users/joantoniramoncrespi/Desktop/cançons youtube';
  const dir = prompt('Ruta absoluta de la carpeta de salida:', defaultDir);
  if (dir && dir.trim()) {
    state.urlOutputDir = dir.trim();
    log(`Carpeta URL: ${state.urlOutputDir}`);
  }
});

document.getElementById('btn-extract-url')!.addEventListener('click', async () => {
  const url = (document.getElementById('url-input') as HTMLInputElement).value.trim();
  if (!url) { log('Introduce una URL'); return; }
  if (!state.urlOutputDir) { log('Selecciona una carpeta de salida'); return; }

  setStatus('Extrayendo audio desde URL...');
  setProgress(0.15);
  log(`=== YouTube / URL ===`);
  log(`URL: ${url}`);
  log(`Carpeta de salida: ${state.urlOutputDir}`);

  const result = await api('extract-url', { url, outputDir: state.urlOutputDir });

  if (result.status === 'ok') {
    setProgress(1);
    setStatus('Audio extraído correctamente');
    log('Extracción completada');
    const tbody = document.querySelector('#url-results-table tbody')!;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>Audio extraído</td><td>Listo</td>`;
    tbody.appendChild(tr);
  } else {
    setStatus('Error en la extracción');
    log(`Error: ${result.error || result.stderr}`);
  }
  setTimeout(() => setProgress(0), 2000);
});

// ── Editor tab ──────────────────────────────────────────

document.getElementById('btn-load-editor')!.addEventListener('click', async () => {
  const path = await browseAndPickOneFile('Selecciona una canción');
  if (!path) return;
  const name = path.split('/').pop() || path;
  state.editorFilePath = path;
  document.getElementById('editor-file')!.textContent = name;
  log(`Cargando: ${name}`);

  const result = await api('probe', { filePath: path });
  if (result.error) {
    log(`Error: ${result.error}`);
    return;
  }

  state.editorDuration = result.duration || 0;

  document.getElementById('editor-info')!.textContent =
    `Duración: ${result.durationFormatted} | Peso: ${result.sizeFormatted} | Bitrate: ${result.bitrateFormatted}`;

  const meta = result.metadata || {};
  const fields = ['title', 'artist', 'album', 'date', 'genre', 'composer', 'track'];
  fields.forEach(f => {
    const el = document.getElementById(`meta-${f}`) as HTMLInputElement;
    if (el) { el.value = meta[f] || ''; el.disabled = false; }
  });

  log(`Canción cargada: ${name}`);
});

document.getElementById('btn-editor-output-dir')!.addEventListener('click', async () => {
  const dir = await browseFolder('Selecciona carpeta de salida');
  if (dir) {
    state.editorOutputDir = dir;
    document.getElementById('editor-output-dir')!.textContent = dir;
  }
});

document.getElementById('btn-generate-waveform')!.addEventListener('click', async () => {
  if (!state.editorFilePath) { log('Carga una canción primero'); return; }

  setStatus('Generando forma de onda...');
  const res = await fetch('/api/generate-waveform', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filePath: state.editorFilePath }),
  });
  if (res.ok) {
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const container = document.getElementById('waveform-container')!;
    container.innerHTML = '';
    const canvas = document.createElement('canvas');
    canvas.className = 'waveform-canvas';
    canvas.width = container.clientWidth;
    canvas.height = 200;
    container.appendChild(canvas);
    drawWaveformWithHandles(canvas, url);
    setStatus('Forma de onda generada');
    log('Forma de onda generada');
  } else {
    setStatus('Error generando forma de onda');
    log('Error generando forma de onda');
  }
});

// ── Interactive waveform with draggable handles ───────────

function drawWaveformWithHandles(canvas: HTMLCanvasElement, imgSrc: string) {
  const ctx = canvas.getContext('2d')!;
  const img = new Image();
  const duration = state.editorDuration || 0;

  // handle positions as fraction of canvas width
  let handles = { start: 0.05, end: 0.95, fadeIn: 0.15, fadeOut: 0.85 };
  let dragging: string | null = null;

  const top = 10, bottom = canvas.height - 30;

  img.onload = () => {
    redraw();
  };
  img.src = imgSrc;

  function redraw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // dimmed regions outside selection
    ctx.fillStyle = 'rgba(0,0,0,0.4)';
    ctx.fillRect(0, top, handles.start * canvas.width, bottom - top);
    ctx.fillRect(handles.end * canvas.width, top, canvas.width - handles.end * canvas.width, bottom - top);

    drawHandleLine(handles.start, '#2f82df', 'inicio');
    drawHandleLine(handles.end, '#2f82df', 'final');
    drawHandleLine(handles.fadeIn, '#6aa6e8', 'fade in');
    drawHandleLine(handles.fadeOut, '#6aa6e8', 'fade out');

    // timeline labels
    ctx.fillStyle = '#555';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('0:00', 4, canvas.height - 5);
    ctx.textAlign = 'right';
    if (duration > 0) ctx.fillText(formatTime(duration), canvas.width - 4, canvas.height - 5);
  }

  function drawHandleLine(fraction: number, color: string, label: string) {
    const x = fraction * canvas.width;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    // handle dot
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, top + 4, 5, 0, Math.PI * 2);
    ctx.fill();
    // label
    ctx.fillStyle = color;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label, x, top - 4);
  }

  function getHandleAt(x: number): string | null {
    const tolerance = 8;
    for (const key of ['start', 'end', 'fadeIn', 'fadeOut']) {
      const hx = handles[key as keyof typeof handles] * canvas.width;
      if (Math.abs(x - hx) < tolerance) return key;
    }
    return null;
  }

  canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    dragging = getHandleAt(x);
    if (dragging) canvas.style.cursor = 'grabbing';
  });

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    if (dragging) {
      const frac = Math.max(0, Math.min(1, x / canvas.width));
      (handles as any)[dragging] = frac;
      // update editor inputs
      if (duration > 0) {
        const sec = (frac * duration).toFixed(1);
        if (dragging === 'start') (document.getElementById('edit-start') as HTMLInputElement).value = sec;
        if (dragging === 'end') (document.getElementById('edit-end') as HTMLInputElement).value = sec;
        if (dragging === 'fadeIn') (document.getElementById('edit-fade-in') as HTMLInputElement).value = ((frac - handles.start) * duration).toFixed(1);
        if (dragging === 'fadeOut') (document.getElementById('edit-fade-out') as HTMLInputElement).value = ((handles.end - frac) * duration).toFixed(1);
      }
      redraw();
    } else {
      const handle = getHandleAt(x);
      canvas.style.cursor = handle ? 'grab' : 'default';
    }
  });

  canvas.addEventListener('mouseup', () => { dragging = null; canvas.style.cursor = 'default'; });
  canvas.addEventListener('mouseleave', () => { dragging = null; });
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

document.getElementById('btn-export-editor')!.addEventListener('click', async () => {
  if (!state.editorFilePath) { log('Carga una canción primero'); return; }
  if (!state.editorOutputDir) { log('Selecciona una carpeta de salida'); return; }

  setStatus('Exportando canción editada...');
  setProgress(0.2);

  const metadata: Record<string, string> = {};
  ['title', 'artist', 'album', 'date', 'genre', 'composer', 'track'].forEach(f => {
    const el = document.getElementById(`meta-${f}`) as HTMLInputElement;
    if (el && el.value.trim()) metadata[f] = el.value.trim();
  });

  const parseTime = (val: string): number | null => {
    val = val.trim();
    if (!val) return null;
    const parts = val.split(':');
    if (parts.length === 1) return parseFloat(parts[0]);
    if (parts.length === 2) return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
    if (parts.length === 3) return parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseFloat(parts[2]);
    return null;
  };

  // Build output filename from metadata: "Artist - Title.mp3"
  // Falls back to original filename if metadata is empty
  const titleMeta = (document.getElementById('meta-title') as HTMLInputElement)?.value?.trim() || '';
  const artistMeta = (document.getElementById('meta-artist') as HTMLInputElement)?.value?.trim() || '';
  let outputName: string;
  if (artistMeta && titleMeta) {
    outputName = `${artistMeta} - ${titleMeta}`;
  } else if (titleMeta) {
    outputName = titleMeta;
  } else {
    outputName = state.editorFilePath.replace(/\.[^.]+$/, '').split('/').pop() || 'output';
  }
  const outputPath = `${state.editorOutputDir}/${outputName}.mp3`;

  const result = await api('export-editor', {
    sourcePath: state.editorFilePath,
    outputPath,
    start: parseTime((document.getElementById('edit-start') as HTMLInputElement).value),
    end: parseTime((document.getElementById('edit-end') as HTMLInputElement).value),
    fadeIn: parseFloat((document.getElementById('edit-fade-in') as HTMLInputElement).value) || null,
    fadeOut: parseFloat((document.getElementById('edit-fade-out') as HTMLInputElement).value) || null,
    volume: parseFloat((document.getElementById('edit-volume') as HTMLInputElement).value) || 1.0,
    quality: (document.getElementById('edit-quality') as HTMLSelectElement).value,
    overwrite: (document.getElementById('chk-editor-overwrite') as HTMLInputElement).checked,
    metadata,
  });

  if (result.status === 'ok') {
    setProgress(1);
    setStatus('Canción exportada correctamente');
    log(`Exportada: ${outputPath} (${formatBytes(result.outputSize)})`);
  } else {
    setStatus('Error en la exportación');
    log(`Error: ${result.error}`);
  }
  setTimeout(() => setProgress(0), 2000);
});

// ── Init ────────────────────────────────────────────────

log('Music Tool iniciado');
setStatus('Listo');

// ── PWA: register service worker ─────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}