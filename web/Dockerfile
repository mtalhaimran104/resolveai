FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
# BuildKit cache mount: a cancelled or failed build resumes from the pip cache
# instead of re-downloading everything.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=600 --retries=10 -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
