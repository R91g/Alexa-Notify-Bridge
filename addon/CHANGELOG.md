# Changelog

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
