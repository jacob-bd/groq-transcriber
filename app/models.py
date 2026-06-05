from typing import TypedDict


class TranscriptionModel(TypedDict):
    id: str
    name: str
    languages: str
    description: str
    cost_per_hour: str
    word_error_rate: str
    default: bool


# Groq speech-to-text models as of June 2026 (console.groq.com/docs/speech-to-text)
TRANSCRIPTION_MODELS: list[TranscriptionModel] = [
    {
        "id": "whisper-large-v3-turbo",
        "name": "Whisper Large V3 Turbo",
        "languages": "Multilingual",
        "description": "Fast transcription with strong price/performance.",
        "cost_per_hour": "$0.04",
        "word_error_rate": "12%",
        "default": True,
    },
    {
        "id": "whisper-large-v3",
        "name": "Whisper Large V3",
        "languages": "Multilingual",
        "description": "Highest accuracy. Also supports translation to English.",
        "cost_per_hour": "$0.111",
        "word_error_rate": "10.3%",
        "default": False,
    },
]

DEFAULT_MODEL_ID = next(m["id"] for m in TRANSCRIPTION_MODELS if m["default"])

# Groq bills transcription per audio hour; requests under 10s are billed as 10s.
MIN_BILLED_SECONDS = 10

MODEL_COST_USD_PER_HOUR: dict[str, float] = {
    "whisper-large-v3-turbo": 0.04,
    "whisper-large-v3": 0.111,
}


def is_valid_model_id(model_id: str) -> bool:
    return any(m["id"] == model_id for m in TRANSCRIPTION_MODELS)


def format_usd(amount: float) -> str:
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def calculate_transcription_cost(duration_seconds: float | None, model_id: str) -> dict:
    rate = MODEL_COST_USD_PER_HOUR[model_id]
    billed_seconds = MIN_BILLED_SECONDS if duration_seconds is None else max(MIN_BILLED_SECONDS, duration_seconds)
    cost_usd = (billed_seconds / 3600) * rate
    return {
        "duration_seconds": duration_seconds,
        "billed_seconds": billed_seconds,
        "cost_usd": cost_usd,
        "cost_display": format_usd(cost_usd),
        "rate_display": f"{format_usd(rate)}/hr",
    }
