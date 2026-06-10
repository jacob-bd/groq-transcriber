# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-06-10

### Added
- Automatic audio chunking for files larger than 24 MB (up to 100 MB limit).
- In-memory audio segmenting using `pydub` and `ffmpeg`.
- Conditional package dependency `audioop-lts` for Python 3.13+ compatibility.
- App version display badge in the header next to the title.

### Fixed
- Request Entity Too Large (413) error from Groq API when uploading audio files larger than 25 MB.
- Whisper segment merging issue by transcribing chunks without the `prompt` parameter to preserve natural Voice Activity Detection (VAD) and formatting of pauses.

## [1.0.0] - 2026-06-08

### Added
- Initial release of the Groq Whisper transcriber web app.
- Support for `whisper-large-v3-turbo` and `whisper-large-v3` models.
- Paragraph, sentence, plain text, and raw segment timestamp formatting.
- Interactive Web UI with upload progress, step tracking, and copy-to-clipboard functionality.
