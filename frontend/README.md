# frontend

Minimal Vue frontend used to test the backend JWT authentication flow from a browser. This is
temporary scaffolding for backend integration testing, not the final product UI.

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

The API client targets `http://127.0.0.1:8000/api`, so run the Django backend locally before
testing the frontend.

## Auth Flow Test Steps

1. Open `/auth/register` and submit `username`, `email`, and `password`.
2. Open `/auth/login` and log in with `username` and `password`.
3. After login you will be redirected to `/dashboard`, which verifies protected access through
   `GET /api/auth/me/`.
4. Use the logout button on `/dashboard` to send the refresh token to `POST /api/auth/logout/`.
5. Open `/auth/password-reset` to request a reset email.
6. Copy the `uid` and `token` from the email or Django log output, then submit them with a new
   password at `/auth/password-reset/confirm`.

## Notes

- Tokens are stored in `localStorage` only as a temporary test implementation. The final storage
  strategy can be reviewed later.
- The dashboard route is protected in the frontend and also verifies backend access using the
  authenticated `/api/auth/me/` endpoint.
- Validation and auth errors are surfaced as normal form messages rather than raw JSON dumps.

### Compile and Minify for Production

```sh
npm run build
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```
