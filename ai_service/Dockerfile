FROM python:3.11-slim

# HF_HOME points Hugging Face model downloads at a mounted volume so the
# ~1.1 GB sentiment model is not re-downloaded every time the container is
# recreated (see the hf_cache volume in docker-compose.yml).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models

WORKDIR /app

COPY requirements.txt .

# The pip cache is kept in a BuildKit cache mount rather than discarded with
# --no-cache-dir. A failed or cancelled build then resumes from what was
# already downloaded instead of starting the multi-hundred-MB pull over again.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=600 --retries=10 -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
