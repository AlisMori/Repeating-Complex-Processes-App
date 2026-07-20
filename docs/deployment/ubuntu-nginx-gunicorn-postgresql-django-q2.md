# Ubuntu Deployment Guide

This guide targets the current repository layout:

- Django backend: `backend/`
- Django entrypoint: `backend/manage.py`
- Django WSGI module: `core.wsgi:application`
- Django environment file read by settings: `backend/.env`
- Django static output: `backend/staticfiles/`
- Django email log path expected by settings: `backend/logs/emails.log`
- Vue frontend source: `frontend/`
- Vue production build output: `frontend/dist/`
- Vue API base variable: `VITE_API_BASE_URL`

Values in angle brackets must be replaced in your deployment copy:

- `<app-user>`: dedicated Unix account for the application
- `<app-group>`: primary group for `<app-user>`
- `<app-domain>`: public frontend hostname, for example `app.example.edu`
- `<api-domain>`: backend hostname if different from `<app-domain>`; if the frontend and API share one host, use the same value for both
- `<db-name>`, `<db-user>`: PostgreSQL database and login role names
- `<release-id>`: release folder name such as `2026-07-20.1`

## 1. Required Ubuntu packages

Install the OS packages first:

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-dev \
  build-essential \
  libpq-dev \
  postgresql \
  postgresql-contrib \
  nginx \
  git \
  curl \
  ca-certificates \
  ufw
```

This repository also requires Node.js that satisfies `frontend/package.json`:

- required by repo: `^22.18.0 || >=24.12.0`
- verify after installation: `node --version`
- verify npm after installation: `npm --version`

Use your institution's approved Node.js distribution method, but do not proceed until `node --version` satisfies the repo engine constraint above.

## 2. Application user and directories

Create a locked-down service account and deployment directories:

```bash
sudo adduser \
  --system \
  --home /srv/repeating-process-app \
  --group \
  <app-user>

sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app
sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app/releases
sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app/shared
sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app/shared/backups
sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app/shared/runbooks
sudo install -d -o root -g <app-group> -m 0750 /etc/repeating-process-app
```

Recommended layout on the server:

```text
/srv/repeating-process-app/
  current -> /srv/repeating-process-app/releases/<release-id>
  releases/
  shared/
    backups/
    runbooks/
```

Copy the repository into a release directory:

```bash
sudo -u <app-user> mkdir -p /srv/repeating-process-app/releases/<release-id>
sudo -u <app-user> git clone <your-git-remote> /srv/repeating-process-app/releases/<release-id>
sudo ln -sfn /srv/repeating-process-app/releases/<release-id> /srv/repeating-process-app/current
```

If university IT deploys from a tarball instead of Git, keep the same release layout and unpack the repository contents into `/srv/repeating-process-app/releases/<release-id>`.

## 3. Python virtual environment

Create the backend virtual environment inside the checked-out release:

```bash
sudo -u <app-user> python3 -m venv /srv/repeating-process-app/current/backend/.venv
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python -m pip install --upgrade pip setuptools wheel
```

## 4. Backend dependency installation

Install the exact backend requirements from the repository:

```bash
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/pip install -r /srv/repeating-process-app/current/backend/requirements.txt
```

Create the backend runtime directories expected by Django settings:

```bash
sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app/current/backend/logs
sudo install -d -o <app-user> -g <app-group> -m 0755 /srv/repeating-process-app/current/backend/staticfiles
```

## 5. PostgreSQL database and user setup

Create the database role and database. Replace the password interactively when prompted:

```bash
sudo -u postgres createuser --pwprompt <db-user>
sudo -u postgres createdb --owner <db-user> <db-name>
```

Validate the new database:

```bash
sudo -u postgres psql -d postgres -c "\du <db-user>"
sudo -u postgres psql -d <db-name> -c "\dt"
```

The Django settings in `backend/core/settings.py` expect these variables:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## 6. Environment file location and permissions

The application loads environment variables from `backend/.env`, so keep the secret source of truth in `/etc/repeating-process-app/backend.env` and link it into the release.

Create the file:

```bash
sudo install -o root -g <app-group> -m 0640 /dev/null /etc/repeating-process-app/backend.env
sudo editor /etc/repeating-process-app/backend.env
```

Populate it with the real variable names from `backend/.env.example`:

```dotenv
SECRET_KEY=<replace-with-long-random-secret>
DEBUG=False

