import re
from typing import TypedDict

DetailBlock = dict[str, float | str]


class DetailLevel(TypedDict):
    id: str
    name: str
    description: str
    default: bool


DETAIL_LEVELS: list[DetailLevel] = [
    {
        "id": "sentences",
        "name": "Sentences",
        "description": "One timestamp per sentence. Best for reading.",
        "default": True,
    },
    {
        "id": "paragraphs",
        "name": "Paragraphs",
        "description": "Groups speech by pauses (1.5s or longer between chunks).",
        "default": False,
    },
    {
        "id": "plain",
        "name": "Plain text (no timestamp)",
        "description": "Full transcript without timestamps.",
        "default": False,
    },
    {
        "id": "detailed",
        "name": "Detailed",
        "description": "Raw Whisper segments. May split mid-sentence.",
        "default": False,
    },
]

DEFAULT_DETAIL_LEVEL = next(level["id"] for level in DETAIL_LEVELS if level["default"])
PARAGRAPH_PAUSE_GAP_SECONDS = 1.5

SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
SENTENCE_END = re.compile(r'[.!?…][\)"\']*\s*$')


def is_valid_detail_level(detail_level: str) -> bool:
    return any(level["id"] == detail_level for level in DETAIL_LEVELS)


def normalize_whisper_segments(segments: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        normalized.append(
            {
                "start": float(segment["start"]),
                "end": float(segment["end"]),
                "text": text,
            }
        )
    return normalized


def blocks_from_detailed(segments: list[dict]) -> list[DetailBlock]:
    return [
        {"start": segment["start"], "end": segment["end"], "text": segment["text"]}
        for segment in normalize_whisper_segments(segments)
    ]


def blocks_from_paragraphs(segments: list[dict], *, pause_gap: float = PARAGRAPH_PAUSE_GAP_SECONDS) -> list[DetailBlock]:
    whisper_segments = normalize_whisper_segments(segments)
    if not whisper_segments:
        return []

    blocks: list[DetailBlock] = []
    current_start = whisper_segments[0]["start"]
    current_end = whisper_segments[0]["end"]
    current_parts = [whisper_segments[0]["text"]]

    for index in range(1, len(whisper_segments)):
        previous = whisper_segments[index - 1]
        segment = whisper_segments[index]
        gap = segment["start"] - previous["end"]
        if gap >= pause_gap:
            blocks.append(
                {
                    "start": current_start,
                    "end": current_end,
                    "text": " ".join(current_parts),
                }
            )
            current_parts = [segment["text"]]
            current_start = segment["start"]
            current_end = segment["end"]
        else:
            current_parts.append(segment["text"])
            current_end = segment["end"]

    if current_parts:
        blocks.append(
            {
                "start": current_start,
                "end": current_end,
                "text": " ".join(current_parts),
            }
        )

    return blocks


def _build_text_timeline(segments: list[dict]) -> tuple[str, list[tuple[int, int, float, float]]]:
    timeline: list[tuple[int, int, float, float]] = []
    parts: list[str] = []
    offset = 0

    for segment in normalize_whisper_segments(segments):
        if parts:
            offset += 1
        char_start = offset
        offset += len(segment["text"])
        parts.append(segment["text"])
        timeline.append((char_start, offset, segment["start"], segment["end"]))

    return " ".join(parts), timeline


def _time_range_for_chars(
    timeline: list[tuple[int, int, float, float]],
    char_start: int,
    char_end: int,
) -> tuple[float, float]:
    start_time: float | None = None
    end_time: float | None = None

    for range_start, range_end, segment_start, segment_end in timeline:
        if range_end <= char_start:
            continue
        if range_start >= char_end:
            break
        if start_time is None:
            start_time = segment_start
        end_time = segment_end

    if start_time is None or end_time is None:
        return 0.0, 0.0
    return start_time, end_time


def blocks_from_sentences(segments: list[dict]) -> list[DetailBlock]:
    whisper_segments = normalize_whisper_segments(segments)
    if not whisper_segments:
        return []

    full_text, timeline = _build_text_timeline(whisper_segments)
    if not full_text.strip():
        return []

    sentence_parts = [part.strip() for part in SENTENCE_SPLIT.split(full_text.strip()) if part.strip()]
    if not sentence_parts:
        return []

    blocks: list[DetailBlock] = []
    search_from = 0

    for sentence in sentence_parts:
        index = full_text.find(sentence, search_from)
        if index == -1:
            index = search_from
        char_start = index
        char_end = index + len(sentence)
        search_from = char_end
        start_time, end_time = _time_range_for_chars(timeline, char_start, char_end)
        blocks.append({"start": start_time, "end": end_time, "text": sentence})

    return blocks


def build_detail_blocks(payload: dict, detail_level: str) -> list[DetailBlock]:
    segments = payload.get("segments") or []
    full_text = str(payload.get("text", "")).strip()

    if detail_level == "plain":
        if not full_text:
            return []
        end_time = float(segments[-1]["end"]) if segments else 0.0
        return [{"start": 0.0, "end": end_time, "text": full_text}]

    if detail_level == "detailed":
        return blocks_from_detailed(segments)

    if detail_level == "paragraphs":
        return blocks_from_paragraphs(segments)

    return blocks_from_sentences(segments)
