# Backend Deployment

The full checked-in Ubuntu deployment runbook now lives at:

- `docs/deployment/ubuntu-nginx-gunicorn-postgresql-django-q2.md`

Checked-in deployment artifacts:

- `deploy/nginx/repeating-process-app.conf`
- `deploy/systemd/repeating-process-app-gunicorn.service`
- `deploy/systemd/repeating-process-app-qcluster.service`

The backend still runs with the repository's real WSGI module:

```bash
gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -
```

Production environment variable names remain defined by `backend/.env.example`.