ALLOWED_HOSTS=<replace-with-comma-separated-hostnames>
CORS_ALLOWED_ORIGINS=https://<app-domain>
CSRF_TRUSTED_ORIGINS=https://<app-domain>

DB_NAME=<db-name>
DB_USER=<db-user>
DB_PASSWORD=<replace-with-db-password>
DB_HOST=localhost
DB_PORT=5432

EMAIL_HOST=<replace-if-smtp-is-used>
EMAIL_PORT=587
EMAIL_HOST_USER=<replace-if-smtp-is-used>
EMAIL_HOST_PASSWORD=<replace-if-smtp-is-used>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=<replace-if-smtp-is-used>

FRONTEND_URL=https://<app-domain>
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
USE_X_FORWARDED_PROTO=True

Q_CLUSTER_WORKERS=2
PASSWORD_RESET_THROTTLE_RATE=5/hour
PASSWORD_RESET_CONFIRM_THROTTLE_RATE=10/hour
```

Link the file into the release so Django reads it at `backend/.env`:

```bash
sudo ln -sfn /etc/repeating-process-app/backend.env /srv/repeating-process-app/current/backend/.env
sudo chown -h root:<app-group> /srv/repeating-process-app/current/backend/.env
```

Permissions guidance:

- `/etc/repeating-process-app/backend.env`: `0640`, owned by `root:<app-group>`
- `/srv/repeating-process-app/current/backend/.env`: symlink owned by root, target remains outside Git
- `/srv/repeating-process-app/current/backend/logs`: writable by `<app-user>`
- never commit a real `.env` file into the repository

## 7. Migrations

Run Django migrations from the backend directory after the environment file exists:

```bash
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py migrate
```

`notifications.apps.NotificationsConfig` automatically registers the notification schedule on `post_migrate`, but the daily maintenance schedule still needs the explicit command below.

## 8. Frontend clean install and production build

The frontend build uses Vite and writes the production bundle to `frontend/dist/`.

Create the frontend environment file and build:

```bash
sudo install -o root -g <app-group> -m 0640 /dev/null /etc/repeating-process-app/frontend.env
printf 'VITE_API_BASE_URL=/api\n' | sudo tee /etc/repeating-process-app/frontend.env >/dev/null
sudo ln -sfn /etc/repeating-process-app/frontend.env /srv/repeating-process-app/current/frontend/.env
sudo chown -h root:<app-group> /srv/repeating-process-app/current/frontend/.env
sudo -u <app-user> bash -lc 'cd /srv/repeating-process-app/current/frontend && rm -rf node_modules dist && npm ci && npm run build'
```

Verify the build output exists:

```bash
sudo -u <app-user> test -f /srv/repeating-process-app/current/frontend/dist/index.html
```

## 9. Collectstatic

Collect Django static files into `backend/staticfiles/`:

```bash
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py collectstatic --noinput
```

## 10. Scheduler registration and service startup

Register the recurring jobs once per environment:

```bash
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py setup_scheduled_jobs
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py setup_notification_schedule
```

Install the checked-in service files from this repository:

```bash
sudo cp /srv/repeating-process-app/current/deploy/systemd/repeating-process-app-gunicorn.service /etc/systemd/system/
sudo cp /srv/repeating-process-app/current/deploy/systemd/repeating-process-app-qcluster.service /etc/systemd/system/
sudo editor /etc/systemd/system/repeating-process-app-gunicorn.service
sudo editor /etc/systemd/system/repeating-process-app-qcluster.service
sudo systemctl daemon-reload
sudo systemctl enable --now repeating-process-app-gunicorn.service
sudo systemctl enable --now repeating-process-app-qcluster.service
```

Replace these values before starting the services:

- `<app-user>`
- `<app-group>`

Install the checked-in Nginx site file from this repository:

```bash
sudo cp /srv/repeating-process-app/current/deploy/nginx/repeating-process-app.conf /etc/nginx/sites-available/repeating-process-app.conf
sudo editor /etc/nginx/sites-available/repeating-process-app.conf
sudo ln -sfn /etc/nginx/sites-available/repeating-process-app.conf /etc/nginx/sites-enabled/repeating-process-app.conf
sudo nginx -t
sudo systemctl reload nginx
```

Replace `<app-domain>` in the copied Nginx file before running `nginx -t`.

## 11. Verification commands

Run these after deployment:

```bash
sudo systemctl status repeating-process-app-gunicorn.service --no-pager
sudo systemctl status repeating-process-app-qcluster.service --no-pager
sudo systemctl status nginx --no-pager
sudo journalctl -u repeating-process-app-gunicorn.service -n 100 --no-pager
sudo journalctl -u repeating-process-app-qcluster.service -n 100 --no-pager
curl -I http://127.0.0.1/
curl -I http://127.0.0.1/favicon.ico
curl -I http://127.0.0.1/static/admin/css/base.css
curl -i http://127.0.0.1/api/auth/password-reset/ -X POST -H 'Content-Type: application/json' -d '{}'
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py check --deploy
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py showmigrations
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py shell -c "from django_q.models import Schedule; print(list(Schedule.objects.values_list('func', flat=True)))"
```

Expected results:

- `curl -I http://127.0.0.1/` returns `200 OK`
- `curl -I http://127.0.0.1/favicon.ico` returns `200 OK`
- `curl -I http://127.0.0.1/static/admin/css/base.css` returns `200 OK`
- `POST /api/auth/password-reset/` returns JSON from Django, usually `400` for an empty body, which proves Nginx to Gunicorn proxying is working
- both systemd units show `active (running)`

