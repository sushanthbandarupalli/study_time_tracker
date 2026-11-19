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

Copy `.env.example` to `.env` and set `DATABASE_URL`. Open
http://127.0.0.1:8000/ to create an account with a unique username and password.
Each new user receives eleven private default subjects; additional subjects can
be added in Settings.

Email verification and email-based password resets are not used. Configure
Google OAuth with `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`;
users must link a Google account before accessing tracker data. To recover a
forgotten password, sign in through the previously linked Google account, then
use **Recovery settings** to set a new password. Keep Google linked to the
account so it remains a recovery option. Google sign-in can also be used to
create an account. Subjects, timers, reports, and CSV exports are scoped to the
signed-in user.

Run validation with:

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check
```

## Environment variables

Copy `.env.example` to `.env`; Django loads it automatically. Set
`DATABASE_URL` to your Neon PostgreSQL connection string (use the pooled
endpoint for app traffic). Do not commit `.env`, OAuth credentials, or
passwords.

| Variable | Local value | Production value |
| --- | --- | --- |
| `SECRET_KEY` | any private development value | a long random secret |
| `DEBUG` | `True` | `False` |
| `DATABASE_URL` | Neon PostgreSQL URL (pooled for app traffic) | Neon PostgreSQL connection string |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | `.onrender.com` or your exact host |
| `CSRF_TRUSTED_ORIGINS` | blank | `https://*.onrender.com` or your exact URL |
| `SITE_DOMAIN` | `localhost:8000` | Exact public host, without scheme |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth credentials | Required to let users link Google and recover passwords |

Never commit the `.env` file or a production database URL.
Create a Web application OAuth client in Google Cloud Console, set
`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, and add
`http://127.0.0.1:8000/accounts/google/login/callback/` as a local authorized
redirect URI. For Render, add the deployed callback URI using the service's
`onrender.com` hostname. For a no-cost test deployment, keep the consent screen
in Testing and add the Google accounts that should be allowed to sign in as test
users; Google may show an unverified-app warning until the app is verified.

The account-ownership migration stops if it finds pre-authentication subjects or
sessions, to avoid deleting or assigning shared data to the wrong account.
Back up and manually assign that legacy data before retrying the migration.

## CSV backup

Open **Time Log** and choose **Export CSV**. The file contains every completed entry with date, subject, activity, start/end time, duration, and notes.

## Deploy with Neon + Render

1. Create a free Neon project and copy its pooled PostgreSQL connection string.
2. Push this repository to GitHub.
3. In Render, choose **New → Blueprint** and select the repository. The included `render.yaml` creates the StudyTrack web service.
4. Set `DATABASE_URL`, `SITE_DOMAIN`, `GOOGLE_OAUTH_CLIENT_ID`, and
   `GOOGLE_OAUTH_CLIENT_SECRET` in Render. Register
   `https://YOUR-RENDER-HOST/accounts/google/login/callback/` as an authorized
   redirect URI in Google Cloud. Keep OAuth credentials in Render's secret
   environment settings, never in Git. Render generates `SECRET_KEY` and sets
   `DEBUG=False` from the blueprint.
5. Deploy. Render runs install, `collectstatic`, and migrations automatically,
   then starts Gunicorn. `/health/` is configured as the health check.

No email sender or paid domain is needed for this authentication flow. The
service can sleep when idle; the first request after sleep can be slow. Data
remains safe because production data is stored in Neon PostgreSQL rather than
Render's ephemeral filesystem.
