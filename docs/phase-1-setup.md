# Phase 1 Setup Guide

This document explains what was built in Phase 1 and how it works, written
for someone new to the project (and possibly new to Django or Docker).

## What Was Created

- A Django project called `config` and one Django app called `dashboard`.
- A Docker Compose setup with two containers: `web` (Django) and `db` (MySQL).
- Django templates that reuse the AdminLTE 4 layout (navbar, sidebar,
  content area, footer).
- One real page: the dashboard, at `/`.
- Django Admin enabled at `/admin/`.

Nothing else exists yet — no tickets, no login page, no AI service. Those
are for later phases.

## How Docker Compose Works

`docker-compose.yml` describes the two services ResolveAI needs to run:

- **`web`** builds the image from `web/Dockerfile`, installs Python
  dependencies, and runs `python manage.py runserver 0.0.0.0:8000`. Port
  `8000` on your machine is mapped to port `8000` in the container, and the
  `web/` folder is mounted into the container so code changes on your
  machine show up immediately without rebuilding.
- **`db`** runs the official `mysql:8` image. It has a health check
  (`mysqladmin ping`) so Docker knows when MySQL is actually ready to
  accept connections, not just "started". `web` waits for `db` to be
  healthy before it starts, using `depends_on: condition: service_healthy`.

Both containers read configuration from the `.env` file at the repo root
(`env_file: .env` for `web`, individual `${VARS}` for `db`).

## What the `web` Container Does

It's a standard Django development server. On every request it:

1. Matches the URL against `config/urls.py`.
2. Runs the matching view function in `dashboard/views.py`.
3. Renders a template with `django.shortcuts.render`.

## What the `db` Container Does

It's a plain MySQL 8 server with a database, user and password created
from the environment variables in `.env`. Data is stored in a Docker
volume (`mysql_data`) so it survives container restarts — `docker compose
down -v` is the only thing that erases it.

## How Django Connects to MySQL

`web/config/settings.py` defines `DATABASES["default"]` using
`django.db.backends.mysql`, with the host, port, database name, user and
password all read from environment variables via `os.getenv(...)`. Since
`web` and `db` are on the same Docker Compose network, Django connects to
MySQL simply by host name `db` (the service name in `docker-compose.yml`).

Django's MySQL backend normally expects the `mysqlclient` driver, which
needs a C compiler and MySQL's dev headers to install. To keep the image
build simple and fast, this project uses `PyMySQL` instead — a pure-Python
driver with the same interface. `web/config/__init__.py` calls
`pymysql.install_as_MySQLdb()` so Django uses it transparently; nothing
elsewhere in the codebase needs to know the difference.

`db/init/01-grant-test-db.sql` is run automatically by the MySQL image the
first time it starts on an empty volume. It grants the app's database user
access to `test_*` databases too, which Django's test runner needs to
create a throwaway database when you run `manage.py test`.

## How Django Templates Are Organized

```text
web/templates/
├── base.html              # the shared page skeleton
├── includes/
│   ├── navbar.html         # top navigation bar
│   ├── sidebar.html        # left sidebar menu
│   ├── footer.html         # page footer
│   └── messages.html       # Django messages framework output
└── dashboard/
    └── index.html          # the dashboard page content
```

`base.html` contains the full HTML document — `<head>`, the AdminLTE app
wrapper, and `{% include %}` tags for the navbar, sidebar and footer. It
exposes template blocks (`title`, `page_title`, `breadcrumbs`, `content`,
`extra_css`, `extra_js`) that child pages can fill in.

`dashboard/index.html` extends `base.html` and only fills in the `content`
block — it doesn't repeat any of the layout markup.

## How AdminLTE Was Integrated

The AdminLTE 4 template we were given ships as static HTML pages with two
self-contained files: `assets/css/adminlte.css` and `assets/js/adminlte.js`
(AdminLTE 4 bundles everything into a single file, unlike AdminLTE 3's
separate plugin folders). Those two files were copied — unmodified — into
`web/static/adminlte/css/` and `web/static/adminlte/js/`. The original
template directory was never edited.

AdminLTE 4 also depends on a few third-party libraries (Bootstrap 5,
Popper, Bootstrap Icons, OverlayScrollbars, a web font). Rather than vendor
those into the repo, `base.html` loads them from a CDN, exactly like the
original template did. This avoids adding a frontend build step for
something this simple.

We then took the HTML structure from the template's
`dashboard-admin.html` (the navbar, sidebar and page layout markup) and
turned it into the Django includes described above, trimming it down to
what Phase 1 actually needs (for example, the sidebar only lists four
items instead of the full menu).

## How the Base Layout Works

Every page in the app should extend `base.html`:

```django
{% extends "base.html" %}

{% block title %}My Page{% endblock %}

{% block content %}
  <p>Page content goes here.</p>
{% endblock %}
```

`base.html` takes care of the `<head>`, the navbar/sidebar/footer, and
loading all CSS/JS — a new page never needs to repeat any of that.

## How to Create Another Page Later

1. Add a view function to `dashboard/views.py` (or a new app's `views.py`
   if the page belongs to a different area of the product).
2. Add a `path(...)` entry to that app's `urls.py`.
3. Create a template that extends `base.html` and fills in the blocks it
   needs (usually `title`, `page_title`, `breadcrumbs` and `content`).
4. Link to it from the sidebar (see below) if it should be reachable from
   the main navigation.

## How to Add Another Sidebar Link Later

Open `web/templates/includes/sidebar.html` and add a new `<li class="nav-item">`
following the existing pattern, pointing `href` at your new URL (use
`{% url 'your-url-name' %}` instead of a hard-coded path once the page is
real) and giving it a `bi-*` Bootstrap Icon.

## Running Tests

```bash
docker compose exec web python manage.py test
```

`dashboard/tests.py` has three small tests: the dashboard page returns
HTTP 200, it renders `dashboard/index.html`, and the response contains the
text "ResolveAI". Use this file as a model for tests on future pages.
