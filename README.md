# ResolveAI

**ResolveAI** is an AI-powered help desk and support-ticket platform.

This repository currently contains **Phase 1: Base Project Boilerplate and
First Django Dashboard Page** — a clean, understandable foundation that the
rest of the project will be built on top of.

## Phase 1 Scope

This phase only includes:

- A Dockerized Django web application
- A MySQL database container
- A simple Django project structure with one app (`dashboard`)
- AdminLTE 4 integrated into Django templates
- One working dashboard page with static mock data
- Django Admin enabled at `/admin/`

It does **not** include authentication screens, ticket management, RBAC,
or the FastAPI AI/ML service. Those arrive in later phases.

## Technology Stack (Phase 1)

- [Django](https://www.djangoproject.com/) — web application
- [AdminLTE 4](https://adminlte.io/) — dashboard UI (Bootstrap 5 based)
- [MySQL 8](https://www.mysql.com/) — database
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/) — local environment

## Prerequisites

- Docker and Docker Compose installed
- Nothing else — Python and MySQL both run inside containers

## Environment Setup

Copy the example environment file and adjust values if needed:

```bash
cp .env.example .env
```

The defaults work out of the box for local development.

## Build and Start the Project

```bash
docker compose up --build
```

This starts two containers:

- `web` — the Django application, served on port `8000`
- `db` — the MySQL 8 database

Wait until `db` reports healthy and Django's development server log
appears before opening the app.

## Run Migrations

In a second terminal, once the containers are up:

```bash
docker compose exec web python manage.py migrate
```

## Create a Superuser

```bash
docker compose exec web python manage.py createsuperuser
```

## URLs

- Dashboard: <http://localhost:8000/>
- Django Admin: <http://localhost:8000/admin/>

## Project Structure

```text
resolve-ai/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
│
├── db/
│   └── init/               # SQL run once against a fresh MySQL volume
│
├── web/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   │
│   ├── config/            # Django project settings, URLs, WSGI/ASGI
│   ├── dashboard/         # The dashboard app (views, urls, tests)
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── includes/      # navbar, sidebar, footer, messages
│   │   └── dashboard/
│   │       └── index.html
│   │
│   └── static/
│       ├── adminlte/      # AdminLTE 4 CSS/JS, copied from the template
│       └── resolve_ai/    # ResolveAI-specific CSS/JS
│
└── docs/
    └── phase-1-setup.md
```

## Common Docker Commands

| Task                          | Command                                             |
| ------------------------------ | ---------------------------------------------------- |
| Start the project               | `docker compose up --build`                          |
| Start in the background         | `docker compose up -d`                                |
| View logs                       | `docker compose logs -f web`                          |
| Run a Django management command | `docker compose exec web python manage.py <command>`  |
| Open a shell in the web container | `docker compose exec web bash`                      |
| Run the test suite              | `docker compose exec web python manage.py test`       |

## Stop and Reset the Project

Stop the containers (keeps the database volume):

```bash
docker compose down
```

Stop the containers and delete the database volume (full reset):

```bash
docker compose down -v
```

## Known Limitations

- No authentication or login screens yet (only Django's default `/admin/` login)
- No ticket, user or knowledge-base models — dashboard data is static mock data
- Sidebar links other than **Dashboard** are placeholders (`#`)
- No AI/ML service — the dashboard shows a "not configured yet" card instead

## Next Planned Phase

Phase 2 is expected to introduce the ticket-management data model and
CRUD pages (create, list, view, update tickets), building on this
boilerplate.

See [`docs/phase-1-setup.md`](docs/phase-1-setup.md) for a walkthrough of
how this phase was built and how to extend it.
