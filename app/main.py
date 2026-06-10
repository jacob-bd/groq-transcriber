from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import load_api_key, mask_api_key, save_api_key
from app.detail_levels import DEFAULT_DETAIL_LEVEL, DETAIL_LEVELS, is_valid_detail_level
from app.models import DEFAULT_MODEL_ID, TRANSCRIPTION_MODELS, is_valid_model_id
from app.transcription import transcribe_file

app = FastAPI(title="Groq Transcriber", version="1.0.1")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

MAX_FILE_SIZE = 100 * 1024 * 1024


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


class SettingsResponse(BaseModel):
    configured: bool
    masked_key: str | None = None


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/models")
async def list_models() -> dict:
    return {"models": TRANSCRIPTION_MODELS, "default": DEFAULT_MODEL_ID}


@app.get("/api/detail-levels")
async def list_detail_levels() -> dict:
    return {"detail_levels": DETAIL_LEVELS, "default": DEFAULT_DETAIL_LEVEL}


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    api_key = load_api_key()
    if not api_key:
        return SettingsResponse(configured=False)
    return SettingsResponse(configured=True, masked_key=mask_api_key(api_key))


@app.post("/api/settings", response_model=SettingsResponse)
async def update_settings(body: ApiKeyRequest) -> SettingsResponse:
    api_key = body.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    save_api_key(api_key)
    return SettingsResponse(configured=True, masked_key=mask_api_key(api_key))


@app.post("/api/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    model: str = Form(default=DEFAULT_MODEL_ID),
    detail_level: str = Form(default=DEFAULT_DETAIL_LEVEL),
) -> dict:
    api_key = load_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="Add your Groq API key in Settings first.")

    if not is_valid_model_id(model):
        raise HTTPException(status_code=400, detail=f"Unsupported model: {model}")

    if not is_valid_detail_level(detail_level):
        raise HTTPException(status_code=400, detail=f"Unsupported detail level: {detail_level}")

    if not audio.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    file_bytes = await audio.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds the 100 MB limit.")

    try:
        result = transcribe_file(
            api_key,
            file_bytes,
            audio.filename,
            model=model,
            detail_level=detail_level,
        )
    except Exception as exc:
        message = str(exc).strip() or "Transcription failed."
        raise HTTPException(status_code=502, detail=message) from exc

    return result
