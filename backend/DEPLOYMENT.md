# Backend Deployment

## Gunicorn

Install production dependencies from `backend/requirements.txt`, then start Django with:

```bash
gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -
```

Run that command from the `backend/` directory after setting the required environment variables in your deployment environment.

## Security-related environment variables

Set these explicitly for production:

- `DEBUG=False`
- `SECRET_KEY=<long-random-secret>`
- `ALLOWED_HOSTS=api.example.com`
- `CORS_ALLOWED_ORIGINS=https://app.example.com`
- `CSRF_TRUSTED_ORIGINS=https://app.example.com`
- `FRONTEND_URL=https://app.example.com`
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `USE_X_FORWARDED_PROTO=True` when Django is behind a reverse proxy that sends `X-Forwarded-Proto`

HSTS is intentionally opt-in:

- `SECURE_HSTS_SECONDS=0` keeps HSTS disabled until HTTPS is confirmed end to end.
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True` only after you have validated every subdomain.
- `SECURE_HSTS_PRELOAD=True` only if you intentionally want preload behavior and meet preload requirements.
