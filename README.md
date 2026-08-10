# ResolveAI

**ResolveAI** is an AI-powered help desk and support-ticket platform.

This repository currently contains:

- **Phase 1: Base Project Boilerplate and First Django Dashboard Page** — a
  clean, understandable foundation that the rest of the project is built on.
- **Phase 2: Identity and RBAC Models** — the custom user model, roles,
  permissions and their migrations, including a seeded superadmin account.

## Phase 1 Scope

- A Dockerized Django web application
- A MySQL database container
- A simple Django project structure with one app (`dashboard`)
- AdminLTE 4 integrated into Django templates
- One working dashboard page with static mock data
- Django Admin enabled at `/admin/`

## Phase 2 Scope

- A custom user model (`accounts.User`, table `users`)
- Role-based access control: `roles`, `permissions`, `user_roles`,
  `role_permissions`
- A data migration seeding the four roles (REQUESTER, AGENT, SUPERVISOR,
  ADMIN) and the permission catalogue
- A data migration creating the `superadmin` account
- Model tests covering RBAC and the seed migrations

It does **not** yet include signup/login screens, ticket management or the
FastAPI AI/ML service. Those arrive in later phases.

New models must follow the conventions in
[`docs/phase-2-models-and-migrations.md`](docs/phase-2-models-and-migrations.md).

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

> **Upgrading from Phase 1?** Phase 2 introduces a custom user model, which
> Django can only create on a database that has never been migrated. Reset
> the volume once — `docker compose down -v`, then `up` and `migrate`
> again. This deletes all local data.

## Log In

Migrations create a super administrator for you, so there is no
`createsuperuser` step:

| Username     | Password       |
| ------------ | -------------- |
| `superadmin` | `ChangeMe123!` |

Both are read from `SUPERADMIN_USERNAME` / `SUPERADMIN_PASSWORD` in `.env` —
change them there before the first `migrate` if you want different ones, or
afterwards with:

```bash
docker compose exec web python manage.py changepassword superadmin
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
│   ├── core/              # Shared abstract models (no tables of its own)
│   ├── accounts/          # User, Role, Permission + RBAC migrations
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
    ├── phase-1-setup.md
    └── phase-2-models-and-migrations.md
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

- No signup or login screens yet — users and roles exist in the database and
  in Django Admin, but the public-facing auth pages are Phase 3
- No ticket, department or knowledge-base models — dashboard data is still
  static mock data
- Sidebar links other than **Dashboard** are placeholders (`#`)
- No AI/ML service — the dashboard shows a "not configured yet" card instead

## Next Planned Phase

Phase 3 adds the signup and login screens on top of the Phase 2 models
(registration that grants the REQUESTER role, login, logout, and role-aware
navigation), followed by the ticket-management data model and CRUD pages.

## Documentation

- [`docs/phase-1-setup.md`](docs/phase-1-setup.md) — how the boilerplate,
  Docker setup and templates fit together
- [`docs/phase-2-models-and-migrations.md`](docs/phase-2-models-and-migrations.md)
  — the identity/RBAC models, the migration workflow, and **the pattern to
  follow when adding the remaining modules**
- `docs/ResolveAI_Database_Schema_Design.pdf` — the full target schema
- `docs/ResolveAI_Complete_Project_SRS_Proposal.pdf` — project requirements
