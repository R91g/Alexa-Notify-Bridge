# Changelog

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
