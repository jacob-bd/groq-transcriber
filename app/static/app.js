const settingsForm = document.getElementById("settings-form");
const transcribeForm = document.getElementById("transcribe-form");
const apiKeyInput = document.getElementById("api-key");
const audioInput = document.getElementById("audio-file");
const modelSelect = document.getElementById("model-select");
const modelDescription = document.getElementById("model-description");
const detailSelect = document.getElementById("detail-select");
const detailDescription = document.getElementById("detail-description");
const submitBtn = document.getElementById("submit-btn");
const submitLabel = document.getElementById("submit-label");
const statusEl = document.getElementById("status");
const resultCard = document.getElementById("result-card");
const resultText = document.getElementById("result-text");
const copyBtn = document.getElementById("copy-btn");
const downloadTxtBtn = document.getElementById("download-txt-btn");
const downloadJsonBtn = document.getElementById("download-json-btn");
const downloadMdBtn = document.getElementById("download-md-btn");
const keyStatus = document.getElementById("key-status");
const maskedKey = document.getElementById("masked-key");
const dropZone = document.getElementById("drop-zone");
const dropZoneEmpty = document.getElementById("drop-zone-empty");
const dropZoneSelected = document.getElementById("drop-zone-selected");
const selectedFilename = document.getElementById("selected-filename");
const selectedMeta = document.getElementById("selected-meta");
const clearFileBtn = document.getElementById("clear-file-btn");
const progressPanel = document.getElementById("progress-panel");
const progressFilename = document.getElementById("progress-filename");
const progressMeta = document.getElementById("progress-meta");
const progressSteps = document.getElementById("progress-steps");
const progressBarFill = document.getElementById("progress-bar-fill");
const progressElapsed = document.getElementById("progress-elapsed");
const successStrip = document.getElementById("success-strip");
const successMessage = document.getElementById("success-message");
const themeToggle = document.getElementById("theme-toggle");
const appVersion = document.getElementById("app-version");


const STEPS = ["prepare", "upload", "transcribe", "format"];
const THEME_KEY = "transcriber-theme";
const MODEL_KEY = "transcriber-model";
const DETAIL_KEY = "transcriber-detail";

