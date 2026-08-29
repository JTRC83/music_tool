/**
 * Music Tool — Backend local
 * Ejecuta ffmpeg / yt-dlp / ffprobe via child_process.
 * Traducido de app.py, misma lógica de comandos.
 */
import express from 'express';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { existsSync, statSync, readdirSync } from 'node:fs';
import { resolve, join, dirname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import which from 'which';

const execFileAsync = promisify(execFile);
const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3001;

app.use(express.json());

// ── Helpers ──────────────────────────────────────────────

interface BinaryInfo {
  path: string;
  version: string;
}

async function findBinary(name: string): Promise<string | null> {
  // Check bin/ folder first (same logic as app.py)
  const localBin = resolve(__dirname, '..', 'bin', name);
  if (existsSync(localBin)) return localBin;
  try {
    return await which(name);
  } catch {
    return null;
  }
}

async function getBinaryVersion(path: string, name: string): Promise<string> {
  try {
    const { stdout } = await execFileAsync(path, name === 'yt-dlp' ? ['--version'] : ['-version']);
    return stdout.split('\n')[0].slice(0, 160);
  } catch {
    return 'no se pudo leer la versión';
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '-';
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

// ── Quality options (same as app.py) ─────────────────────

const CONVERSION_FORMATS = ['MP3', 'AAC/M4A', 'FLAC', 'WAV'] as const;
const MP3_QUALITIES = ['128k', '192k', '256k', '320k'];
const BITRATE_QUALITIES = ['128k', '192k', '256k', '320k'];
const FLAC_QUALITIES = ['Compresión 0', 'Compresión 4', 'Compresión 5', 'Compresión 8'];
const WAV_QUALITIES = ['Sin compresión'];
const QUALITY_OPTIONS: Record<string, string[]> = {
  'MP3': MP3_QUALITIES,
  'AAC/M4A': BITRATE_QUALITIES,
  'FLAC': FLAC_QUALITIES,
  'WAV': WAV_QUALITIES,
};

function conversionExtension(formatName: string): string {
  return { MP3: '.mp3', 'AAC/M4A': '.m4a', FLAC: '.flac', WAV: '.wav' }[formatName] ?? '.mp3';
}

function flacCompressionValue(label: string): string {
  return label.replace('Compresión', '').trim() || '5';
}

// ── Endpoints ────────────────────────────────────────────

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// ── File system browser ──────────────────────────────────
// Lets the frontend navigate real folders instead of typing paths.

const AUDIO_EXTENSIONS = ['.flac', '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.opus'];

app.get('/api/browse', (req, res) => {
  const requestedPath = (req.query.path as string) || '';
  // Default to home directory
  let dirPath: string;
  if (requestedPath && existsSync(requestedPath)) {
    dirPath = resolve(requestedPath);
  } else {
    dirPath = resolve(process.env.HOME || '/Users');
  }

  try {
    const entries = readdirSync(dirPath, { withFileTypes: true });
    const folders = entries
      .filter(e => e.isDirectory() && !e.name.startsWith('.'))
      .map(e => e.name)
      .sort();
    const audioFiles = entries
      .filter(e => {
        if (!e.isFile()) return false;
        const ext = '.' + e.name.split('.').pop()?.toLowerCase();
        return AUDIO_EXTENSIONS.includes(ext);
      })
      .map(e => e.name)
      .sort();

    // parent directory for navigation
    const parent = dirPath !== '/' ? dirname(dirPath) : null;

    res.json({
      current: dirPath,
      parent,
      folders,
      audioFiles,
      sep,
    });
  } catch {
    res.status(403).json({ error: 'No se puede leer el directorio', current: dirPath });
  }
});

app.post('/api/browse-select', (req, res) => {
  // Returns the full path of a selected folder + lists its audio files
  const { folderPath } = req.body;
  if (!folderPath || !existsSync(folderPath)) {
    res.status(400).json({ error: 'Ruta no válida' });
    return;
  }
  try {
    const entries = readdirSync(folderPath, { withFileTypes: true });
    const audioFiles = entries
      .filter(e => {
        if (!e.isFile()) return false;
        const ext = '.' + e.name.split('.').pop()?.toLowerCase();
        return AUDIO_EXTENSIONS.includes(ext);
      })
      .map(e => join(folderPath, e.name));
    res.json({ folderPath, audioFiles });
  } catch {
    res.status(403).json({ error: 'No se puede leer la carpeta' });
  }
});

app.get('/api/formats', (_req, res) => {
  res.json({ formats: CONVERSION_FORMATS, qualityOptions: QUALITY_OPTIONS });
});

app.get('/api/diagnostics', async (_req, res) => {
  const items: Array<{ status: string; label: string; detail: string }> = [];

  for (const name of ['ffmpeg', 'ffprobe', 'yt-dlp', 'deno']) {
    const path = await findBinary(name);
    if (!path) {
      items.push({ status: 'FALTA', label: name, detail: `añade ${name} a bin/ o al PATH` });
      continue;
    }
    const version = await getBinaryVersion(path, name);
    items.push({ status: 'OK', label: name, detail: path });
    items.push({ status: 'OK', label: `${name} versión`, detail: version });
  }

  res.json({ items });
});

app.post('/api/probe', async (req, res) => {
  const { filePath } = req.body;
  const ffprobe = await findBinary('ffprobe');
  if (!ffprobe) {
    res.status(500).json({ error: 'No se ha encontrado ffprobe.' });
    return;
  }
  try {
    const { stdout } = await execFileAsync(ffprobe, [
      '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', filePath,
    ]);
    const data = JSON.parse(stdout);
    const format = data.format || {};
    const audioStream = (data.streams || []).find((s: any) => s.codec_type === 'audio');
    const duration = parseFloat(format.duration || '0');
    const bitrate = parseInt(format.bit_rate || '0');
    const size = existsSync(filePath) ? statSync(filePath).size : 0;
    const tags = format.tags || {};

    res.json({
      duration,
      durationFormatted: formatDuration(duration),
      size,
      sizeFormatted: formatSize(size),
      bitrate,
      bitrateFormatted: bitrate > 0 ? `${Math.floor(bitrate / 1000)} kbps` : '-',
      metadata: {
        title: tags.title || '',
        artist: tags.artist || '',
        album: tags.album || '',
        date: tags.date || '',
        genre: tags.genre || '',
        composer: tags.composer || '',
        track: tags.track || '',
      },
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/convert', async (req, res) => {
  const { files, outputDir, format, quality, overwrite } = req.body;
  const ffmpeg = await findBinary('ffmpeg');
  if (!ffmpeg) {
    res.status(500).json({ error: 'No se ha encontrado ffmpeg.' });
    return;
  }

  const results: Array<{ file: string; status: string; outputSize?: number }> = [];

  for (const file of files as string[]) {
    const fileName = file.split('/').pop() || file;  // just the filename, no path
    const baseName = fileName.replace(/\.[^.]+$/, '');
    const ext = conversionExtension(format);
    let outputPath = join(outputDir, `${baseName}${ext}`);

    // unique name if exists and not overwrite
    if (!overwrite && existsSync(outputPath)) {
      let counter = 1;
      while (existsSync(join(outputDir, `${baseName}_${counter}${ext}`))) counter++;
      outputPath = join(outputDir, `${baseName}_${counter}${ext}`);
    }

    const command: string[] = [
      '-hide_banner', overwrite ? '-y' : '-n', '-i', file, '-vn', '-map_metadata', '0',
    ];

    if (format === 'MP3') {
      command.push('-codec:a', 'libmp3lame', '-b:a', quality, '-id3v2_version', '3');
    } else if (format === 'AAC/M4A') {
      command.push('-codec:a', 'aac', '-b:a', quality);
    } else if (format === 'FLAC') {
      command.push('-codec:a', 'flac', '-compression_level', flacCompressionValue(quality));
    } else if (format === 'WAV') {
      command.push('-codec:a', 'pcm_s16le');
    }

    command.push(outputPath);

    try {
      await execFileAsync(ffmpeg, command, { maxBuffer: 10 * 1024 * 1024 });
      const outputSize = existsSync(outputPath) ? statSync(outputPath).size : 0;
      results.push({ file, status: 'OK', outputSize });
    } catch (err: any) {
      results.push({ file, status: `Error: ${err.message.slice(0, 200)}` });
    }
  }

  res.json({ results });
});

app.post('/api/extract-url', async (req, res) => {
  const { url, outputDir } = req.body;
  const ytDlp = await findBinary('yt-dlp');
  const ffmpeg = await findBinary('ffmpeg');
  if (!ytDlp || !ffmpeg) {
    res.status(500).json({ error: 'Falta yt-dlp o ffmpeg.' });
    return;
  }

  const deno = await findBinary('deno');
  const outputTemplate = join(outputDir, '%(title)s [%(id)s].%(ext)s');

  const command: string[] = [
    '--js-runtimes', deno ? `deno:${deno}` : 'deno',
    '-f', 'bestaudio/best',
    '-x', '--audio-format', 'mp3', '--audio-quality', '0',
    '--no-playlist', '--no-overwrites', '--restrict-filenames',
    '--embed-metadata', '--add-metadata',
    '--ffmpeg-location', dirname(ffmpeg),
    '-o', outputTemplate,
    url,
  ];

  try {
    const { stdout, stderr } = await execFileAsync(ytDlp, command, { maxBuffer: 50 * 1024 * 1024 });
    res.json({ status: 'ok', stdout, stderr });
  } catch (err: any) {
    // Retry without certificate check on SSL errors
    if (String(err.stderr || err.stdout || '').includes('CERTIFICATE_VERIFY_FAILED')) {
      const retryCmd = [...command];
      retryCmd.splice(2, 0, '--no-check-certificates');
      try {
        const { stdout, stderr } = await execFileAsync(ytDlp, retryCmd, { maxBuffer: 50 * 1024 * 1024 });
        res.json({ status: 'ok', stdout, stderr });
        return;
      } catch (err2: any) {
        res.status(500).json({ error: err2.message, stderr: err2.stderr });
        return;
      }
    }
    res.status(500).json({ error: err.message, stderr: err.stderr, stdout: err.stdout });
  }
});

app.post('/api/export-editor', async (req, res) => {
  const { sourcePath, outputPath, start, end, fadeIn, fadeOut, volume, quality, overwrite, metadata } = req.body;
  const ffmpeg = await findBinary('ffmpeg');
  if (!ffmpeg) {
    res.status(500).json({ error: 'No se ha encontrado ffmpeg.' });
    return;
  }

  const command: string[] = [
    '-hide_banner', overwrite ? '-y' : '-n', '-i', sourcePath, '-vn', '-map_metadata', '0',
  ];

  // Audio filters (same logic as app.py _build_editor_audio_filters)
  const filters: string[] = [];
  if (start != null || end != null) {
    const parts: string[] = [];
    if (start != null) parts.push(`start=${start}`);
    if (end != null) parts.push(`end=${end}`);
    filters.push(`atrim=${parts.join(':')}`);
    filters.push('asetpts=PTS-STARTPTS');
  }
  if (fadeIn && fadeIn > 0) {
    filters.push(`afade=t=in:st=0:d=${fadeIn}`);
  }
  if (fadeOut && fadeOut > 0 && end != null) {
    const fadeStart = Math.max(0, end - (start || 0) - fadeOut);
    filters.push(`afade=t=out:st=${fadeStart}:d=${fadeOut}`);
  }
  if (volume != null && volume !== 1.0) {
    filters.push(`volume=${volume}`);
  }
  if (filters.length) {
    command.push('-af', filters.join(','));
  }

  command.push('-codec:a', 'libmp3lame', '-b:a', quality, '-id3v2_version', '3');

  // Metadata overrides
  if (metadata) {
    for (const [key, value] of Object.entries(metadata)) {
      if (value && String(value).trim()) {
        command.push('-metadata', `${key}=${value}`);
      }
    }
  }

  command.push(outputPath);

  try {
    await execFileAsync(ffmpeg, command, { maxBuffer: 10 * 1024 * 1024 });
    const outputSize = existsSync(outputPath) ? statSync(outputPath).size : 0;
    res.json({ status: 'ok', outputSize });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/generate-waveform', async (req, res) => {
  const { filePath } = req.body;
  const ffmpeg = await findBinary('ffmpeg');
  if (!ffmpeg) {
    res.status(500).json({ error: 'No se ha encontrado ffmpeg.' });
    return;
  }
  // Generate a PNG waveform (same as app.py)
  try {
    const { stdout } = await execFileAsync(ffmpeg, [
      '-hide_banner', '-i', filePath,
      '-filter_complex', 'showwavespic=s=1280x240:colors=#2f82df|#80c0ff',
      '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1',
    ], { maxBuffer: 20 * 1024 * 1024, encoding: 'buffer' });
    res.set('Content-Type', 'image/png');
    res.send(stdout);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Music Tool server: http://localhost:${PORT}`);
});