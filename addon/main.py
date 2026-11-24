import asyncio
import logging
import math
import os
import secrets
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ─── Logging ─────────────────────────────────────────────────────────────────

LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("alexa-notify-bridge")


def _parse_float_env(name: str, default: float) -> float:
    """Safely parse a finite float from an environment variable, falling back to default."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Invalid numeric value for %s (%r). Falling back to default (%s).",
            name,
            raw,
            default,
        )
        return default
    if not math.isfinite(value):
        logger.warning(
            "Non-finite value for %s (%r). Falling back to default (%s).",
            name,
            raw,
            default,
        )
        return default
    return value


# ─── Alexa credentials ──────────────────────────────────────────────────────

ALEXA_CLIENT_ID = (os.getenv("ALEXA_CLIENT_ID") or "").strip() or None
ALEXA_CLIENT_SECRET = (os.getenv("ALEXA_CLIENT_SECRET") or "").strip() or None

# ─── API Key security (optional, recommended) ───────────────────────────────
# If API_KEY is set in .env, requests must include it in the "x-api-key" header.

API_KEY = (os.getenv("API_KEY") or "").strip() or None
api_key_header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)

if not API_KEY:
    logger.warning(
        "API_KEY is not set. The /notify, /history and /status endpoints are open without authentication. "
        "Set API_KEY in your .env file to protect them."
    )


async def verify_api_key(key: str = Security(api_key_header_scheme)):
    """Validate the API key if one is configured."""
    if API_KEY:
        if not key or not secrets.compare_digest(key, API_KEY):
            raise HTTPException(
                status_code=403,
                detail="Invalid or missing API key.",
            )
    return key


# ─── Amazon endpoints ───────────────────────────────────────────────────────

TOKEN_URL = "https://api.amazon.com/auth/o2/token"

PROACTIVE_EVENTS_URL = (
    (os.getenv("PROACTIVE_EVENTS_URL") or "").strip()
    or "https://api.eu.amazonalexa.com/v1/proactiveEvents/stages/development"
)


def _detect_region(url: str) -> str:
    """Infer the Amazon Alexa API region label from PROACTIVE_EVENTS_URL."""
    if "api.eu.amazonalexa.com" in url:
        return "EU"
    if "api.fe.amazonalexa.com" in url:
        return "FE"
    if "api.amazonalexa.com" in url:
        return "NA"
    return "CUSTOM"


API_REGION = _detect_region(PROACTIVE_EVENTS_URL)
STARTED_AT = time.monotonic()

# Explicit HTTP client timeouts for Amazon LWA & Proactive Events requests
HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Shared HTTP client managed by FastAPI lifespan for TLS/connection reuse
http_client: "httpx.AsyncClient | None" = None


def get_http_client() -> "httpx.AsyncClient":
    """Return the shared AsyncClient, creating one lazily if called outside lifespan."""
    global http_client
    if http_client is None or http_client.is_closed:
        http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    return http_client


# Amazon Proactive Events requires expiry to be between 5 minutes and 24 hours.
MIN_EXPIRY_HOURS = 5 / 60  # 5 minutes (~0.0833 hours)
MAX_EXPIRY_HOURS = 24.0   # 24 hours


def clamp_expiry_hours(hours: float) -> float:
    """Clamp expiry to Amazon's allowed range (5 minutes to 24 hours)."""
    return max(MIN_EXPIRY_HOURS, min(MAX_EXPIRY_HOURS, hours))


_raw_default_expiry = _parse_float_env("DEFAULT_EXPIRY_HOURS", 24.0)
DEFAULT_EXPIRY_HOURS = clamp_expiry_hours(_raw_default_expiry)
if DEFAULT_EXPIRY_HOURS != _raw_default_expiry:
    _adjusted_desc = "5 minutes (minimum)" if DEFAULT_EXPIRY_HOURS == MIN_EXPIRY_HOURS else "24 hours (maximum)"
    logger.warning(
        "Configured DEFAULT_EXPIRY_HOURS (%s) is outside Amazon's limits (5 min to 24h). Adjusted to %s.",
        _raw_default_expiry,
        _adjusted_desc,
    )

# ─── Debounce filter (anti-duplicate notifications) ──────────────────────────
# Minimum time in seconds to prevent sending identical consecutive notifications.
# 0 = disabled. Can be overridden per request via debounce_seconds.

_raw_debounce = _parse_float_env("DEBOUNCE_SECONDS", 0.0)
DEBOUNCE_SECONDS = max(0.0, _raw_debounce)


