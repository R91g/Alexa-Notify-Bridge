# Changelog

## 1.3.0

- **New `GET /status` endpoint:** Returns bridge diagnostics (region, credentials configured, token validity & remaining TTL, effective expiry/debounce settings, history count, and uptime), protected by `API_KEY` when configured.
- **Accept `message` alias in `POST /notify`:** Requests can now use either `"message"` or `"creator_name"` (100% backwards-compatible).
- **1-click Alexa Skill setup wizard (`setup-skill.sh` + `.devcontainer`):** Automated bilingual wizard for GitHub Codespaces, Docker, and local Node.js that creates the private skill, applies proactive permissions, allows custom skill naming, and prints `ALEXA_CLIENT_ID` and `ALEXA_CLIENT_SECRET`.
- **Security upgrades:**
  - Updated dependencies to `fastapi==0.165.0` (`starlette==1.10.0`), `uvicorn==0.54.0`, `httpx==0.28.1`, `pydantic==2.14.4`, and `python-dotenv==1.2.4` (fixes Starlette CVEs).
  - Upgraded base images to Python 3.13 (`3.13-alpine3.22` for the add-on, `python:3.13-slim` for standalone Docker) replacing EOL Alpine 3.18.
  - Drop root privileges in the add-on using `su-exec` (`appuser`) and confine the Python API runtime in a strict AppArmor child profile without broad filesystem access.
  - Sanitized upstream error responses so raw Amazon/network error bodies are kept in server logs only.
- **Reliability & HTTP improvements:**
  - Switched internal timers (`TokenCache`, `DebounceFilter`, `RateLimiter`) from `time.time()` to `time.monotonic()` to avoid NTP clock-jump issues.
  - Shared `httpx.AsyncClient` managed in FastAPI `lifespan` with explicit timeouts and TLS connection reuse.
  - Prevented duplicate OAuth token refreshes on concurrent `401` responses.
  - Mapped upstream Amazon errors cleanly to `502 Bad Gateway` (with specific log hints for `403` and `432` daily quota) and timeouts to `504 Gateway Timeout`, plus `Retry-After` headers on local `429` rate limits.
  - Safe parsing for numeric environment variables (no startup crashes on typos or `NaN`/`Infinity`).
- **Documentation:** Added Spanish add-on documentation (`DOCS_es.md`), Alexa+ (Early Access) compatibility notes, and expanded the test suite to 33 passing tests.

## 1.2.1

- Rollback debounce cache on delivery failure: if Amazon API or network fails, the message is unblocked so subsequent retries succeed immediately.
- Prevent startup crash (`ValueError`) when optional numeric environment variables are left empty in `.env` (`DEFAULT_EXPIRY_HOURS=""`, `DEBOUNCE_SECONDS=""`).
- Concurrency protection: thread-safe `asyncio.Lock` in `TokenCache` to prevent duplicate OAuth2 token requests during concurrent notifications.
- Validation hardening: reject `NaN` and `Infinity` values in Pydantic models (`allow_inf_nan=False`).
- Memory bound in `DebounceFilter`: enforce `_max_entries` limit by pruning oldest entry when the cache is full.
- Home Assistant Watchdog: enable native HA supervisor watchdog monitoring on `/health` endpoint.
- Add-on schema alignment: adjust minimum `default_expiry_hours` to 0.1 (6 min) to prevent out-of-bounds warnings on startup.
- Robust Bashio parsing: use `bashio::config.has_value` in `run.sh` to prevent empty fields exporting literal `"null"` strings.
- Pure Python Uvicorn: switch to `uvicorn` (without `[standard]` C-extensions) to ensure reliable multi-arch builds on Alpine Linux (armv7/armhf).
- CI/CD synchronization check: automated CI check ensuring standalone and add-on files remain strictly identical.

## 1.2.0

- Automatic message truncation: messages exceeding Amazon's 256-character limit are automatically truncated to 253 characters + `...` with warning logs, ensuring notifications are never dropped.
- In-memory anti-duplicate debounce filter: ignore identical consecutive notifications within a configurable time window (`debounce_seconds`, default: 0 / disabled) to prevent repeating alerts from bouncing sensors.
- Fix validation error handling: strip non-serializable exception objects from Pydantic error contexts to ensure validation failures return HTTP 422 instead of 500.
- Automated test suite: 20 unit tests with mocked Amazon APIs for fast and isolated verification.
- CI/CD workflow: GitHub Actions pipeline running test suite and validating Docker builds for both standalone and add-on images on every push and PR.

## 1.1.1

- Automatically clamp notification expiry between 5 minutes and 24 hours (Amazon's allowed limits) with clear warning logs when adjusted.
- Auto-recovery: refresh expired access tokens automatically on 401 errors and retry.
- Enhanced `/notify` response: now includes `reference_id` and effective `expiry_hours`.
- Enhanced `/history`: added optional `?limit=N` query parameter.
- Home Assistant integration: updated `rest_command` and UI script examples to support `expiry_hours`.

## 1.1.0

- Configurable notification expiry: default 24h (was 1h), adjustable globally or per request via `expiry_hours`.
- Automatic retry on transient Amazon API errors (1 retry after 2s delay).
- New `/history` endpoint: returns the last 50 sent notifications (in-memory).

## 1.0.2

- Add custom AppArmor profile to elevate security rating to 6.

## 1.0.1

- Fix `s6-overlay-suexec` PID 1 error by setting `init: false` in add-on configuration.
- Enforce LF line endings for shell scripts.

## 1.0.0

- Initial release as Home Assistant add-on
- Configuration via Home Assistant UI (credentials, region, API key, log level)
- Support for NA, EU and FE Amazon regions
- Optional API key protection for the /notify endpoint
- Configurable log level
- Rate limiting (10 requests per 10-second window)
