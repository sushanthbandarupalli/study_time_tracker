# StudyTrack

StudyTrack is a timer-first personal exam study tracker. Start a Class, Notes, Practice Time, or Other timer, then stop it when finished. Dates, times, durations, dashboards, reports, and a downloadable CSV backup are handled automatically.

## Local setup (Windows)

```powershell
cd "C:\path\to\Personal Portfolio\studytrack"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

StudyTrack requires Neon PostgreSQL and will not fall back to SQLite. Set
`DATABASE_URL` in this folder's `.env` using the connection string from your
Neon project. Django loads `.env` automatically.

Copy `.env.example` to `.env` and set `EMAIL_HOST_USER` to your Gmail address and
`EMAIL_HOST_PASSWORD` to a Google App Password. Then open http://127.0.0.1:8000/
and create an account. A six-digit verification code is sent to that inbox. If
SMTP credentials are missing, the message (including the code) is printed in the
development server console. Each new user receives eleven private default
subjects; additional subjects can be added in Settings.

Email/password accounts must verify their email address with the emailed OTP
before signing in. If the email is already registered, signup offers a sign-in
link instead of sending another code. OTP delivery failures are shown to the
user without leaving a partial account. Signed-in users can change their
password by confirming the current password and entering the new password twice.
Password-reset instructions are sent only for registered accounts; the result
page uses the same neutral message either way.
Google sign-in is enabled when `GOOGLE_OAUTH_CLIENT_ID` and
`GOOGLE_OAUTH_CLIENT_SECRET` are configured. Subjects, timers, reports, and CSV
exports are scoped to the signed-in user.

Run validation with:

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check
```

## Environment variables

Copy `.env.example` to `.env`; Django loads it automatically. Set
`DATABASE_URL` to your Neon PostgreSQL connection string (use the pooled
endpoint for app traffic). For Gmail delivery, enable 2-Step
Verification on the Google account, create an App Password in Google Account
Security settings, and use that App Password (not the normal Gmail password) as
`EMAIL_HOST_PASSWORD`. Do not commit `.env` or share the App Password.

| Variable | Local value | Production value |
| --- | --- | --- |
| `SECRET_KEY` | any private development value | a long random secret |
| `DEBUG` | `True` | `False` |
| `DATABASE_URL` | Neon PostgreSQL URL (pooled for app traffic) | Neon PostgreSQL connection string |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | `.onrender.com` or your exact host |
| `CSRF_TRUSTED_ORIGINS` | blank | `https://*.onrender.com` or your exact URL |
| `SITE_DOMAIN` | `localhost:8000` | Exact public host, without scheme |
| `EMAIL_HOST`, `EMAIL_PORT` | `smtp.gmail.com`, `587` | SMTP server and port for verification email |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Gmail address and Google App Password | Gmail SMTP credentials |
| `EMAIL_USE_TLS` | `True` | `True` for SMTP STARTTLS |
| `DEFAULT_FROM_EMAIL` | blank | Verified sender address |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | blank | Optional Google OAuth credentials |

Never commit the `.env` file or a production database URL.
Create a Web application OAuth client in Google Cloud Console, set
`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, and add
`https://YOUR_HOST/accounts/google/login/callback/` as an authorized redirect URI.

The account-ownership migration stops if it finds pre-authentication subjects or
sessions, to avoid deleting or assigning shared data to the wrong account.
Back up and manually assign that legacy data before retrying the migration.

## CSV backup

Open **Time Log** and choose **Export CSV**. The file contains every completed entry with date, subject, activity, start/end time, duration, and notes.

## Deploy with Neon + Render

1. Create a free Neon project and copy its pooled PostgreSQL connection string.
2. Push this repository to GitHub.
3. In Render, choose **New → Blueprint** and select the repository. The included `render.yaml` creates the StudyTrack web service.
4. Set `DATABASE_URL`, `SITE_DOMAIN`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
   and `DEFAULT_FROM_EMAIL` in Render. Use a Google App Password for
   `EMAIL_HOST_PASSWORD`; keep it in Render's secret environment settings, never
   in Git. Render generates `SECRET_KEY` and sets `DEBUG=False` from the
   blueprint.
5. Optionally add Google OAuth credentials and register the deployed callback URI with Google Cloud.
6. Deploy. Render runs install, `collectstatic`, and migrations automatically, then starts Gunicorn. `/health/` is configured as the health check.

Render's free service can sleep when idle; the first request after sleep can be slow. Data remains safe because production data is stored in Neon PostgreSQL rather than Render's ephemeral filesystem.
