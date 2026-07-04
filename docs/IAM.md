# IAM & Authentication

The API supports two authentication modes, selected by `CE_AUTH_MODE` (default `demo`).
Existing suites and the demo experience run in `demo` mode with no behavioral change.

## Auth model

`get_current_user` accepts **either** credential, checked in this order:

1. `Authorization: Bearer <api-key>` — programmatic access (agents, CLI, MCP, demo UI).
   Keys are `ce_<kind>_<32 hex>`, stored as sha256. Unchanged in both modes.
2. `ce_session` httpOnly cookie — an HS256 JWT `{sub, email, iat, exp}` signed with
   `CE_SECRET_KEY`. The browser SPA drives cookie sessions in `oidc` mode.

An invalid/expired cookie falls through to `401 {"detail": "Not authenticated"}`.

## Settings (env prefix `CE_`)

| Setting | Env | Default |
| --- | --- | --- |
| `auth_mode` | `CE_AUTH_MODE` | `demo` |
| `secret_key` | `CE_SECRET_KEY` | `dev-secret-change-me` |
| `oidc_issuer` | `CE_OIDC_ISSUER` | `""` |
| `oidc_client_id` | `CE_OIDC_CLIENT_ID` | `""` |
| `oidc_client_secret` | `CE_OIDC_CLIENT_SECRET` | `""` |
| `oidc_redirect_url` | `CE_OIDC_REDIRECT_URL` | `http://localhost:8000/v1/auth/callback` |
| `session_ttl_hours` | `CE_SESSION_TTL_HOURS` | `12` |
| `allowed_email_domains` | `CE_ALLOWED_EMAIL_DOMAINS` | `[]` (any) |
| `cookie_secure` | `CE_COOKIE_SECURE` | `false` |

## OIDC flow (Authorization Code, confidential client)

1. `GET /v1/auth/login` → `{authorization_url}` (409 in demo mode). The SPA redirects
   the browser there. A signed `state` JWT (10 min) protects against CSRF.
2. The provider redirects back to `GET /v1/auth/callback?code=&state=`. The backend
   validates `state`, exchanges the `code` at the token endpoint, and validates the ID
   token (RS256 signature via the issuer JWKS, `aud=client_id`, `iss`, `exp`).
3. **JIT provisioning** — if `users.email` is unknown and the domain is allowlisted
   (or the allowlist is empty), a `viewer` user is created (`auth.jit_provision`
   audit). A non-allowlisted domain is rejected with `403`.
4. `last_login_at` + `external_subject` are updated, an `auth.login` audit row is
   written, the `ce_session` cookie is set (httpOnly, SameSite=Lax, path=/), and the
   browser is 302-redirected to the UI origin.

Inactive users are rejected with `403` at login and on every subsequent request.

Endpoints:

- `GET /v1/auth/login` (no auth)
- `GET /v1/auth/callback` (no auth)
- `POST /v1/auth/logout` → `204`, clears the cookie
- `GET /v1/auth/session` (auth-optional) → `{auth_mode, authenticated, user}`

## Run OIDC locally with Keycloak

```bash
docker compose up -d keycloak            # http://localhost:8081 (admin/admin)
```

The `keycloak` service imports `backend/keycloak/realm-org-context.json` on start:
realm `org-context`, confidential client `org-context-api`
(secret `dev-client-secret`), demo users `admin@demo.dev` (Ava Admin, admin),
`priya@demo.dev` (lead), `liam@demo.dev` (engineer) — password `demo1234`. The emails
match the seeded org, so SSO logs into the seeded identity with its role, team, and ACLs.

Point the API at it and switch to oidc mode:

```bash
export CE_AUTH_MODE=oidc
export CE_OIDC_ISSUER=http://localhost:8081/realms/org-context
export CE_OIDC_CLIENT_ID=org-context-api
export CE_OIDC_CLIENT_SECRET=dev-client-secret
export CE_SECRET_KEY=dev-secret-change-me
```

A login whose email matches no platform user is JIT-provisioned as `viewer` (subject to
`CE_ALLOWED_EMAIL_DOMAINS` when set); promote via Admin → Users or
`PATCH /v1/admin/users/{id}`.

The SPA queries `GET /v1/auth/session` on boot; when unauthenticated in oidc mode it
shows a full-screen login page whose button fetches `authorization_url` and redirects.

## Production notes

- Use a real IdP. Set `CE_OIDC_ISSUER` / client id / secret from the provider:

  | Provider | Issuer |
  | --- | --- |
  | Okta | `https://<org>.okta.com/oauth2/default` |
  | Auth0 | `https://<tenant>.auth0.com/` |
  | Google | `https://accounts.google.com` |

  Register `https://<api-host>/v1/auth/callback` as the redirect URI.
- Generate a strong random `CE_SECRET_KEY` and store it in a secret manager (never
  commit it). Rotating it invalidates all live sessions.
- Set `CE_COOKIE_SECURE=true` in production so the cookie is only sent over HTTPS.
- Constrain sign-ups with `CE_ALLOWED_EMAIL_DOMAINS` (comma/JSON list) to your org
  domains; an empty list allows any authenticated email.
