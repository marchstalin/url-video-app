# URL Video Downloader

Simple Flask app that uses `yt-dlp` to download videos from a provided URL and return the file. No login is performed.

Quick start:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U -r requirements.txt
python app.py
```

Open http://localhost:5000 and paste a video page URL. The app downloads the video directly from the URL without using cookie files.

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
