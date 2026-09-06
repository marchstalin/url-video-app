# URL Video Downloader

Simple Flask app that uses `yt-dlp` to download videos from a provided URL and return the file. No login is performed.

Quick start:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U -r requirements.txt
gunicorn --bind 0.0.0.0:5000 app:app # OR python app.py
```

For production, install the requirements and run the app with Gunicorn instead
of Flask's development server:

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

Set `FLASK_DEBUG=true` only for local debugging. It is disabled by default.

# Push the code
env -u GIT_ASKPASS -u VSCODE_GIT_ASKPASS_NODE -u VSCODE_GIT_ASKPASS_MAIN \
  git push -u origin main

Open http://localhost:5000 and paste a video page URL. The app downloads the video directly from the URL without using cookie files.

Choose the desired output before downloading: MP3 audio, MP4 with audio at up to 360p, 480p, 720p, or 1080p, or a muted MP4 video at those resolutions. MP4 merging and MP3 conversion require `ffmpeg` to be installed.

Downloaded and converted files are stored temporarily in a system directory such as `/tmp/yvdl_<random-id>/`. The file is used for preview and download, then the temporary directory is removed automatically. Files are not permanently saved in the project directory.

If you see errors like HTTP 403 or warnings about JS runtimes, try:

- Some videos may still be unavailable when the source requires authentication or blocks automated requests.
- Provide a proxy in the form (e.g. `http://127.0.0.1:8080`) to route requests through the required region.
- The requirements install yt-dlp's JavaScript challenge components. A JS runtime is also required:

	- Node.js (recommended):

		```bash
		# Debian/Ubuntu
		curl -fsSL https://deb.nodesource.com/setup_current.x | sudo -E bash -
		sudo apt-get install -y nodejs
		```

	- Deno (alternative):

		```bash
		curl -fsSL https://deno.land/x/install/install.sh | sh
		```

After installing a JS runtime, restart the app and retry the download.
