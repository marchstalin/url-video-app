import os
import tempfile
import shutil
import threading
import mimetypes
from flask import Flask, request, render_template, send_file, redirect, url_for, flash
try:
    from yt_dlp import YoutubeDL
    HAVE_YTDLP_LIB = True
except Exception:
    HAVE_YTDLP_LIB = False
from uuid import uuid4

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")

# in-memory map of pending downloads: token -> (filepath, tmpdir)
pending_downloads = {}

QUALITY_FORMATS = {
    'mp3': {
        'format': 'bestaudio/best',
        'extension': 'mp3',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    },
    'mp4_best': {'format': 'bestvideo+bestaudio/best', 'extension': 'mp4'},
}

for height in (360, 480, 720, 1080):
    QUALITY_FORMATS[f'mp4_{height}'] = {
        'format': f'bestvideo[height<={height}]+bestaudio/best[height<={height}]',
        'extension': 'mp4',
    }
    QUALITY_FORMATS[f'muted_{height}'] = {
        'format': f'bestvideo[height<={height}]',
        'extension': 'mp4',
    }


def cleanup_later(path, delay=60):
    def _rm():
        try:
            shutil.rmtree(path)
        except Exception:
            pass
    t = threading.Timer(delay, _rm)
    t.daemon = True
    t.start()


def find_downloaded_file(tmpdir):
    candidates = []
    for root, _, files in os.walk(tmpdir):
        for filename in files:
            if filename.endswith('.txt') or filename.endswith('.part'):
                continue
            filepath = os.path.join(root, filename)
            if os.path.isfile(filepath) and os.path.getsize(filepath) > 0:
                candidates.append((os.path.getsize(filepath), filepath))
    if not candidates:
        return None
    return max(candidates)[1]


def make_ready_response(filepath, tmpdir, cleanup_delay=300):
    token = uuid4().hex
    pending_downloads[token] = (filepath, tmpdir)
    cleanup_later(tmpdir, delay=cleanup_delay)
    return render_template('ready.html', token=token, filename=os.path.basename(filepath))


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/download', methods=['POST'])
def download():
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    url = request.form.get('url', '').strip()
    # strip playlist-related query params so yt-dlp treats this as a single video
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            # rebuild URL keeping only the video id
            new_qs = {'v': qs['v']}
            new_query = urlencode(new_qs, doseq=True)
            url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        else:
            # handle youtu.be short links: leave as-is
            url = url
    except Exception:
        pass
    if not url:
        flash('Please provide a URL')
        return redirect(url_for('index'))

    quality = request.form.get('quality', 'mp4_best')
    format_options = QUALITY_FORMATS.get(quality)
    if not format_options:
        flash('Please select a valid video quality.')
        return redirect(url_for('index'))

    tmpdir = tempfile.mkdtemp(prefix='yvdl_')

    try:
        # small helper logger to prevent yt-dlp from printing noisy JS-runtime warnings to stdout
        class _YTDLPLogger:
            def debug(self, msg):
                pass
            def info(self, msg):
                pass
            def warning(self, msg):
                app.logger.warning(msg)
            def error(self, msg):
                app.logger.error(msg)

        ydl_opts = {
            'format': format_options['format'],
            'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,
            'no_warnings': False,
            'geo_bypass': True,
            'retries': 3,
            'logger': _YTDLPLogger(),
            'merge_output_format': 'mp4',
        }
        if format_options.get('postprocessors'):
            ydl_opts['postprocessors'] = format_options['postprocessors']

        # prefer an installed JS runtime (deno or node) and pass explicit path to yt-dlp
        try:
            deno_path = shutil.which('deno')
            node_path = shutil.which('node') or shutil.which('nodejs')
            if deno_path:
                # yt-dlp expects js_runtimes as a dict: {runtime: {config}}
                ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
                app.logger.info(f'Using JS runtime: deno at {deno_path}')
            elif node_path:
                ydl_opts['js_runtimes'] = {'node': {'path': node_path}}
                app.logger.info(f'Using JS runtime: node at {node_path}')
            else:
                app.logger.warning('No JS runtime (deno/node) found in PATH; install one for full YouTube extraction support')
        except Exception:
            pass

        test_only = request.form.get('test_only') is not None

        info = None
        if HAVE_YTDLP_LIB:
            with YoutubeDL(ydl_opts) as ydl:
                # If user requested a test, don't download; only extract metadata.
                info = ydl.extract_info(url, download=not test_only)
        else:
            # Fall back to calling yt-dlp CLI if installed
            import subprocess, json
            node_path = shutil.which('node') or shutil.which('nodejs')
            cmd = [
                'yt-dlp', '-f', format_options['format'],
                '-o', os.path.join(tmpdir, '%(title)s.%(ext)s'), '--no-playlist',
            ]
            if quality == 'mp3':
                cmd += ['--extract-audio', '--audio-format', 'mp3', '--audio-quality', '192K']
            if test_only:
                cmd += ['--skip-download']
            if node_path:
                cmd += ['--js-runtimes', f'node:{node_path}']
            cmd += [url]
            app.logger.info('Running yt-dlp CLI: ' + ' '.join(cmd))
            proc = subprocess.run(cmd, capture_output=True, text=True)
            app.logger.info(proc.stdout)
            app.logger.warning(proc.stderr)
            if proc.returncode != 0:
                raise Exception(proc.stderr.strip() or 'yt-dlp CLI failed')

        if test_only:
            # cleanup and inform the user about the result
            shutil.rmtree(tmpdir, ignore_errors=True)
            flash('Test completed: metadata retrieved successfully (no file downloaded).')
            return redirect(url_for('index'))

        filepath = find_downloaded_file(tmpdir)
        if not filepath:
            flash('Download completed but no file found')
            cleanup_later(tmpdir, delay=5)
            return redirect(url_for('index'))

        return make_ready_response(filepath, tmpdir)

    except Exception as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        if '403' in str(e):
            flash('The video service rejected this URL (HTTP 403). This video requires access that yt-dlp cannot obtain without authentication.')
        else:
            flash(f'Error: {e}')
        return redirect(url_for('index'))


def get_pending_file(token, remove=False):
    entry = pending_downloads.pop(token, None) if remove else pending_downloads.get(token)
    if not entry:
        flash('File not found or expired')
        return redirect(url_for('index'))
    filepath, tmpdir = entry
    return filepath, tmpdir


@app.route('/preview/<token>', methods=['GET'])
def preview_file(token):
    entry = get_pending_file(token)
    if not isinstance(entry, tuple):
        return entry
    filepath, _ = entry
    media_type = mimetypes.guess_type(filepath)[0] or 'video/mp4'
    return send_file(filepath, mimetype=media_type, as_attachment=False, conditional=True)


@app.route('/get/<token>', methods=['GET'])
def serve_file(token):
    entry = get_pending_file(token, remove=True)
    if not isinstance(entry, tuple):
        return entry
    filepath, tmpdir = entry
    # remove the tmpdir shortly after serving (1s) so the download can start
    cleanup_later(tmpdir, delay=1)
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))


if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    app.run(host='0.0.0.0', port=5000, debug=debug)
