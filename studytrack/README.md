# StudyTrack

StudyTrack is a timer-first personal exam study tracker. Start a Class, Notes, Practice Time, or Other timer, then stop it when finished. Dates, times, durations, dashboards, reports, and a downloadable CSV backup are handled automatically.

## Local setup (Windows)

```powershell
cd "C:\path\to\Personal Portfolio\studytrack"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Open http://127.0.0.1:8000/. The `seed_data` command is idempotent: it creates only the eleven placeholder subjects and never adds study sessions.

Run validation with:

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check
```

## Environment variables

Copy `.env.example` for reference; local development works with SQLite when `DATABASE_URL` is empty.

| Variable | Local value | Production value |
| --- | --- | --- |
| `SECRET_KEY` | any private development value | a long random secret |
| `DEBUG` | `True` | `False` |
| `DATABASE_URL` | blank (SQLite) | Neon PostgreSQL connection string |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | `.onrender.com` or your exact host |
| `CSRF_TRUSTED_ORIGINS` | blank | `https://*.onrender.com` or your exact URL |

Never commit the `.env` file or a production database URL.

## CSV backup

Open **Time Log** and choose **Export CSV**. The file contains every completed entry with date, subject, activity, start/end time, duration, and notes.

## Deploy with Neon + Render

1. Create a free Neon project and copy its pooled PostgreSQL connection string.
2. Push this repository to GitHub.
3. In Render, choose **New → Blueprint** and select the repository. The included `render.yaml` creates the StudyTrack web service.
4. Set `DATABASE_URL` in Render to the Neon connection string. Render generates `SECRET_KEY` and sets `DEBUG=False` from the blueprint.
5. Deploy. Render runs install, `collectstatic`, and migrations automatically, then starts Gunicorn. `/health/` is configured as the health check.

Render's free service can sleep when idle; the first request after sleep can be slow. Data remains safe because production data is stored in Neon PostgreSQL rather than Render's ephemeral filesystem.
