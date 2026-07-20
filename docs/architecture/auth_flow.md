# Auth Flow

## Overview

Authentication uses JWT access and refresh tokens (`app/auth.py`). Access tokens are
short-lived and used for API requests; refresh tokens have longer expiry and are used to obtain
new access tokens. Passwords are hashed with bcrypt directly (not passlib), truncated to 72
bytes before hashing (bcrypt's hard limit).

**Token lifetimes:** access — 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`); refresh — 7 days
(`REFRESH_TOKEN_EXPIRE_DAYS`). Algorithm — HS256, signed with `SECRET_KEY`.

**JWT claims:** `{"sub": <email>, "tv": <token_version>, "exp": ..., "type": "access"|"refresh"}`.
`tv` is the user's `token_version` column at the moment the token was issued.

## Endpoints

- `POST /api/v1/register` — register with `email` and `password` (+ optional profile/weight fields).
- `POST /api/v1/login` — accepts JSON (or form-urlencoded fallback) `email` + `password`, returns `access_token` and `refresh_token`.
- `POST /api/v1/token` — OAuth2-compatible endpoint. `grant_type=password` behaves like `/login`; `grant_type=refresh_token` (with `refresh_token` field) issues a new token pair.
- `GET /api/v1/me` — current user, requires a valid access token.
- `POST /api/v1/change-password` — requires current + new password; bumps `token_version`.

## Client behavior

1. Client logs in with email/password and stores `access_token` and `refresh_token`.
2. For every request, client sends `Authorization: Bearer <access_token>`.
3. If server responds `401 Unauthorized`, client attempts to refresh:
   - Call `POST /api/v1/token` with `grant_type=refresh_token` and `refresh_token`.
   - If successful, replace stored tokens and retry the original request.
   - If refresh fails, client must prompt user to re-authenticate.
4. The React frontend (`frontend/src/api/axios.ts`) implements this exact flow via an axios
   response interceptor, with in-flight-request de-duplication so concurrent 401s trigger only
   one refresh call.

### Token revocation on password change

`get_current_user()` (`app/auth.py`) decodes the access token, loads the user by `sub` (email),
then compares the token's `tv` claim against the user's **current** `token_version` column. If
they don't match, the request is rejected with `401` even though the token hasn't technically
expired. `POST /api/v1/change-password` increments `token_version`, which instantly invalidates
every access/refresh token issued before the change — including a token an attacker may have
stolen. The same check applies to refresh tokens in `POST /api/v1/token` with
`grant_type=refresh_token`.

### Notes

- `POST /api/v1/login` and `POST /api/v1/token` share the same `AuthRequest` contract; `grant_type` controls whether `password` or `refresh_token` is required.
- `refresh_token` may be omitted for direct login, but is mandatory for token refresh requests.

## Bot specifics (`app/telegram_bot.py`)

- The Telegram bot auto-registers users with a synthetic email `{telegram_user_id}@tg.local`.
- **Password is a random secret**, not the numeric Telegram ID. On first registration the bot
  generates `secrets.token_urlsafe(24)` and stores it in Redis under `tg_pwd:{user_id}`
  (`_password_key`/`_set_password`/`_get_password`). This matters because Telegram user IDs are
  not secret — if the password were the numeric ID, anyone could log into any bot-created account
  through the plain `/api/v1/login` endpoint.
- **Legacy migration:** accounts created before this fix used `str(user_id)` as the password.
  `_migrate_legacy_account()` detects a failed login with the current stored/random password,
  retries with the old numeric-ID password, and if that succeeds immediately rotates it to a
  fresh random secret via `POST /api/v1/change-password`.
- Bot stores `access` and `refresh` tokens in Redis under `tg_tokens:{user_id}` (hash with
  `access`/`refresh` fields) to survive bot restarts — see `_store_tokens`/`_get_tokens`/`_pop_tokens`.
- `api_client.APIClient` handles token refresh transparently: on a `401` it retries once with
  `POST /api/v1/token` (`grant_type=refresh_token`) before giving up.

## Known limitation

There is no server-side token blacklist/allowlist beyond `token_version` — an access token is
valid for its full 30-minute lifetime unless the user changes their password. Logout is purely
client-side (dropping the stored token); the Telegram bot's "🚪 Выйти" (logout) button clears
local Redis-stored tokens but there is no corresponding revocation call to the API.
