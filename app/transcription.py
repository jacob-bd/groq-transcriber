from groq import Groq
import io
import os
from pydub import AudioSegment

from app.detail_levels import DEFAULT_DETAIL_LEVEL, DETAIL_LEVELS, build_detail_blocks
from app.models import DEFAULT_MODEL_ID, calculate_transcription_cost


def format_timestamp(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, rem_ms = divmod(total_ms, 3_600_000)
    minutes, rem_ms = divmod(rem_ms, 60_000)
    secs, ms = divmod(rem_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def normalize_payload(transcription: object) -> dict:
    if hasattr(transcription, "model_dump"):
        return transcription.model_dump()
    if isinstance(transcription, dict):
        return transcription
    return {
        "text": getattr(transcription, "text", ""),
        "segments": getattr(transcription, "segments", []),
    }


def get_audio_duration(payload: dict) -> float | None:
    if payload.get("duration") is not None:
        return float(payload["duration"])

    segments = payload.get("segments") or []
    if segments:
        return float(segments[-1].get("end", 0))

    return None


def format_duration_human(seconds: float) -> str:
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_blocks_text(blocks: list[dict], *, include_timestamps: bool) -> str:
    lines: list[str] = []

    for block in blocks:
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        if include_timestamps:
            start = format_timestamp(float(block["start"]))
            end = format_timestamp(float(block["end"]))
            lines.append(f"[{start} --> {end}] {text}")
        else:
            lines.append(text)

    return "\n".join(lines)


def format_transcription_text(blocks: list[dict], *, detail_level: str) -> str:
    include_timestamps = detail_level != "plain"
    return format_blocks_text(blocks, include_timestamps=include_timestamps)


def format_transcription_markdown(
    blocks: list[dict],
    *,
    model: str,
    source_filename: str,
    cost: dict,
    detail_level: str,
    detail_level_name: str,
) -> str:
    lines = [
        "# Transcription",
        "",
        f"- **Model:** `{model}`",
        f"- **Source:** {source_filename}",
        f"- **Timestamps detail:** {detail_level_name}",
    ]

    if cost.get("duration_seconds") is not None:
        lines.append(f"- **Audio duration:** {format_duration_human(cost['duration_seconds'])}")
    lines.extend(
        [
            f"- **Billed duration:** {format_duration_human(cost['billed_seconds'])} (10s minimum)",
            f"- **Estimated cost:** {cost['cost_display']} ({cost['rate_display']})",
            "",
        ]
    )

    include_timestamps = detail_level != "plain"
    if blocks:
        heading = "Transcript" if detail_level == "plain" else "Segments"
        lines.append(f"## {heading}")
        lines.append("")
        for index, block in enumerate(blocks, start=1):
            text = str(block.get("text", "")).strip()
            if not text:
                continue
            if include_timestamps:
                start = format_timestamp(float(block["start"]))
                end = format_timestamp(float(block["end"]))
                lines.append(f"### {index}. `{start}` → `{end}`")
            else:
                lines.append(f"### {index}.")
            lines.append("")
            lines.append(text)
            lines.append("")
    else:
        lines.append("## Transcript")
        lines.append("")
        lines.append("_No transcript text returned._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_export_json(
    payload: dict,
    blocks: list[dict],
    *,
    model: str,
    source_filename: str,
    cost: dict,
    detail_level: str,
) -> dict:
    return {
        "model": model,
        "source_filename": source_filename,
        "detail_level": detail_level,
        "text": payload.get("text", ""),
        "language": payload.get("language"),
        "duration": payload.get("duration"),
        "duration_seconds": cost.get("duration_seconds"),
        "billed_seconds": cost.get("billed_seconds"),
        "estimated_cost_usd": cost.get("cost_usd"),
        "estimated_cost_display": cost.get("cost_display"),
        "rate_display": cost.get("rate_display"),
        "blocks": blocks,
        "segments_raw": payload.get("segments") or [],
        "words": payload.get("words") or [],
    }


def chunk_audio(
    file_bytes: bytes,
    filename: str,
    max_chunk_size_bytes: int = 24 * 1024 * 1024,
) -> list[dict]:
    # Determine the audio format from the extension
    _, ext = os.path.splitext(filename)
    format_name = ext.lstrip(".").lower()
    if not format_name:
        format_name = "mp3"  # Fallback to mp3 if no extension is found

    # Load audio into memory
    audio = AudioSegment.from_file(io.BytesIO(file_bytes), format=format_name)
    duration_ms = len(audio)

    # Start with 10-minute chunks (600,000 milliseconds)
    chunk_duration_ms = 600_000
    chunks = []
    start_ms = 0

    while start_ms < duration_ms:
        end_ms = min(start_ms + chunk_duration_ms, duration_ms)

        while True:
            chunk = audio[start_ms:end_ms]
            buffer = io.BytesIO()
            chunk.export(buffer, format=format_name)
            chunk_bytes = buffer.getvalue()

            # Verify that the exported chunk size is within the allowed limit.
            # If not, halve the duration (down to a minimum of 10 seconds) and try again.
            if len(chunk_bytes) <= max_chunk_size_bytes or chunk_duration_ms <= 10_000:
                chunks.append({
                    "bytes": chunk_bytes,
                    "offset_seconds": start_ms / 1000.0,
                    "duration_seconds": (end_ms - start_ms) / 1000.0,
                })
                break
            else:
                chunk_duration_ms = max(chunk_duration_ms // 2, 10_000)
                end_ms = min(start_ms + chunk_duration_ms, duration_ms)

        start_ms = end_ms

    return chunks


def transcribe_file(
    api_key: str,
    file_bytes: bytes,
    filename: str,
    model: str = DEFAULT_MODEL_ID,
    detail_level: str = DEFAULT_DETAIL_LEVEL,
) -> dict:
    client = Groq(api_key=api_key)

    # Check if the file fits within the Groq API limit (24 MB to be safe)
    if len(file_bytes) <= 24 * 1024 * 1024:
        # Single file upload
        transcription = client.audio.transcriptions.create(
            file=(filename, file_bytes),
            model=model,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            temperature=0.0,
        )
        payload = normalize_payload(transcription)
    else:
        # Split file into chunks
        chunks = chunk_audio(file_bytes, filename)

        all_texts = []
        all_segments = []
        total_duration = 0.0
        detected_language = None

        for index, chunk in enumerate(chunks):
            # Send chunk bytes to Groq
            chunk_filename = f"chunk_{index}_{filename}"

            transcription = client.audio.transcriptions.create(
                file=(chunk_filename, chunk["bytes"]),
                model=model,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                temperature=0.0,
            )

            chunk_payload = normalize_payload(transcription)

            # Save language of first chunk
            if index == 0:
                detected_language = chunk_payload.get("language")

            chunk_text = chunk_payload.get("text", "").strip()
            if chunk_text:
                all_texts.append(chunk_text)

            # Adjust segment timestamps by the offset of the chunk
            offset = chunk["offset_seconds"]
            chunk_segments = chunk_payload.get("segments") or []
            for segment in chunk_segments:
                adjusted_segment = dict(segment)
                if "start" in adjusted_segment:
                    adjusted_segment["start"] = float(adjusted_segment["start"]) + offset
                if "end" in adjusted_segment:
                    adjusted_segment["end"] = float(adjusted_segment["end"]) + offset
                # If there are word-level timestamps (words array), adjust those too
                if "words" in adjusted_segment and isinstance(adjusted_segment["words"], list):
                    adjusted_words = []
                    for word_obj in adjusted_segment["words"]:
                        adjusted_word = dict(word_obj)
                        if "start" in adjusted_word:
                            adjusted_word["start"] = float(adjusted_word["start"]) + offset
                        if "end" in adjusted_word:
                            adjusted_word["end"] = float(adjusted_word["end"]) + offset
                        adjusted_words.append(adjusted_word)
                    adjusted_segment["words"] = adjusted_words
                all_segments.append(adjusted_segment)

            total_duration += chunk["duration_seconds"]

        payload = {
            "text": " ".join(all_texts),
            "segments": all_segments,
            "duration": total_duration,
            "language": detected_language,
        }

    duration_seconds = get_audio_duration(payload)
    cost = calculate_transcription_cost(duration_seconds, model)
    blocks = build_detail_blocks(payload, detail_level)
    detail_level_name = next(
        (level["name"] for level in DETAIL_LEVELS if level["id"] == detail_level),
        detail_level,
    )
    text = format_transcription_text(blocks, detail_level=detail_level)
    markdown = format_transcription_markdown(
        blocks,
        model=model,
        source_filename=filename,
        cost=cost,
        detail_level=detail_level,
        detail_level_name=detail_level_name,
    )
    export_json = build_export_json(
        payload,
        blocks,
        model=model,
        source_filename=filename,
        cost=cost,
        detail_level=detail_level,
    )

    return {
        "text": text,
        "markdown": markdown,
        "json": export_json,
        "model": model,
        "detail_level": detail_level,
        "filename": filename,
        "block_count": len(blocks),
        "segment_count": len(payload.get("segments") or []),
        "duration_seconds": duration_seconds,
        "billed_seconds": cost["billed_seconds"],
        "cost_usd": cost["cost_usd"],
        "cost_display": cost["cost_display"],
        "rate_display": cost["rate_display"],
    }
