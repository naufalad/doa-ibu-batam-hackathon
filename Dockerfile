# syntax=docker/dockerfile:1
#
# Pilahin backend (FastAPI + Mask2Former/ViT waste-classification pipeline).
#
# Build:
#   docker build -t pilahin-backend .
# Run:
#   docker run --rm -p 8000:8000 --env-file src/backend/.env.example pilahin-backend
#
# NOTE: this image bakes in torch/torchvision/transformers (CPU wheels) plus
# the two Hugging Face model checkpoints the pipeline needs, so the resulting
# image is large (~3GB) and the build needs outbound internet access to pull
# packages and model weights. That trade-off buys a container with no
# runtime dependency on PyPI/huggingface.co and no slow first-request model
# download after each cold start.

FROM python:3.13-slim-bookworm

# libgomp1: required at import time by torch's CPU threading (OpenMP).
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# Install deps first so this (slow) layer is cached independently of source
# changes. CPU-only torch/torchvision come from PyTorch's own index — the
# default PyPI wheels pull in CUDA libraries nothing here uses, ballooning
# the image for no benefit since APP_ML_DEVICE defaults to "cpu".
COPY src/backend/requirements.txt ./requirements.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install -r requirements.txt

# Pre-download & cache the two HF model checkpoints the pipeline loads
# lazily on first /waste/submit call (see
# src/backend/pipeline/segment_classify.py -> load_models). Baking them in
# here means the running container never needs to reach huggingface.co.
RUN python -c "\
from transformers import AutoImageProcessor, Mask2FormerForUniversalSegmentation, AutoModelForImageClassification; \
AutoImageProcessor.from_pretrained('facebook/mask2former-swin-tiny-coco-instance'); \
Mask2FormerForUniversalSegmentation.from_pretrained('facebook/mask2former-swin-tiny-coco-instance'); \
AutoImageProcessor.from_pretrained('watersplash/waste-classification'); \
AutoModelForImageClassification.from_pretrained('watersplash/waste-classification')"

COPY src/backend ./src/backend

# Non-root runtime user. Output dir is where /waste/submit writes the
# annotated overlay + results-grid per submission (settings.waste_output_dir)
# — it's created here so it's writable, but it's on the container's
# writable layer, i.e. ephemeral; mount a volume at
# /app/src/backend/pipeline/images/output if you need those to persist.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/src/backend/pipeline/images/output \
    && chown -R appuser:appuser /app
USER appuser

# src/backend is self-contained (main.py + requirements.txt + app/ all
# resolve relative to this directory) — same layout Vercel expects when its
# Root Directory is set to src/backend. Run from here so `app.*` imports
# inside main.py resolve without needing the repo root on PYTHONPATH.
WORKDIR /app/src/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/v1/health', timeout=3)"]

# Honors $PORT (Railway/Render/Cloud Run style platforms) and falls back to
# 8000 otherwise. No --reload (that's dev-only, see src/backend/main.py).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
