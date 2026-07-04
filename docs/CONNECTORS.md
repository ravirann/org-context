# Live Connectors

The context engine ships two connector implementations per source type:

- **demo** (default) — deterministic offline fixtures, no network, used by seeds
  and the demo UI. Behavior is unchanged from the base platform.
- **live** — real HTTP against GitHub / Jira / Slack / Confluence.

`config["mode"]` selects the implementation (`"demo"` when absent). Everything
below applies to `mode: "live"`.

## Enabling live mode

A source's `config` JSONB carries the mode plus credentials and scope. Switch an
existing source to live mode via `PATCH /v1/sources/{id}`:

```http
PATCH /v1/sources/{id}
Content-Type: application/json

{
  "config": {
    "mode": "live",
    "token": "ghp_xxxxxxxxxxxxxxxx",
    "org": "acme",
    "repos": ["payments-api", "web-app"],
    "team_name": "Payments"
  }
}
```

Then trigger a sync (`POST /v1/sources/{id}/sync`) or wait for the scheduled run.

### Credential masking

`GET /v1/sources` and every source response return `config` with secret values
masked: keys in `{token, api_token, client_secret, password}` become
`"•••" + last4` (e.g. `"•••x999"`). `sync_state` is returned read-only.

On `PATCH`, a secret value that still starts with the `•••` sentinel is treated
as "unchanged" and the stored secret is preserved; any other value replaces it.
This lets a UI round-trip the masked config without leaking or clobbering secrets.

## Per-type configuration

### github

| field      | required | notes |
|------------|----------|-------|
| `mode`     | yes      | `"live"` |
| `token`    | yes      | Personal Access Token (secret, masked) |
| `org`      | no       | org/owner; prepended to each repo as `org/repo` |
| `repos`    | yes      | list of repo names to sync |
| `api_url`  | no       | defaults to `https://api.github.com` (set for GHE) |
| `team_name`| no       | ACL team for **private** repos |

**PAT scopes**: `repo` (private repos), or `public_repo` for public-only. Reads
pulls, issues, and repo contents (`README.md`).

Emits: PRs (`doc_type=pr`, content = title + body + up to 5 review comments),
repo docs (`README.md` → `doc_type=code`), issues (`doc_type=ticket`; GitHub PRs
returned by the issues endpoint are filtered out).

**external_id**: `pr-<number>`, `issue-<repo>-<number>`, `doc-<repo>-<path>`.

**ACL**: private repo → team-restricted via `team_name`; public repo → public.

### jira

| field       | required | notes |
|-------------|----------|-------|
| `mode`      | yes      | `"live"` |
| `base_url`  | yes      | e.g. `https://acme.atlassian.net` |
| `email`     | yes      | account email (basic-auth username) |
| `api_token` | yes      | Atlassian API token (secret, masked) |
| `jql`       | no       | extra JQL, AND-ed with the cursor clause |
| `restrict_to_team` | no | if set, issues become team-restricted |

**Auth**: HTTP Basic `email:api_token`. Reads `/rest/api/3/search`.

Emits: issues (`doc_type=ticket`, content = summary + description; ADF bodies are
flattened to text). **external_id** = the Jira key (`ENG-1401`). `severity`
mirrors Jira priority (lowercased).

### slack

| field      | required | notes |
|------------|----------|-------|
| `mode`     | yes      | `"live"` |
| `token`    | yes      | Bot token `xoxb-…` (secret, masked) |
| `channels` | yes      | list of channel IDs (e.g. `C01ABCD`) |
| `restrict_to_team` | no | if set, messages become team-restricted |

**Bot scopes**: `channels:history` (+ `groups:history` for private channels) and
`channels:read`. Reads `conversations.history`.

Emits: one `doc_type=message` item **per channel-day** (messages batched by UTC
day, ordered by ts). **external_id** = `slack-<channel>-<first_ts>`.

### confluence

| field        | required | notes |
|--------------|----------|-------|
| `mode`       | yes      | `"live"` |
| `base_url`   | yes      | e.g. `https://acme.atlassian.net/wiki` |
| `email`      | yes      | account email (basic-auth username) |
| `api_token`  | yes      | Atlassian API token (secret, masked) |
| `space_keys` | no       | restrict CQL to these spaces |
| `restrict_to_team` | no | if set, docs become team-restricted |

**Auth**: HTTP Basic `email:api_token`. Reads `/rest/api/content/search` (CQL).

Emits: pages (`doc_type=doc`). Storage-format HTML is stripped to plain text
(block tags → newlines, entities decoded). **external_id** = `conf-<page_id>`.

## Cursor semantics (`sync_state`)

Live connectors read and advance incremental cursors on `source.sync_state`
(a JSONB column). The pipeline persists the mutation after a successful sync
(`flag_modified` marks the JSONB dirty). On a failed sync the cursor is **not**
advanced.

| source type | cursor key(s) | value |
|-------------|---------------|-------|
| github      | `pr_cursor`, `issues_cursor`, `docs_cursor` | ISO-8601 timestamp per stream |
| jira        | `updated_cursor` | ISO-8601 timestamp |
| slack       | `channel_cursor:<channel_id>` | Slack `ts` string |
| confluence  | `lastmodified_cursor` | ISO-8601 timestamp |

**First sync (backfill)**: with no cursor, connectors look back
`config["backfill_days"]` days (default **90**).

## Rate limits & retries

All requests go through a shared async HTTP helper (`connectors/live/http.py`):

- 30s timeout, bearer or basic auth.
- Retries **429** and **5xx** up to 3 times with exponential backoff
  (`0.5 / 2 / 8s`, capped), honoring the `Retry-After` header when present.
- **401 / 403** raise `ConnectorAuthError` immediately (no retry) → the sync is
  marked `sync_status=error` with `last_error` set, and the cursor is preserved.
- Any other non-2xx (or exhausted retries) raises `ConnectorError`.

Malformed individual items are skipped with a warning rather than failing the
whole sync.

## Testing

Live connectors accept a dependency-injected `httpx.AsyncBaseTransport`, so tests
use `httpx.MockTransport` with canned payloads — no real network. See
`tests/unit/test_live_connectors.py` and `tests/integration/test_live_sync.py`.