## 12. Safe restart, status, and log commands

Safe service operations:

```bash
sudo systemctl restart repeating-process-app-gunicorn.service
sudo systemctl restart repeating-process-app-qcluster.service
sudo systemctl reload nginx
sudo systemctl status repeating-process-app-gunicorn.service --no-pager
sudo systemctl status repeating-process-app-qcluster.service --no-pager
sudo systemctl status nginx --no-pager
sudo journalctl -u repeating-process-app-gunicorn.service -f
sudo journalctl -u repeating-process-app-qcluster.service -f
sudo tail -f /srv/repeating-process-app/current/backend/logs/emails.log
```

Use `restart`, not `stop`, during normal deployments so qcluster resumes scheduled work immediately after the new release comes up.

## 13. Deployment checklist

- Confirm DNS for `<app-domain>` and, if separate, `<api-domain>`
- Confirm the server has Node.js satisfying `^22.18.0 || >=24.12.0`
- Confirm `/etc/repeating-process-app/backend.env` exists with production secrets
- Confirm `/srv/repeating-process-app/current` points at the intended release
- Create or refresh `backend/.venv`
- Run `pip install -r backend/requirements.txt`
- Run `npm ci && npm run build` in `frontend/`
- Run `manage.py migrate`
- Run `manage.py collectstatic --noinput`
- Run `manage.py setup_scheduled_jobs`
- Run `manage.py setup_notification_schedule`
- Install or validate the Nginx config
- Install or validate both systemd unit files
- Replace placeholders in the copied Nginx and systemd files
- Run `nginx -t`
- Restart Gunicorn and qcluster
- Reload Nginx
- Execute the smoke checks in section 17
- Review Gunicorn, qcluster, Nginx, and `backend/logs/emails.log`

## 14. PostgreSQL backup and restore

Create a compressed backup:

```bash
sudo -u postgres pg_dump -Fc -d <db-name> -f /srv/repeating-process-app/shared/backups/<db-name>-$(date +%F-%H%M%S).dump
```

List backup contents:

```bash
sudo -u postgres pg_restore -l /srv/repeating-process-app/shared/backups/<backup-file>.dump
```

Restore into the live database after an outage window is approved:

```bash
sudo systemctl stop repeating-process-app-qcluster.service
sudo systemctl stop repeating-process-app-gunicorn.service
sudo -u postgres dropdb <db-name>
sudo -u postgres createdb --owner <db-user> <db-name>
sudo -u postgres pg_restore -d <db-name> /srv/repeating-process-app/shared/backups/<backup-file>.dump
sudo systemctl start repeating-process-app-gunicorn.service
sudo systemctl start repeating-process-app-qcluster.service
```

Safer dry-run restore into a throwaway database:

```bash
sudo -u postgres createdb --owner <db-user> <db-name>_restore_test
sudo -u postgres pg_restore -d <db-name>_restore_test /srv/repeating-process-app/shared/backups/<backup-file>.dump
sudo -u postgres dropdb <db-name>_restore_test
```

## 15. Rollback procedure

Rollback order matters because the repository contains both schema changes and built frontend assets.

### Application code

Switch `current` back to the last known-good release:

```bash
sudo ln -sfn /srv/repeating-process-app/releases/<previous-release-id> /srv/repeating-process-app/current
```

### Frontend build

Rebuild the frontend from the rollback release before reloading Nginx:

