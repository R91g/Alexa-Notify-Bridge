"""Unit and integration tests for Alexa Notify Bridge.

Amazon LWA and Proactive Events APIs are mocked with httpx.MockTransport;
no real network calls or Amazon credentials required.

Run from repository root:
    pytest
"""

import asyncio
import importlib
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_RealAsyncClient = httpx.AsyncClient
_open_clients: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_test_clients():
    """Ensure every TestClient created in a test exits its lifespan cleanly."""
    yield
    while _open_clients:
        client = _open_clients.pop()
        client.__exit__(None, None, None)


class FakeAmazon:
    """Simulates Amazon LWA OAuth and Proactive Events API."""

    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.token_status = 200
        self.token_counter = 0
        self.proactive_status = 202
        self.proactive_responses: list[int | Exception] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        url = str(request.url)

        if url == "https://api.amazon.com/auth/o2/token":
            if self.token_status == 200:
                self.token_counter += 1
                return httpx.Response(
                    200,
                    json={
                        "access_token": f"mock-lwa-token-{self.token_counter}",
                        "expires_in": 3600,
                    },
                )
            return httpx.Response(self.token_status, text="OAuth failed")

        if "proactiveEvents" in url:
            # If a queue of responses was configured, pop the next one
            if self.proactive_responses:
                next_item = self.proactive_responses.pop(0)
                if isinstance(next_item, Exception):
                    raise next_item
                status = next_item
            else:
                status = self.proactive_status

            if status == 202:
                return httpx.Response(202)
            return httpx.Response(status, text=f"Amazon internal error body {status}")

        return httpx.Response(404, text=f"Unexpected URL: {url}")

    def requests_to(self, pattern: str) -> list[httpx.Request]:
        return [c for c in self.calls if pattern in str(c.url)]


def make_test_client(monkeypatch, env_overrides: dict | None = None) -> tuple[TestClient, FakeAmazon]:
    """Factory creating an isolated TestClient with clean environment and mocked Amazon API."""
    env = {
        "ALEXA_CLIENT_ID": "mock-client-id",
        "ALEXA_CLIENT_SECRET": "mock-client-secret",
        "PROACTIVE_EVENTS_URL": "https://api.eu.amazonalexa.com/v1/proactiveEvents/stages/development",
        "DEFAULT_EXPIRY_HOURS": "24",
    }
    if env_overrides:
        env.update(env_overrides)

    # Clean existing environment variables
    for key in (
        "ALEXA_CLIENT_ID",
        "ALEXA_CLIENT_SECRET",
        "API_KEY",
        "PROACTIVE_EVENTS_URL",
        "DEFAULT_EXPIRY_HOURS",
        "DEBOUNCE_SECONDS",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    for k, v in env.items():
        if v is not None:
            monkeypatch.setenv(k, str(v))

    # Prevent local .env file from polluting tests
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)

    fake = FakeAmazon()

    def mocked_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake.handler)
        return _RealAsyncClient(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mocked_async_client)

    # Reload main module to apply new environment settings
    sys.modules.pop("main", None)
    main = importlib.import_module("main")

    client = TestClient(main.app)
    client.__enter__()  # Trigger lifespan startup checks
    _open_clients.append(client)
    fake.calls.clear()

    return client, fake


# ─── Health check ────────────────────────────────────────────────────────────


def test_health_endpoint(monkeypatch):
    """GET /health returns 200 and status ok."""
    client, _ = make_test_client(monkeypatch)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_endpoint_returns_diagnostics(monkeypatch):
    """GET /status reports region, credentials, token validity, config and history count."""
    client, _ = make_test_client(
        monkeypatch,
        {
            "PROACTIVE_EVENTS_URL": "https://api.amazonalexa.com/v1/proactiveEvents/stages/development",
            "DEBOUNCE_SECONDS": "15",
            "DEFAULT_EXPIRY_HOURS": "12",
        },
    )
    client.post("/notify", json={"message": "Status check msg"})

    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["region"] == "NA"
    assert data["credentials_configured"] is True
    assert data["api_key_enabled"] is False
    assert data["token_valid"] is True
    assert data["token_expires_in_seconds"] > 0
    assert data["default_expiry_hours"] == 12.0
    assert data["debounce_seconds"] == 15.0
    assert data["history_count"] == 1
    assert data["uptime_seconds"] >= 0


