# Auth Flow

## Overview

Authentication uses JWT access and refresh tokens. Access tokens are short-lived and used for API requests; refresh tokens have longer expiry and are used to obtain new access tokens.

## Endpoints

- `POST /api/v1/register` — register with `email` and `password`.
- `POST /api/v1/login` — accepts form `email` + `password`, returns `access_token` and `refresh_token`.
- `POST /api/v1/token` — token endpoint. Supports `grant_type=refresh_token` with form field `refresh_token` to obtain a new access token.

## Client behavior

1. Client logs in with email/password and stores `access_token` and `refresh_token`.
2. For every request, client sends `Authorization: Bearer <access_token>`.
3. If server responds `401 Unauthorized`, client attempts to refresh:
   - Call `POST /api/v1/token` with `grant_type=refresh_token` and `refresh_token` form field.
   - If successful, replace stored tokens and retry the original request.
   - If refresh fails, client must prompt user to re-authenticate.

### Notes

- `POST /api/v1/login` and `POST /api/v1/token` now share the same `AuthRequest` contract, but `grant_type` controls whether `password` or `refresh_token` is required.
- `refresh_token` may be omitted for direct login, but is mandatory for token refresh requests.

## Bot specifics

- Telegram bot auto-registers users with synthetic email `{user_id}@tg.local` and password equal to the numeric ID.
- Bot stores `access` and `refresh` tokens in Redis under `tg_tokens:{user_id}` to survive restarts.
