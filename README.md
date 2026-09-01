# ResolveAI

**ResolveAI** is an AI-powered help desk and support-ticket platform built for
The Islamia University of Bahawalpur.

It is a two-service application: a **Django** web application for the help desk
itself, and a **FastAPI** service that runs the AI/ML models (ticket
classification, priority prediction, sentiment analysis, summarisation and FAQ
retrieval). Both run in Docker alongside a MySQL 8 database.

## Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [How Long the First Build Takes](#how-long-the-first-build-takes)
- [Services](#services)
- [Logging In](#logging-in)
- [URLs](#urls)
- [The AI Service API](#the-ai-service-api)
- [Project Structure](#project-structure)
- [Common Commands](#common-commands)
- [Stopping and Resetting](#stopping-and-resetting)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)

## Prerequisites

- Docker and Docker Compose (Docker Desktop on Windows or macOS)
- About **8 GB of free disk space** for images, volumes and the model cache
- Nothing else — Python, MySQL and every dependency run inside containers

## Quick Start

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py migrate
```

Then open <http://localhost:8000/> and log in with `superadmin` /
`ChangeMe123!`.

The defaults in `.env.example` work out of the box for local development.

## How Long the First Build Takes

The first `ai_service` build downloads roughly **700 MB** of Python packages
(PyTorch, transformers, scikit-learn, pandas) and produces a ~1.6 GB image.
On a normal connection that is about **five minutes**.

Later builds reuse Docker's layer cache and finish in seconds — the pip step
is skipped entirely unless `requirements.txt` changed. Adding `--no-cache`
throws that away and costs the full five minutes again, so use it only when
you specifically need to discard a stale layer.

The first time `ai_service` *starts*, it also downloads the sentiment model
from Hugging Face (~2.1 GB) into the `hf_cache` volume. That happens once and
survives `docker compose down` / `up`; only `docker compose down -v` discards
it.

> **If a build runs for hours, something is wrong.** The usual cause is a
> dependency pulling the CUDA build of PyTorch (~3.2 GB of unused NVIDIA
> packages) instead of the CPU build this project pins. See
> [`docs/docker-build-performance.md`](docs/docker-build-performance.md) for
> the diagnosis and the fix.

## Services

| Service      | Image             | Host port | Purpose                          |
| ------------ | ----------------- | --------- | -------------------------------- |
| `web`        | built from `web/` | `8000`    | Django help desk application     |
| `ai_service` | built from `ai_service/` | `8001` | FastAPI AI/ML inference service |
| `db`         | `mysql:8.4`       | `3307`    | MySQL 8 database                 |

`web` waits for `db` to report healthy before starting. `web` reaches the AI
service over the compose network at `http://ai_service:8000`, configurable
with `AI_SERVICE_URL`.

Named volumes:

| Volume       | Holds                                                    |
| ------------ | -------------------------------------------------------- |
| `mysql_data` | the MySQL data directory                                  |
| `media_data` | user-uploaded files (ticket attachments)                  |
| `hf_cache`   | the downloaded Hugging Face models (~2.1 GB)              |

## Train the Models Before First Start

The trained model artifacts are gitignored, so a fresh clone has none and
`ai_service` will **exit immediately** with:

```
FileNotFoundError: Classification model not found:
    /app/app/models/ticket_classification/ticket_classification_model.pkl
```

The models load at import time, so one missing file takes down the whole
service, including the endpoints that do not need it. Train them once:

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/project -w /project \
    -e HOME=/tmp resolveai-ai_service:latest python training/train_category_model.py

docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/project -w /project \
    -e HOME=/tmp resolveai-ai_service:latest python training/train_priority_model.py

docker compose up -d ai_service
```

This writes four `.pkl` files plus `model_metrics.json` into
`ai_service/app/models/`, which is bind-mounted, so no rebuild is needed. The
`-u` flag keeps the files owned by you rather than root. Takes about a minute
and needs no GPU.

Verify:

```bash
curl -s http://localhost:8001/api/v1/classification/metrics
curl -s http://localhost:8001/api/v1/priority/metrics
```

Both should return `"status": true`. Current models score 98.07% accuracy
(classification, 19 categories) and 98.31% (priority, 4 classes).

## Logging In

Migrations create a super administrator, so there is no `createsuperuser`
step:

| Username     | Password       |
| ------------ | -------------- |
| `superadmin` | `ChangeMe123!` |

Both come from `SUPERADMIN_USERNAME` / `SUPERADMIN_PASSWORD` in `.env`. Change
them there *before* the first `migrate` to get different ones, or afterwards
with:

```bash
docker compose exec web python manage.py changepassword superadmin
```

## URLs

| Page                | URL                                               |
| ------------------- | ------------------------------------------------- |
| Dashboard           | <http://localhost:8000/>                          |
| Tickets             | <http://localhost:8000/tickets/>                  |
| Knowledge base      | <http://localhost:8000/knowledge-base/>           |
| Reports             | <http://localhost:8000/reports/>                  |
| Categories          | <http://localhost:8000/categories/>               |
| User administration | <http://localhost:8000/accounts/users/>           |
| Django Admin        | <http://localhost:8000/admin/>                    |
| AI service docs     | <http://localhost:8001/docs>                      |

## The AI Service API

The FastAPI service exposes interactive docs at <http://localhost:8001/docs>.
Django calls it server-side; these are the endpoints:

| Endpoint                          | Method | Purpose                                  |
| --------------------------------- | ------ | ---------------------------------------- |
| `/api/v1/classification/predict`  | POST   | Route a ticket to a category             |
| `/api/v1/classification/metrics`  | GET    | Classifier evaluation metrics            |
| `/api/v1/priority/predict`        | POST   | Predict ticket priority                  |
| `/api/v1/priority/metrics`        | GET    | Priority model evaluation metrics        |
| `/api/v1/sentiment/predict`       | POST   | Multilingual sentiment of ticket text    |
| `/api/v1/summarization/predict`   | POST   | Summarise a ticket thread                |
| `/faq/`                           | POST   | Retrieve the closest FAQ answer          |

Sentiment uses `cardiffnlp/twitter-xlm-roberta-base-sentiment` on **CPU**.
Everything else is scikit-learn or TF-IDF based. There is no GPU anywhere in
this project — see [Troubleshooting](#troubleshooting).

## Project Structure

```text
resolveai/
├── docker-compose.yml
├── .env.example
│
├── db/init/                    # SQL run once against a fresh MySQL volume
├── data/                       # FAQ dataset and other CSV inputs
├── training/                   # Model training scripts
├── notebooks/                  # Exploratory notebooks
│
├── web/                        # Django application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config/                 # Settings, root URLs, WSGI/ASGI
│   ├── core/                   # Shared abstract models
│   ├── accounts/               # User, Role, Permission + RBAC, auth pages
│   ├── dashboard/              # Dashboard, notifications, settings pages
│   ├── organization/           # Departments and organisational structure
│   ├── classification/         # Ticket categories
│   ├── tickets/                # Ticket model and CRUD
│   ├── knowledge/              # Knowledge base articles
│   ├── reports/                # Reporting and analytics pages
│   ├── ai/                     # Client for the FastAPI service
│   ├── templates/              # AdminLTE 4 templates
│   └── static/
│
└── ai_service/                 # FastAPI AI/ML service
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py
        ├── api/routers/        # One router per AI capability
        ├── services/           # Business logic per capability
        ├── models/             # Model loading and inference
        ├── retrieval/          # FAQ retrieval
        ├── schemas/            # Pydantic request/response models
        └── core/               # Config, database, helpers
```

## Common Commands

| Task                              | Command                                              |
| --------------------------------- | ---------------------------------------------------- |
| Start everything                  | `docker compose up -d --build`                       |
| View web logs                     | `docker compose logs -f web`                         |
| View AI service logs              | `docker compose logs -f ai_service`                  |
| Run a Django management command   | `docker compose exec web python manage.py <command>` |
| Make migrations                   | `docker compose exec web python manage.py makemigrations` |
| Apply migrations                  | `docker compose exec web python manage.py migrate`   |
| Open a shell in the web container | `docker compose exec web bash`                       |
| Run the test suite                | `docker compose exec web python manage.py test`      |
| Rebuild just the AI service       | `docker compose build ai_service`                    |

## Stopping and Resetting

Stop the containers, keeping the database and model cache:

```bash
docker compose down
```

Full reset — **deletes the database, uploaded media and the 2.1 GB model
cache**:

```bash
docker compose down -v
```

Prefer `docker compose down` for everyday use. `-v` means the next start
re-downloads the Hugging Face model and you lose all local data.

## Troubleshooting

**Every rebuild re-downloads all the packages.**
Docker's *layer* cache should make a plain `docker compose up -d --build` skip
the pip step. If you are passing `--no-cache`, stop — that is what discards
it. The BuildKit pip cache mount is not a reliable fallback: on the default
`docker` builder driver it is dropped between builds. See
[`docs/docker-build-performance.md`](docs/docker-build-performance.md).

**The build has been running for over an hour.**
Read [`docs/docker-build-performance.md`](docs/docker-build-performance.md).
Verify that CPU-only PyTorch was installed:

```bash
docker compose exec ai_service pip list | grep -i -E "nvidia|torch|triton|cuda"
```

The only line should be `torch 2.13.0+cpu`. Any `nvidia-*` or `triton` package
means the 3.2 GB CUDA build slipped in — check that the `--extra-index-url`
line and the `+cpu` pin are still in `ai_service/requirements.txt`.

**Docker has run out of disk space.**
Check what is being held with `docker system df`. Reclaim dangling images and
build cache with `docker image prune` and `docker builder prune`. Be careful
with `docker volume prune`: a stopped project's volumes count as *dangling*,
so it will happily delete `resolveai_mysql_data` along with the junk.

**`web` cannot reach the AI service.**
`AI_SERVICE_URL` defaults to `http://ai_service:8000` — the internal compose
address and port, not the `8001` published on the host. Only change it if you
run the AI service outside Docker.

**The first request to a sentiment endpoint is very slow.**
That is the one-time Hugging Face model download filling the `hf_cache`
volume. Watch it with `docker compose logs -f ai_service`.

**Migrations fail after pulling new models.**
A custom user model can only be created against a database that has never been
migrated. If you are upgrading a very old local database, reset it once with
`docker compose down -v`, then `up` and `migrate`. This deletes local data.

## Documentation

- [`docs/docker-build-performance.md`](docs/docker-build-performance.md) — why
  the AI service build was slow, and the rules that keep it fast
- [`docs/phase-1-setup.md`](docs/phase-1-setup.md) — how the boilerplate,
  Docker setup and templates fit together
- [`docs/phase-2-models-and-migrations.md`](docs/phase-2-models-and-migrations.md)
  — the identity/RBAC models, the migration workflow, and **the pattern to
  follow when adding new modules**
- `docs/ResolveAI_Database_Schema_Design.pdf` — the full target schema
- `docs/ResolveAI_Complete_Project_SRS_Proposal.pdf` — project requirements