class DebounceFilter:
    """In-memory cache preventing identical notifications from sounding repeatedly."""

    def __init__(self, max_entries: int = 50):
        self._history: dict[str, float] = {}
        self._max_entries = max_entries
        self._lock = asyncio.Lock()

    async def is_duplicate(self, text: str, window_seconds: float) -> bool:
        """Check if identical text was received within window_seconds. If not, record it."""
        if window_seconds <= 0:
            return False

        async with self._lock:
            now = time.monotonic()
            retention = max(window_seconds, 3600.0)
            self._history = {k: ts for k, ts in self._history.items() if (now - ts) < retention}

            last_time = self._history.get(text)
            if last_time is not None and (now - last_time) < window_seconds:
                return True

            if self._max_entries > 0 and len(self._history) >= self._max_entries and text not in self._history:
                oldest_key = min(self._history, key=self._history.get)
                del self._history[oldest_key]

            self._history[text] = now
            return False

    async def remove(self, text: str) -> None:
        """Remove a recorded message from the debounce cache (e.g., if delivery failed)."""
        async with self._lock:
            self._history.pop(text, None)


debounce_filter = DebounceFilter()

# ─── Message length limits ───────────────────────────────────────────────────
# Amazon limits the MessageAlert creator.name field to 256 characters.

MAX_MESSAGE_CHARS = 256
TRUNCATE_CHARS = 253  # Leaves 3 chars for "..."


def process_message_text(text: str) -> tuple[str, bool]:
    """Strip whitespace and truncate message to 256 chars if it exceeds Amazon's limit.

    Returns (processed_text, was_truncated).
    """
    clean = text.strip()
    if len(clean) > MAX_MESSAGE_CHARS:
        truncated = clean[:TRUNCATE_CHARS] + "..."
        logger.warning(
            "Notification message exceeded Amazon's %d char limit (%d chars). "
            "Truncated automatically to: '%s'",
            MAX_MESSAGE_CHARS,
            len(clean),
            truncated,
        )
        return truncated, True
    return clean, False


# ─── Request model ──────────────────────────────────────────────────────────


class NotificationRequest(BaseModel):
    """Payload expected by the POST /notify endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    creator_name: str = Field(
        ...,
        validation_alias=AliasChoices("creator_name", "message"),
        min_length=1,
        max_length=4096,
        description="The text that Alexa will read aloud (accepts 'creator_name' or 'message'). "
        "If longer than 256 chars, it is automatically truncated to 253 + '...'.",
    )
    urgency: Literal["URGENT"] = "URGENT"
    expiry_hours: float | None = Field(
        default=None,
        allow_inf_nan=False,
        description="Hours until the notification expires (5 min to 24h). "
        "Values under 5 min are adjusted to 5 min; values over 24h are capped at 24h. "
        "If omitted, uses the DEFAULT_EXPIRY_HOURS setting (default: 24h).",
    )
    debounce_seconds: float | None = Field(
        default=None,
        ge=0,
        allow_inf_nan=False,
        description="Optional per-request debounce window in seconds. Overrides DEBOUNCE_SECONDS.",
    )


# ─── Token cache ────────────────────────────────────────────────────────────


class TokenCache:
    """Simple in-memory cache for the Amazon LWA access token.

    Note: the cache is per-process. If you run multiple Uvicorn workers,
    each worker will maintain its own token cache.
    """

    def __init__(self):
        self.token: str | None = None
        self.expires_at: float = 0.0
        self._lock = asyncio.Lock()


token_cache = TokenCache()


async def get_access_token(
    force_refresh: bool = False,
    failed_token: str | None = None,
) -> str:
    """Obtain a valid Amazon LWA access token, using the cache when possible."""
    async with token_cache._lock:
        now = time.monotonic()

        if not force_refresh and token_cache.token and token_cache.expires_at > now:
            return token_cache.token

        # If another concurrent request already refreshed the failed token, reuse the new one
        if (
            force_refresh
            and failed_token is not None
            and token_cache.token
            and token_cache.token != failed_token
            and token_cache.expires_at > now
        ):
            return token_cache.token

        if not ALEXA_CLIENT_ID or not ALEXA_CLIENT_SECRET:
            logger.error("ALEXA_CLIENT_ID or ALEXA_CLIENT_SECRET not configured.")
            raise HTTPException(
                status_code=500,
                detail="Alexa client credentials not configured.",
            )

        client = get_http_client()
        data = {
            "grant_type": "client_credentials",
            "client_id": ALEXA_CLIENT_ID,
            "client_secret": ALEXA_CLIENT_SECRET,
            "scope": "alexa::proactive_events",
        }
        try:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("Timeout obtaining Amazon access token: %s", exc)
            raise HTTPException(
                status_code=504,
                detail="Timeout authenticating with Amazon Alexa API.",
            )
        except httpx.HTTPError as exc:
            logger.error("Failed to obtain Amazon access token: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Failed to authenticate with Amazon Alexa API. Check server logs for details.",
            )

        try:
            token_data = response.json()
            access_token = token_data["access_token"]
            expires_in = float(token_data.get("expires_in", 3600))
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("Malformed Amazon token response: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Received an invalid authentication response from Amazon.",
            )

        token_cache.token = access_token
        # Subtract 60 s as a safety margin for network delays
        token_cache.expires_at = time.monotonic() + max(0.0, expires_in - 60.0)

        logger.info("Amazon access token refreshed successfully.")
        return token_cache.token


# ─── Rate limiter ───────────────────────────────────────────────────────────


class RateLimiter:
    """Prevents flooding Amazon's API by limiting requests in a sliding time window."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 10.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def check(self):
        async with self._lock:
            now = time.monotonic()
            # Remove timestamps outside the window
            self._timestamps = [t for t in self._timestamps if (now - t) < self.window_seconds]
            if len(self._timestamps) >= self.max_requests:
                retry_after = max(1, math.ceil(self._timestamps[0] + self.window_seconds - now))
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit: max {self.max_requests} notifications "
                    f"per {self.window_seconds:.0f}s. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            self._timestamps.append(now)