```bash
sudo -u <app-user> bash -lc 'cd /srv/repeating-process-app/current/frontend && rm -rf node_modules dist && npm ci && npm run build'
```

### Python dependencies

Reinstall backend dependencies from the rollback release in its own virtual environment:

```bash
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/pip install -r /srv/repeating-process-app/current/backend/requirements.txt
```

### Database restoration

If the failed deploy included schema or data migrations that are not backward-compatible, restore the matching PostgreSQL backup instead of only switching code:

```bash
sudo systemctl stop repeating-process-app-qcluster.service
sudo systemctl stop repeating-process-app-gunicorn.service
sudo -u postgres dropdb <db-name>
sudo -u postgres createdb --owner <db-user> <db-name>
sudo -u postgres pg_restore -d <db-name> /srv/repeating-process-app/shared/backups/<pre-deploy-backup>.dump
sudo systemctl start repeating-process-app-gunicorn.service
sudo systemctl start repeating-process-app-qcluster.service
```

### Migration risks

- Do not assume a Django migration is reversible just because `migrate` succeeds going forward.
- Any deploy containing destructive schema changes or data migrations requires a fresh backup taken immediately before `manage.py migrate`.
- qcluster should be stopped before restoring a backup so background jobs do not run against a half-restored database.
- After rollback, rerun `manage.py showmigrations` and application smoke checks before reopening access.

## 16. Ownership, permissions, and firewall guidance

Recommended ownership:

- `/srv/repeating-process-app/releases/*`: `<app-user>:<app-group>`
- `/srv/repeating-process-app/current`: symlink managed by root during cutover
- `/etc/repeating-process-app/backend.env`: `root:<app-group>` with `0640`
- `/etc/repeating-process-app/frontend.env`: `root:<app-group>` with `0640`
- `/srv/repeating-process-app/current/backend/logs`: `<app-user>:<app-group>` with `0755`
- `/srv/repeating-process-app/current/backend/staticfiles`: `<app-user>:<app-group>` with `0755`

Firewall baseline with UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status verbose
```

Do not expose PostgreSQL or Gunicorn directly to the internet. PostgreSQL should stay bound to localhost unless university IT explicitly requires a different internal network design.

## 17. Post-deployment smoke checks

Frontend:

```bash
curl -I https://<app-domain>/
curl -I https://<app-domain>/dashboard
```

API routing:

```bash
curl -i https://<app-domain>/api/auth/password-reset/ -X POST -H 'Content-Type: application/json' -d '{}'
curl -i https://<app-domain>/api/search/ -H 'Authorization: Bearer <replace-with-test-token>'
```

Static assets:

```bash
curl -I https://<app-domain>/favicon.ico
curl -I https://<app-domain>/static/admin/css/base.css
```

Authentication:

1. Log in through the Vue frontend with a non-admin test account.
2. Confirm the browser loads authenticated views without a redirect loop.
3. Confirm `/api/auth/me/` returns `200` for the authenticated session.

Scheduler:

```bash
sudo systemctl status repeating-process-app-qcluster.service --no-pager
sudo -u <app-user> /srv/repeating-process-app/current/backend/.venv/bin/python /srv/repeating-process-app/current/backend/manage.py shell -c "from django_q.models import Schedule, Success; print(list(Schedule.objects.values_list('func', flat=True))); print(Success.objects.order_by('-stopped')[:5].count())"
```

Logs:

```bash
sudo journalctl -u repeating-process-app-gunicorn.service -n 50 --no-pager
sudo journalctl -u repeating-process-app-qcluster.service -n 50 --no-pager
sudo tail -n 50 /srv/repeating-process-app/current/backend/logs/emails.log
sudo tail -n 50 /var/log/nginx/repeating-process-app.access.log
sudo tail -n 50 /var/log/nginx/repeating-process-app.error.log
```

## 18. HTTPS guidance

The checked-in Nginx file includes an HTTP server block only. Add HTTPS on the real server after university IT provides:

- the real hostname or hostnames
- the approved certificate management method
- the certificate and private key paths, or a managed TLS termination point

After that, add a `listen 443 ssl http2;` server block, configure the real certificate paths, and keep these settings aligned with the backend environment:

- `FRONTEND_URL=https://<app-domain>`
- `CORS_ALLOWED_ORIGINS=https://<app-domain>`
- `CSRF_TRUSTED_ORIGINS=https://<app-domain>`
- `USE_X_FORWARDED_PROTO=True`
- `SECURE_SSL_REDIRECT=True`

Do not invent certificate paths or commit certificates to Git.