let lastBaseName = "transcription";
let lastResult = null;
let availableModels = [];
let availableDetailLevels = [];
let elapsedTimer = null;
let progressStart = 0;
let stepStarts = {};

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatElapsed(ms) {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${String(sec).padStart(2, "0")}`;
}

function formatStepDuration(ms) {
  return `${(ms / 1000).toFixed(1)}s`;
}

function selectedModelId() {
  return modelSelect.value;
}

function selectedModelLabel() {
  const model = availableModels.find((item) => item.id === selectedModelId());
  return model?.name || selectedModelId();
}

function updateModelDescription() {
  const model = availableModels.find((item) => item.id === selectedModelId());
  if (!model) {
    modelDescription.textContent = "";
    return;
  }
  modelDescription.textContent = `${model.description} · ${model.languages} · ${model.cost_per_hour}/hr · WER ${model.word_error_rate}`;
}

function selectedDetailLevel() {
  return detailSelect.value;
}

function selectedDetailLabel() {
  const level = availableDetailLevels.find((item) => item.id === selectedDetailLevel());
  return level?.name || selectedDetailLevel();
}

function updateDetailDescription() {
  const level = availableDetailLevels.find((item) => item.id === selectedDetailLevel());
  detailDescription.textContent = level?.description || "";
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  applyTheme(saved === "dark" ? "dark" : "light");
}

function updateDropZone(file) {
  if (file) {
    dropZoneEmpty.classList.add("hidden");
    dropZoneSelected.classList.remove("hidden");
    selectedFilename.textContent = file.name;
    selectedMeta.textContent = formatBytes(file.size);
  } else {
    dropZoneEmpty.classList.remove("hidden");
    dropZoneSelected.classList.add("hidden");
    selectedFilename.textContent = "";
    selectedMeta.textContent = "";
  }
}

function clearFile() {
  audioInput.value = "";
  updateDropZone(null);
}

function getStepEl(step) {
  return progressSteps.querySelector(`[data-step="${step}"]`);
}

function setStepState(step, state) {
  const el = getStepEl(step);
  if (!el) return;
  el.dataset.state = state;
}

function completeStep(step) {
  const elapsed = Date.now() - (stepStarts[step] || progressStart);
  const timeEl = getStepEl(step)?.querySelector(".step-time");
  if (timeEl) timeEl.textContent = formatStepDuration(elapsed);
  setStepState(step, "done");
}

function activateStep(step) {
  stepStarts[step] = Date.now();
  setStepState(step, "active");
}

function resetProgress() {
  STEPS.forEach((step) => {
    setStepState(step, "pending");
    const timeEl = getStepEl(step)?.querySelector(".step-time");
    if (timeEl) timeEl.textContent = "";
  });
  progressBarFill.className = "progress-bar-fill";
  progressBarFill.style.removeProperty("--upload-pct");
  progressElapsed.textContent = "";
  successStrip.classList.add("hidden");
}

function startElapsedTimer() {
  progressStart = Date.now();
  stepStarts = {};
  progressElapsed.textContent = "Elapsed 0:00";
  elapsedTimer = setInterval(() => {
    progressElapsed.textContent = `Elapsed ${formatElapsed(Date.now() - progressStart)}`;
  }, 1000);
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
}

function showProgressPanel(file) {
  resetProgress();
  progressFilename.textContent = file.name;
  progressMeta.textContent = `${formatBytes(file.size)} · ${selectedModelId()}`;
  progressPanel.classList.remove("hidden");
  startElapsedTimer();
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function transcribeWithProgress(file, model, detailLevel, onUploadComplete) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("audio", file);
    formData.append("model", model);
    formData.append("detail_level", detailLevel);
    let uploadDone = false;

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        const pct = Math.round((event.loaded / event.total) * 100);
        progressBarFill.className = "progress-bar-fill is-upload";
        progressBarFill.style.setProperty("--upload-pct", `${pct}%`);

        if (!uploadDone && event.loaded >= event.total) {
          uploadDone = true;
          onUploadComplete();
        }
      }
    });

    xhr.upload.addEventListener("load", () => {
      if (!uploadDone) {
        uploadDone = true;
        onUploadComplete();
      }
    });

    xhr.addEventListener("load", () => {
      let data;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        reject(new Error("Invalid response from server."));
        return;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
        return;
      }

      const detail = data.detail;
      const message = Array.isArray(detail)
        ? detail.map((item) => item.msg).join(" ")
        : detail || "Transcription failed.";
      reject(new Error(message));
    });

    xhr.addEventListener("error", () => reject(new Error("Network error during transcription.")));
    xhr.addEventListener("abort", () => reject(new Error("Transcription cancelled.")));

    xhr.open("POST", "/api/transcribe");
    xhr.send(formData);
  });
}

async function runTranscription(file) {
  const model = selectedModelId();
  const detailLevel = selectedDetailLevel();
  localStorage.setItem(MODEL_KEY, model);
  localStorage.setItem(DETAIL_KEY, detailLevel);

  showProgressPanel(file);
  setStatus("");
  submitBtn.disabled = true;
  modelSelect.disabled = true;
  detailSelect.disabled = true;
  submitBtn.classList.add("is-loading");
  submitLabel.textContent = "Transcribing…";
  dropZone.classList.add("is-disabled");
  resultCard.classList.add("hidden");
  lastResult = null;

  try {
    activateStep("prepare");
    await new Promise((r) => setTimeout(r, 200));
    completeStep("prepare");

    activateStep("upload");
    progressBarFill.className = "progress-bar-fill is-upload";
    progressBarFill.style.setProperty("--upload-pct", "0%");

    let transcribeStarted = false;
    const uploadPromise = transcribeWithProgress(file, model, detailLevel, () => {
      completeStep("upload");
      if (!transcribeStarted) {
        transcribeStarted = true;
        activateStep("transcribe");
        progressBarFill.className = "progress-bar-fill is-indeterminate";
      }
    });

    const data = await uploadPromise;

    if (!transcribeStarted) {
      completeStep("upload");
      activateStep("transcribe");
    }
    completeStep("transcribe");

    activateStep("format");
    await new Promise((r) => setTimeout(r, 250));
    completeStep("format");

    progressBarFill.className = "progress-bar-fill";
    progressBarFill.style.setProperty("--upload-pct", "100%");

    lastResult = data;
    lastBaseName = file.name.replace(/\.[^.]+$/, "") || "transcription";
    resultText.value = data.text;

    const blocks = data.block_count ?? 0;
    const chars = data.text.length;
    const totalMs = Date.now() - progressStart;
    const costDisplay = data.cost_display ?? "";
    const durationLabel = data.duration_seconds != null
      ? formatElapsed(data.duration_seconds * 1000)
      : null;

    const blockLabel = data.detail_level === "plain" ? null : `${blocks} blocks`;
    const parts = [`Done in ${formatElapsed(totalMs)}`];
    if (durationLabel) parts.push(`${durationLabel} audio`);
    if (blockLabel) parts.push(blockLabel);
    parts.push(`${chars.toLocaleString()} characters`);
    parts.push(selectedModelLabel());
    parts.push(selectedDetailLabel());
    if (costDisplay) parts.push(`${costDisplay} estimated`);

    successMessage.textContent = parts.join(" · ");
    successStrip.classList.remove("hidden");

    resultCard.classList.remove("hidden");
    setStatus("");
  } catch (error) {
    const activeStep = STEPS.find((s) => getStepEl(s)?.dataset.state === "active");
    if (activeStep) {
      setStepState(activeStep, "error");
    }
    progressBarFill.className = "progress-bar-fill";
    setStatus(error.message, true);
  } finally {
    submitBtn.disabled = false;
    modelSelect.disabled = false;
    detailSelect.disabled = false;
    submitBtn.classList.remove("is-loading");
    submitLabel.textContent = "Transcribe";
    dropZone.classList.remove("is-disabled");
    stopElapsedTimer();
  }
}

async function loadModels() {
  const response = await fetch("/api/models");
  const data = await response.json();
  if (!response.ok) {
    throw new Error("Could not load models.");
  }

  availableModels = data.models;
  modelSelect.innerHTML = "";

  for (const model of availableModels) {
    const option = document.createElement("option");
    option.value = model.id;
    option.textContent = `${model.name} — ${model.cost_per_hour}/hr`;
    modelSelect.appendChild(option);
  }

  const savedModel = localStorage.getItem(MODEL_KEY);
  const defaultModel = savedModel && availableModels.some((m) => m.id === savedModel)
    ? savedModel
    : data.default;
  modelSelect.value = defaultModel;
  updateModelDescription();
}

async function loadDetailLevels() {
  const response = await fetch("/api/detail-levels");
  const data = await response.json();
  if (!response.ok) {
    throw new Error("Could not load detail levels.");
  }

  availableDetailLevels = data.detail_levels;
  detailSelect.innerHTML = "";

  for (const level of availableDetailLevels) {
    const option = document.createElement("option");
    option.value = level.id;
    option.textContent = level.name;
    detailSelect.appendChild(option);
  }

  const savedDetail = localStorage.getItem(DETAIL_KEY);
  const defaultDetail = savedDetail && availableDetailLevels.some((level) => level.id === savedDetail)
    ? savedDetail
    : data.default;
  detailSelect.value = defaultDetail;
  updateDetailDescription();
}

async function loadSettings() {
  const response = await fetch("/api/settings");
  const data = await response.json();

  if (data.version) {
    appVersion.textContent = `v${data.version}`;
    appVersion.classList.remove("hidden");
  }

  if (data.configured) {
    keyStatus.textContent = "Configured";
    keyStatus.className = "badge badge-ok";
    maskedKey.textContent = data.masked_key ? `Saved key: ${data.masked_key}` : "";
  } else {
    keyStatus.textContent = "Not configured";
    keyStatus.className = "badge badge-muted";
    maskedKey.textContent = "Add your Groq API key to get started.";
  }
}

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const apiKey = apiKeyInput.value.trim();
  if (!apiKey) {
    setStatus("Enter an API key before saving.", true);
    return;
  }

  const response = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });

  const data = await response.json();
  if (!response.ok) {
    setStatus(data.detail || "Could not save API key.", true);
    return;
  }

  apiKeyInput.value = "";
  await loadSettings();
  setStatus("API key saved.");
});

transcribeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = audioInput.files?.[0];
  if (!file) {
    setStatus("Choose an audio file first.", true);
    return;
  }

  await runTranscription(file);
});

modelSelect.addEventListener("change", () => {
  localStorage.setItem(MODEL_KEY, selectedModelId());
  updateModelDescription();
});

detailSelect.addEventListener("change", () => {
  localStorage.setItem(DETAIL_KEY, selectedDetailLevel());
  updateDetailDescription();
});

audioInput.addEventListener("change", () => {
  updateDropZone(audioInput.files?.[0] || null);
});

clearFileBtn.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  clearFile();
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  if (!dropZone.classList.contains("is-disabled")) {
    dropZone.classList.add("is-dragover");
  }
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragover");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragover");
  if (dropZone.classList.contains("is-disabled")) return;

  const file = event.dataTransfer.files?.[0];
  if (file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    audioInput.files = dt.files;
    updateDropZone(file);
  }
});

copyBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultText.value);
  setStatus("Copied to clipboard.");
});

downloadTxtBtn.addEventListener("click", () => {
  if (!lastResult?.text) {
    setStatus("No transcription to download.", true);
    return;
  }
  downloadBlob(lastResult.text, `${lastBaseName}.txt`, "text/plain;charset=utf-8");
  setStatus(`Saved ${lastBaseName}.txt`);
});

downloadJsonBtn.addEventListener("click", () => {
  if (!lastResult?.json) {
    setStatus("No transcription to download.", true);
    return;
  }
  const content = JSON.stringify(lastResult.json, null, 2);
  downloadBlob(content, `${lastBaseName}.json`, "application/json;charset=utf-8");
  setStatus(`Saved ${lastBaseName}.json`);
});

downloadMdBtn.addEventListener("click", () => {
  if (!lastResult?.markdown) {
    setStatus("No transcription to download.", true);
    return;
  }
  downloadBlob(lastResult.markdown, `${lastBaseName}.md`, "text/markdown;charset=utf-8");
  setStatus(`Saved ${lastBaseName}.md`);
});

Promise.all([loadSettings(), loadModels(), loadDetailLevels()]).catch(() => {
  setStatus("Could not load app settings.", true);
});

initTheme();

themeToggle.addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
});