rate_limiter = RateLimiter(max_requests=10, window_seconds=10.0)


# ─── Retry configuration ───────────────────────────────────────────────────

MAX_RETRIES = 1
RETRY_DELAY_S = 2.0


# ─── Notification history (in-memory, last N entries) ──────────────────────

MAX_HISTORY = 50
notification_history: deque[dict] = deque(maxlen=MAX_HISTORY)


# ─── App lifespan (startup / shutdown) ──────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared HTTP client and run startup checks before accepting requests."""
    global http_client, STARTED_AT
    STARTED_AT = time.monotonic()
    http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    try:
        if ALEXA_CLIENT_ID and ALEXA_CLIENT_SECRET:
            try:
                await get_access_token()
                logger.info(
                    "Startup check passed: Amazon credentials are valid."
                )
            except Exception as exc:
                logger.error(
                    "Startup check FAILED: could not authenticate with Amazon. "
                    "Verify ALEXA_CLIENT_ID and ALEXA_CLIENT_SECRET in your .env file. "
                    "Error: %s",
                    exc,
                )
        else:
            logger.error(
                "ALEXA_CLIENT_ID and/or ALEXA_CLIENT_SECRET not set in .env. "
                "The bridge will NOT be able to send notifications."
            )
        yield
    finally:
        if http_client is not None and not http_client.is_closed:
            await http_client.aclose()
        http_client = None


# ─── FastAPI app ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Alexa Notify Bridge",
    docs_url=None,   # Disable Swagger UI in production
    redoc_url=None,  # Disable ReDoc in production
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors clearly so they are visible in Docker logs."""
    # Strip pydantic's 'ctx' which may contain non-serializable exception objects
    errors = [
        {k: v for k, v in err.items() if k != "ctx"} for err in exc.errors()
    ]
    logger.error("Request validation failed: %s", errors)
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(errors)},
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Health-check endpoint for monitoring and Docker HEALTHCHECK."""
    return {"status": "ok"}


@app.get("/status")
async def status(_api_key: str = Depends(verify_api_key)):
    """Return bridge configuration and Amazon token status (protected by API_KEY if set)."""
    now = time.monotonic()
    async with token_cache._lock:
        token_valid = bool(token_cache.token and token_cache.expires_at > now)
        token_expires_in = round(token_cache.expires_at - now) if token_valid else 0

    return {
        "status": "ok",
        "region": API_REGION,
        "credentials_configured": bool(ALEXA_CLIENT_ID and ALEXA_CLIENT_SECRET),
        "api_key_enabled": bool(API_KEY),
        "token_valid": token_valid,
        "token_expires_in_seconds": token_expires_in,
        "default_expiry_hours": round(DEFAULT_EXPIRY_HOURS, 2),
        "debounce_seconds": DEBOUNCE_SECONDS,
        "history_count": len(notification_history),
        "uptime_seconds": round(now - STARTED_AT),
    }


@app.get("/history")
async def get_history(
    limit: int = 50,
    _api_key: str = Depends(verify_api_key),
):
    """Return the last notifications sent (most recent first, in-memory only)."""
    safe_limit = max(1, min(limit, MAX_HISTORY))
    items = list(notification_history)[:safe_limit]
    return {
        "count": len(items),
        "total": len(notification_history),
        "notifications": items,
    }