def test_status_endpoint_requires_api_key_when_configured(monkeypatch):
    """GET /status enforces API_KEY when configured and reports api_key_enabled=True."""
    client, _ = make_test_client(monkeypatch, {"API_KEY": "my-secret"})
    assert client.get("/status").status_code == 403
    r = client.get("/status", headers={"x-api-key": "my-secret"})
    assert r.status_code == 200
    assert r.json()["api_key_enabled"] is True


def test_status_endpoint_when_credentials_missing(monkeypatch):
    """GET /status cleanly reports credentials_configured=False and token_valid=False when unset."""
    client, _ = make_test_client(
        monkeypatch,
        {"ALEXA_CLIENT_ID": "", "ALEXA_CLIENT_SECRET": ""},
    )
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["credentials_configured"] is False
    assert data["token_valid"] is False
    assert data["token_expires_in_seconds"] == 0


# ─── Notification delivery ───────────────────────────────────────────────────


def test_successful_notification(monkeypatch):
    """POST /notify delivers a MessageAlert.Activated proactive event."""
    client, fake = make_test_client(monkeypatch)
    payload = {"creator_name": "La puerta del garaje está abierta"}

    response = client.post("/notify", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Notification sent successfully"
    assert "reference_id" in data
    assert data["expiry_hours"] == 24.0

    # Verify Amazon event payload
    proactive_calls = fake.requests_to("proactiveEvents")
    assert len(proactive_calls) == 1

    event_body = json.loads(proactive_calls[0].content)
    assert event_body["event"]["name"] == "AMAZON.MessageAlert.Activated"
    assert event_body["event"]["payload"]["messageGroup"]["creator"]["name"] == "La puerta del garaje está abierta"
    assert event_body["event"]["payload"]["messageGroup"]["count"] == 1
    assert event_body["event"]["payload"]["messageGroup"]["urgency"] == "URGENT"
    assert event_body["relevantAudience"]["type"] == "Multicast"


def test_notification_accepts_message_alias(monkeypatch):
    """POST /notify accepts 'message' as an intuitive alias for 'creator_name'."""
    client, fake = make_test_client(monkeypatch)
    response = client.post("/notify", json={"message": "La lavadora ha terminado"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    proactive_calls = fake.requests_to("proactiveEvents")
    assert len(proactive_calls) == 1
    event_body = json.loads(proactive_calls[0].content)
    assert event_body["event"]["payload"]["messageGroup"]["creator"]["name"] == "La lavadora ha terminado"


def test_notification_empty_message_alias_returns_422(monkeypatch):
    """Empty or whitespace-only 'message' alias is rejected with 422."""
    client, _ = make_test_client(monkeypatch)
    assert client.post("/notify", json={"message": ""}).status_code == 422
    assert client.post("/notify", json={"message": "   "}).status_code == 422


def test_token_caching(monkeypatch):
    """Access token is cached and reused across multiple notifications."""
    client, fake = make_test_client(monkeypatch)

    client.post("/notify", json={"creator_name": "First message"})
    client.post("/notify", json={"creator_name": "Second message"})

    # Token was loaded during startup; subsequent calls reuse the cached token (0 extra calls)
    token_calls = fake.requests_to("/auth/o2/token")
    assert len(token_calls) == 0

    proactive_calls = fake.requests_to("proactiveEvents")
    assert len(proactive_calls) == 2


def test_shared_http_client_reused_and_closed_on_shutdown(monkeypatch):
    """Lifespan creates a shared AsyncClient with explicit timeout and closes it cleanly on exit."""
    client, _ = make_test_client(monkeypatch)
    import main

    shared = main.http_client
    assert shared is not None
    assert not shared.is_closed
    assert shared.timeout == main.HTTP_TIMEOUT

    client.post("/notify", json={"creator_name": "Reuse client test"})
    assert main.http_client is shared

    # Manually trigger shutdown and verify closure
    _open_clients.remove(client)
    client.__exit__(None, None, None)
    assert shared.is_closed
    assert main.http_client is None


# ─── Expiry hours clamping ───────────────────────────────────────────────────


def test_expiry_hours_minimum_clamped_to_5_minutes(monkeypatch):
    """Values below 5 minutes (0.0833h) are clamped to 5 minutes."""
    client, _ = make_test_client(monkeypatch)
    response = client.post("/notify", json={"creator_name": "Test min", "expiry_hours": 0.01})
    assert response.status_code == 200
    assert response.json()["expiry_hours"] == 0.08  # 5 min in hours rounded to 2 decimals


def test_expiry_hours_maximum_clamped_to_24_hours(monkeypatch):
    """Values above 24 hours are clamped to 24 hours."""
    client, _ = make_test_client(monkeypatch)
    response = client.post("/notify", json={"creator_name": "Test max", "expiry_hours": 72.0})
    assert response.status_code == 200
    assert response.json()["expiry_hours"] == 24.0


def test_expiry_hours_valid_custom_value(monkeypatch):
    """Custom expiry values within limits (e.g. 2.5h) are preserved."""
    client, _ = make_test_client(monkeypatch)
    response = client.post("/notify", json={"creator_name": "Test custom", "expiry_hours": 2.5})
    assert response.status_code == 200
    assert response.json()["expiry_hours"] == 2.5


# ─── Validation and Error Handling ──────────────────────────────────────────


def test_missing_creator_name_returns_422(monkeypatch):
    """Missing creator_name returns 422 Unprocessable Entity (not 500)."""
    client, _ = make_test_client(monkeypatch)
    response = client.post("/notify", json={})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    # Ensure ctx was stripped and response is valid JSON
    assert isinstance(data["detail"], list)


def test_creator_name_exceeding_256_chars_is_automatically_truncated(monkeypatch):
    """Text exceeding Amazon's 256 character limit is automatically truncated to 253 + '...'."""
    client, fake = make_test_client(monkeypatch)
    original_text = "A" * 300
    expected_text = ("A" * 253) + "..."

    response = client.post("/notify", json={"creator_name": original_text})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data.get("truncated") is True

    # Check payload sent to Amazon
    proactive_calls = fake.requests_to("proactiveEvents")
    assert len(proactive_calls) == 1
    event_body = json.loads(proactive_calls[0].content)
    sent_name = event_body["event"]["payload"]["messageGroup"]["creator"]["name"]
    assert sent_name == expected_text
    assert len(sent_name) == 256


def test_empty_or_whitespace_creator_name_returns_422(monkeypatch):
    """Empty or whitespace-only messages are rejected with 422."""
    client, _ = make_test_client(monkeypatch)
    r1 = client.post("/notify", json={"creator_name": ""})
    assert r1.status_code == 422
    r2 = client.post("/notify", json={"creator_name": "   "})
    assert r2.status_code == 422


def test_invalid_json_body_returns_422(monkeypatch):
    """Malformed body triggers validation handler cleanly."""
    client, _ = make_test_client(monkeypatch)
    response = client.post(
        "/notify",
        content="not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_empty_env_vars_fallback_cleanly(monkeypatch):
    """Empty strings in optional numeric env vars fall back to defaults without ValueError."""
    client, _ = make_test_client(
        monkeypatch,
        {"DEFAULT_EXPIRY_HOURS": "", "DEBOUNCE_SECONDS": "", "LOG_LEVEL": ""},
    )
    response = client.post("/notify", json={"creator_name": "Env fallback test"})
    assert response.status_code == 200
    assert response.json()["expiry_hours"] == 24.0


def test_invalid_and_non_finite_env_vars_fallback_cleanly(monkeypatch):
    """Invalid strings or NaN/Infinity in numeric env vars fall back to defaults without crashing."""
    client, _ = make_test_client(
        monkeypatch,
        {"DEFAULT_EXPIRY_HOURS": "24h", "DEBOUNCE_SECONDS": "inf"},
    )
    import main

    assert main.DEFAULT_EXPIRY_HOURS == 24.0
    assert main.DEBOUNCE_SECONDS == 0.0
    response = client.post("/notify", json={"creator_name": "Bad env test"})
    assert response.status_code == 200


# ─── Debounce Filter (Anti-Duplicates) ───────────────────────────────────────


def test_debounce_ignores_duplicate_within_window(monkeypatch):
    """Duplicate notification sent within debounce window is ignored and not sent to Amazon."""
    client, fake = make_test_client(monkeypatch, {"DEBOUNCE_SECONDS": "5"})

    # 1st notification -> sent
    r1 = client.post("/notify", json={"creator_name": "Puerta abierta"})
    assert r1.status_code == 200
    assert r1.json()["status"] == "success"
    assert len(fake.requests_to("proactiveEvents")) == 1

    # 2nd notification with same text -> debounced/ignored
    r2 = client.post("/notify", json={"creator_name": "Puerta abierta"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "ignored"
    assert r2.json()["debounced"] is True
    # Amazon was NOT called again
    assert len(fake.requests_to("proactiveEvents")) == 1

    # 3rd notification with DIFFERENT text -> sent
    r3 = client.post("/notify", json={"creator_name": "Ventana abierta"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "success"
    assert len(fake.requests_to("proactiveEvents")) == 2


def test_debounce_per_request_override(monkeypatch):
    """Payload parameter debounce_seconds overrides global setting."""
    client, fake = make_test_client(monkeypatch, {"DEBOUNCE_SECONDS": "0"})

    r1 = client.post("/notify", json={"creator_name": "Alarma", "debounce_seconds": 10})
    assert r1.status_code == 200
    assert r1.json()["status"] == "success"

    r2 = client.post("/notify", json={"creator_name": "Alarma", "debounce_seconds": 10})
    assert r2.status_code == 200
    assert r2.json()["status"] == "ignored"
    assert r2.json()["debounced"] is True

    assert len(fake.requests_to("proactiveEvents")) == 1


def test_debounce_rollback_on_delivery_failure(monkeypatch):
    """If delivery to Amazon fails, the message is removed from debounce cache so retries succeed."""
    client, fake = make_test_client(monkeypatch, {"DEBOUNCE_SECONDS": "60"})
    fake.proactive_responses = [500, 500, 202]

    async def _dummy_sleep():
        return

    monkeypatch.setattr("asyncio.sleep", lambda s: _dummy_sleep())

    # 1st attempt fails after retry (both 500s consumed) -> 502 Bad Gateway
    r1 = client.post("/notify", json={"creator_name": "Fallo temporal"})
    assert r1.status_code == 502

    # Immediate retry with identical text must NOT be debounced
    r2 = client.post("/notify", json={"creator_name": "Fallo temporal"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "success"


# ─── API Key Authentication ─────────────────────────────────────────────────


def test_api_key_required_when_configured(monkeypatch):
    """When API_KEY is set, requests without valid x-api-key header return 403 on /notify and /history."""
    client, _ = make_test_client(monkeypatch, {"API_KEY": "  secret-token-123  "})

    # No key provided
    r1 = client.post("/notify", json={"creator_name": "Hello"})
    assert r1.status_code == 403
    assert client.get("/history").status_code == 403

    # Wrong key provided
    r2 = client.post(
        "/notify",
        json={"creator_name": "Hello"},
        headers={"x-api-key": "wrong-token"},
    )
    assert r2.status_code == 403

    # Correct trimmed key provided
    r3 = client.post(
        "/notify",
        json={"creator_name": "Hello"},
        headers={"x-api-key": "secret-token-123"},
    )
    assert r3.status_code == 200
    assert client.get("/history", headers={"x-api-key": "secret-token-123"}).status_code == 200


def test_api_key_not_required_when_not_configured(monkeypatch):
    """When API_KEY is empty or whitespace-only, requests without x-api-key succeed."""
    client, _ = make_test_client(monkeypatch, {"API_KEY": "   "})
    response = client.post("/notify", json={"creator_name": "Hello"})
    assert response.status_code == 200


# ─── Rate Limiting ───────────────────────────────────────────────────────────


def test_rate_limiter_allows_up_to_10_and_blocks_11th(monkeypatch):
    """Rate limiter allows 10 requests per 10s window and returns 429 with Retry-After on the 11th."""
    client, _ = make_test_client(monkeypatch)

    for i in range(10):
        r = client.post("/notify", json={"creator_name": f"Message {i}"})
        assert r.status_code == 200, f"Request {i} failed: {r.text}"

    # 11th request must be rate limited with Retry-After header
    r11 = client.post("/notify", json={"creator_name": "Message 11"})
    assert r11.status_code == 429
    assert "Rate limit" in r11.json()["detail"]
    assert "retry-after" in r11.headers
    assert int(r11.headers["retry-after"]) >= 1


# ─── History Endpoint ────────────────────────────────────────────────────────


def test_history_records_sent_notifications(monkeypatch):
    """GET /history lists recent notifications in reverse chronological order."""
    client, _ = make_test_client(monkeypatch)

    client.post("/notify", json={"creator_name": "Msg 1"})
    client.post("/notify", json={"creator_name": "Msg 2"})

    response = client.get("/history")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["notifications"][0]["message"] == "Msg 2"
    assert data["notifications"][1]["message"] == "Msg 1"


def test_history_respects_limit_parameter(monkeypatch):
    """GET /history?limit=1 limits the returned entries."""
    client, _ = make_test_client(monkeypatch)

    client.post("/notify", json={"creator_name": "Msg 1"})
    client.post("/notify", json={"creator_name": "Msg 2"})

    response = client.get("/history?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["total"] == 2
    assert data["notifications"][0]["message"] == "Msg 2"


# ─── Retry & Upstream Amazon Error Handling ──────────────────────────────────


def test_token_refreshed_on_401_unauthorized(monkeypatch):
    """If Amazon returns 401 Unauthorized, the bridge refreshes the token and retries."""
    client, fake = make_test_client(monkeypatch)
    # First proactive call returns 401, second returns 202
    fake.proactive_responses = [401, 202]

    response = client.post("/notify", json={"creator_name": "Retry test"})
    assert response.status_code == 200

    # Token requested once on refresh (startup token was cleared from fake.calls)
    assert len(fake.requests_to("/auth/o2/token")) == 1
    assert len(fake.requests_to("proactiveEvents")) == 2


@pytest.mark.anyio
async def test_concurrent_401_triggers_single_token_refresh(monkeypatch):
    """Two concurrent refresh calls for the same failed token only hit LWA once."""
    client, fake = make_test_client(monkeypatch)
    import main

    stale_token = main.token_cache.token
    assert stale_token is not None

    t1, t2 = await asyncio.gather(
        main.get_access_token(force_refresh=True, failed_token=stale_token),
        main.get_access_token(force_refresh=True, failed_token=stale_token),
    )
    assert t1 == t2
    assert t1 != stale_token
    assert len(fake.requests_to("/auth/o2/token")) == 1


def test_retry_on_5xx_server_error(monkeypatch):
    """If Amazon returns 500 once and then 202, retry succeeds."""
    client, fake = make_test_client(monkeypatch)
    fake.proactive_responses = [500, 202]

    async def _dummy_sleep():
        return

    monkeypatch.setattr("asyncio.sleep", lambda s: _dummy_sleep())

    response = client.post("/notify", json={"creator_name": "Retry 500 test"})
    assert response.status_code == 200
    assert len(fake.requests_to("proactiveEvents")) == 2


def test_upstream_403_returns_502_without_leaking_body(monkeypatch):
    """Upstream Amazon 403 maps to 502 (distinct from local API_KEY 403) and hides raw error body."""
    client, fake = make_test_client(monkeypatch)
    fake.proactive_responses = [403]

    response = client.post("/notify", json={"creator_name": "Forbidden test"})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "403" in detail
    assert "Amazon internal error body" not in detail


def test_upstream_432_daily_quota_returns_502(monkeypatch):
    """Upstream Amazon 432 daily quota error maps cleanly to 502."""
    client, fake = make_test_client(monkeypatch)
    fake.proactive_responses = [432]

    response = client.post("/notify", json={"creator_name": "Quota test"})
    assert response.status_code == 502
    assert "432" in response.json()["detail"]


def test_upstream_timeout_returns_504(monkeypatch):
    """Timeout contacting Amazon Proactive Events API retries once and returns 504."""
    client, fake = make_test_client(monkeypatch)
    fake.proactive_responses = [
        httpx.ReadTimeout("timed out"),
        httpx.ReadTimeout("timed out again"),
    ]

    async def _dummy_sleep():
        return

    monkeypatch.setattr("asyncio.sleep", lambda s: _dummy_sleep())

    response = client.post("/notify", json={"creator_name": "Timeout test"})
    assert response.status_code == 504
    assert len(fake.requests_to("proactiveEvents")) == 2


@pytest.mark.anyio
async def test_validation_exception_handler_handles_non_serializable_ctx():
    """Ensure validation_exception_handler strips non-serializable 'ctx' objects and returns 422."""
    import main
    from fastapi.exceptions import RequestValidationError
    from starlette.requests import Request

    # Craft a validation error whose ctx contains an actual Python Exception object
    raw_error = {
        "type": "value_error",
        "loc": ("body", "custom_field"),
        "msg": "Value error message",
        "input": "bad",
        "ctx": {"error": ValueError("non-serializable exception object")},
    }
    exc = RequestValidationError([raw_error])
    req = Request(scope={"type": "http", "method": "POST", "path": "/notify", "headers": []})

    response = await main.validation_exception_handler(req, exc)
    assert response.status_code == 422
    body = json.loads(response.body)
    assert "detail" in body
    assert "ctx" not in body["detail"][0]
    assert body["detail"][0]["msg"] == "Value error message"
