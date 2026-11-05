# StudyTrack

StudyTrack is a timer-first personal study tracker built with Django. Track class,
notes, practice time, and other activities; review daily, weekly, and monthly
reports; and export completed sessions as CSV.

## Features

- Start and stop a persistent study timer.
- Add, rename, color-code, deactivate, and delete subjects.
- Review daily totals, subject breakdowns, and weekly and monthly reports.
- Edit or delete completed time-log entries.
- Export completed sessions as a CSV backup.
- Store data locally with SQLite or connect to PostgreSQL for deployment.

## Quick start

The Django project is in the `studytrack/` directory. From the repository root,
run:

```powershell
cd studytrack
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. On macOS or Linux, activate the environment with
`source .venv/bin/activate` instead.

The `seed_data` command is safe to run more than once. It creates the eleven
default subjects if they do not already exist and does not create study sessions.
Additional subjects can be added in **Settings**.

## Validation

Run these commands from `studytrack/`:

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check
```

## Configuration

Local development uses SQLite by default and does not require environment
variables. See [`studytrack/.env.example`](studytrack/.env.example) for the
available settings. Django reads these values from the process environment; the
example file is a reference and is not loaded automatically.

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django secret key; use a private random value outside local development. |
| `DEBUG` | Enables Django debug mode; keep it disabled in production. |
| `DATABASE_URL` | Optional database URL; leave blank to use local SQLite. |
| `ALLOWED_HOSTS` | Comma-separated hostnames accepted by Django. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins for HTTPS form submissions. |

Never publish a real secret key, database URL, `.env` file, or database backup.

## Deploying with Render and Neon

The repository includes a Render Blueprint in [`studytrack/render.yaml`](studytrack/render.yaml).

1. Create a Neon PostgreSQL database and copy its connection URL.
2. In Render, create a Blueprint from this repository.
3. Set the service's `DATABASE_URL` to the Neon connection URL.
4. Deploy. The Blueprint installs dependencies, collects static files, applies
   migrations, and starts the Django app with Gunicorn.

Render generates `SECRET_KEY` and configures production settings. The service
uses `/health/` for its health check. Keep database credentials and other
production secrets in the hosting provider's environment settings, not in Git.
