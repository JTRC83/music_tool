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

document.getElementById('btn-add-files')!.addEventListener('click', () => {
  // Browsers don't expose file paths from <input type="file">. For a local
  // app that passes paths to ffmpeg, we ask the user to paste full paths
  // (one per line). The file picker still works for the filename, but we
  // need the absolute path.
  const input = prompt('Rutas absolutas de las canciones (una por línea):\n(ej: /Users/joantoniramoncrespi/Music/song.mp3)');
  if (!input || !input.trim()) return;
  const paths = input.trim().split('\n').map(p => p.trim()).filter(Boolean);
  paths.forEach(p => {
    const name = p.split('/').pop() || p;
    state.files.push(p);
    addSongRow(p, name);
  });
  log(`Añadidas ${paths.length} canciones`);
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
  const dir = prompt('Ruta absoluta de la carpeta de salida:\n(ej: /Users/joantoniramoncrespi/Music)');
  if (dir && dir.trim()) {
    state.outputDir = dir.trim();
    document.getElementById('output-label')!.textContent = `Carpeta de salida: ${state.outputDir}`;
    log(`Carpeta de salida: ${state.outputDir}`);
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
  // showDirectoryPicker only gives the folder name, not the full path.
  // For a local app that passes the path to yt-dlp/ffmpeg, we need the
  // absolute path. Use a prompt where the user types or pastes it.
  const dir = prompt('Ruta absoluta de la carpeta de salida:\n(ej: /Users/joantoniramoncrespi/Music)');
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
  const filePath = prompt('Ruta absoluta de la canción:\n(ej: /Users/joantoniramoncrespi/Music/song.mp3)');
  if (!filePath || !filePath.trim()) return;
  const path = filePath.trim();
  const name = path.split('/').pop() || path;
  state.editorFilePath = path;
  document.getElementById('editor-file')!.textContent = name;
  log(`Cargando: ${name}`);

  const result = await api('probe', { filePath: path });
  if (result.error) {
    log(`Error: ${result.error}`);
    return;
  }

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
  const dir = prompt('Ruta absoluta de la carpeta de salida:\n(ej: /Users/joantoniramoncrespi/Music)');
  if (dir && dir.trim()) {
    state.editorOutputDir = dir.trim();
    document.getElementById('editor-output-dir')!.textContent = state.editorOutputDir;
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
    container.innerHTML = `<img src="${url}" alt="Forma de onda" />`;
    setStatus('Forma de onda generada');
    log('Forma de onda generada');
  } else {
    setStatus('Error generando forma de onda');
    log('Error generando forma de onda');
  }
});

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

  const baseName = state.editorFilePath.replace(/\.[^.]+$/, '').split('/').pop() || 'output';
  const outputPath = `${state.editorOutputDir}/${baseName}_editado.mp3`;

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