@app.post("/notify")
async def notify(
    request: NotificationRequest,
    _api_key: str = Depends(verify_api_key),
):
    """Receive a local request and forward it as a proactive event to Alexa."""
    raw_text = request.creator_name.strip()
    if not raw_text:
        raise HTTPException(
            status_code=422,
            detail="Message ('creator_name' or 'message') cannot be empty or whitespace only.",
        )

    message_text, is_truncated = process_message_text(raw_text)

    # Check debounce filter before rate limiter
    effective_debounce = (
        request.debounce_seconds
        if request.debounce_seconds is not None
        else DEBOUNCE_SECONDS
    )
    if await debounce_filter.is_duplicate(message_text, effective_debounce):
        logger.info(
            "Debounced duplicate notification within %.1fs: '%s'",
            effective_debounce,
            message_text,
        )
        return {
            "status": "ignored",
            "debounced": True,
            "message": "Duplicate notification ignored (debounced)",
        }

    try:
        # Check rate limit before doing any work
        await rate_limiter.check()

        token = await get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Build ISO 8601 timestamps
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        raw_hours = request.expiry_hours if request.expiry_hours is not None else DEFAULT_EXPIRY_HOURS
        hours = clamp_expiry_hours(raw_hours)
        if request.expiry_hours is not None and hours != raw_hours:
            adjusted_desc = (
                "5 minutes (minimum allowed)"
                if hours == MIN_EXPIRY_HOURS
                else "24 hours (maximum allowed)"
            )
            logger.warning(
                "Notification expiry of %s hours is outside Amazon's limits (5 min to 24h). Adjusted to %s.",
                raw_hours,
                adjusted_desc,
            )
        expiry_dt = now + timedelta(hours=hours)
        expiry = expiry_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{expiry_dt.microsecond // 1000:03d}Z"

        reference_id = str(uuid.uuid4())

        event_payload = {
            "timestamp": timestamp,
            "referenceId": reference_id,
            "expiryTime": expiry,
            "event": {
                "name": "AMAZON.MessageAlert.Activated",
                "payload": {
                    "state": {
                        "status": "UNREAD",
                        "freshness": "NEW",
                    },
                    "messageGroup": {
                        "creator": {
                            "name": message_text,
                        },
                        "count": 1,
                        "urgency": request.urgency,
                    },
                },
            },
            "relevantAudience": {
                "type": "Multicast",
                "payload": {},
            },
        }

        client = get_http_client()
        for attempt in range(1 + MAX_RETRIES):
            try:
                response = await client.post(
                    PROACTIVE_EVENTS_URL, headers=headers, json=event_payload
                )
                response.raise_for_status()
                break  # Success — exit retry loop
            except httpx.HTTPStatusError as exc:
                upstream_status = exc.response.status_code
                if upstream_status == 401 and attempt < MAX_RETRIES:
                    logger.warning(
                        "Amazon access token rejected (401), refreshing token and retrying..."
                    )
                    token = await get_access_token(force_refresh=True, failed_token=token)
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                if upstream_status >= 500 and attempt < MAX_RETRIES:
                    logger.warning(
                        "Amazon API error (%s), retrying in %.0fs...",
                        upstream_status,
                        RETRY_DELAY_S,
                    )
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue

                if upstream_status == 403:
                    logger.error(
                        "Alexa API returned 403 Forbidden: %s. "
                        "Make sure the skill is enabled in the Alexa app and Notifications permission is granted.",
                        exc.response.text,
                    )
                elif upstream_status == 432:
                    logger.error(
                        "Alexa API returned 432 (daily proactive notification quota exceeded): %s",
                        exc.response.text,
                    )
                else:
                    logger.error(
                        "Alexa API rejected the request (%s): %s",
                        upstream_status,
                        exc.response.text,
                    )
                raise HTTPException(
                    status_code=502,
                    detail=f"Amazon Alexa API error (HTTP {upstream_status}). Check server logs for details.",
                )
            except httpx.TimeoutException as exc:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "Timeout sending proactive event, retrying in %.0fs: %s",
                        RETRY_DELAY_S,
                        exc,
                    )
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue
                logger.error("Timeout sending proactive event: %s", exc)
                raise HTTPException(
                    status_code=504,
                    detail="Timeout sending proactive event to Amazon Alexa API.",
                )
            except httpx.HTTPError as exc:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "Network error, retrying in %.0fs: %s",
                        RETRY_DELAY_S,
                        exc,
                    )
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue
                logger.error("Network error sending proactive event: %s", exc)
                raise HTTPException(
                    status_code=502,
                    detail="Failed to communicate with Amazon Alexa API. Check server logs for details.",
                )
    except Exception:
        if effective_debounce > 0:
            await debounce_filter.remove(message_text)
        raise

    # Store in history (most recent first)
    history_entry = {
        "timestamp": timestamp,
        "message": message_text,
        "expiry_hours": round(hours, 2),
        "reference_id": reference_id,
    }
    if is_truncated:
        history_entry["truncated"] = True
    notification_history.appendleft(history_entry)

    logger.info("Notification sent: %s", message_text)
    response_data = {
        "status": "success",
        "message": "Notification sent successfully",
        "reference_id": reference_id,
        "expiry_hours": round(hours, 2),
    }
    if is_truncated:
        response_data["truncated"] = True
    return response_data
