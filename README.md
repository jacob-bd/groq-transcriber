# Groq Transcriber

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=flat-square&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/jacobbd)

A lightweight web app for transcribing audio with [Groq](https://groq.com) Whisper models. Upload a file, pick a model and timestamp detail level, and download the result as plain text, JSON, or Markdown.

## Features

- **Whisper models** — `whisper-large-v3-turbo` (fast, $0.04/hr) and `whisper-large-v3` (highest accuracy, $0.111/hr)
- **Timestamps detail** — sentences (default), paragraphs, plain text, or raw Whisper segments
- **Export formats** — TXT, JSON (includes raw segments + formatted blocks), Markdown
- **Cost estimate** — per-run billing estimate based on audio duration
- **Progress UI** — step timeline, upload progress, elapsed time
- **Docker ready** — single-container deploy with persisted API key storage

## Quick start

### Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

CONFIG_DIR=./data uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080), add your Groq API key in Settings, then transcribe.

### Docker

```bash
docker compose up --build
```

The app listens on port **8080**. Your API key is stored in the `transcriber-data` volume.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIG_DIR` | `/data` | Directory for `config.json` (stores Groq API key) |

## Supported audio

MP3, MP4, MPEG, MPGA, M4A, WAV, WebM, OGG, FLAC — up to **100 MB** per file.

## License

MIT — see [LICENSE](LICENSE).
