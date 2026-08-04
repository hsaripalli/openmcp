"""
OpenMCP Canada — Anonymous Usage Telemetry & Observability Module

Sends high-level, anonymous usage events to a database endpoint (e.g., Supabase,
PostgREST, Firebase, or a custom HTTP collector) in a non-blocking background thread.

Privacy Guarantee:
    - NO raw questions, search queries, SQL, filters, or complete URLs
    - NO full error messages, local file paths, or resource contents
    - ONLY a temporary session ID, tool name, success/failure status,
      normalized error code, latency, server version, and a unique list of
      public dataset IDs when available.

Opt-In:
    Set environment variable `OPENDATA_FYI_TELEMETRY_ENABLED=true`.
    Telemetry is disabled unless explicitly enabled.
"""

import os
import sys
import time
import uuid
import logging
import functools
import concurrent.futures
import hashlib
import threading
from typing import Any, Callable, Dict, Optional
import re
import inspect
import requests

from version import __version__

logger = logging.getLogger("openmcp.telemetry")

# Default public collector endpoint (Supabase REST, insert-only via RLS).
# The anon key below is a *publishable* key: it can only INSERT telemetry rows,
# never read/update/delete (enforced by row-level security). Override with
# TELEMETRY_DB_URL / TELEMETRY_DB_KEY after opting in (see module docstring).
DEFAULT_TELEMETRY_URL = "https://oqeeqakubthktgzuschb.supabase.co/rest/v1/telemetry_events"
DEFAULT_TELEMETRY_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xZWVxYWt1YnRoa3RnenVzY2hiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ3NTk2NTcsImV4cCI6MjEwMDMzNTY1N30."
    "R6yZFuvApZY8--RLBZU8U76pPmD_LeKVSURL5F-lZK8"
)

# Generate a single random session ID per server process run (non-identifiable)
SESSION_ID = str(uuid.uuid4())
SERVER_VERSION = __version__

# Background thread pool worker (max 2 threads, fast daemon)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="TelemetryWorker")
_resource_dataset_map: Dict[str, str] = {}
_resource_dataset_lock = threading.Lock()


def is_telemetry_disabled() -> bool:
    """Telemetry is off by default and runs only after explicit opt-in."""
    enabled_var = os.environ.get(
        "OPENDATA_FYI_TELEMETRY_ENABLED", ""
    ).strip().lower()
    legacy_enabled_var = os.environ.get(
        "OPENMCP_TELEMETRY_ENABLED", ""
    ).strip().lower()
    disabled_var = os.environ.get("OPENMCP_TELEMETRY_DISABLED", "").strip().lower()
    legacy_var = os.environ.get("DISABLE_TELEMETRY", "").strip().lower()
    truthy = ("1", "true", "yes")
    explicitly_enabled = (
        enabled_var in truthy or legacy_enabled_var in truthy
    )
    explicitly_disabled = disabled_var in truthy or legacy_var in truthy
    return not explicitly_enabled or explicitly_disabled


def _post_event_task(endpoint_url: str, api_key: Optional[str], payload: Dict[str, Any]) -> None:
    """Internal worker function to post telemetry event to Supabase / REST endpoint."""
    headers = {
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    if api_key:
        headers["apikey"] = api_key
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.post(endpoint_url, json=payload, headers=headers, timeout=3.0)
        if resp.status_code not in (200, 201, 204):
            logger.debug(f"Telemetry HTTP status {resp.status_code}: {resp.text}")
    except Exception as err:
        logger.debug(f"Telemetry post failed (silently caught): {err}")


def record_telemetry_event(
    tool_name: str,
    dataset_ids: Optional[list[Any]] = None,
    latency_ms: Optional[float] = None,
    status: str = "success",
    error_code: Optional[str] = None,
) -> None:
    """
    Queue an anonymous telemetry event to be posted in a background thread.
    Does nothing if telemetry is disabled or if TELEMETRY_DB_URL is unset.
    """
    if is_telemetry_disabled():
        return

    endpoint_url = os.environ.get("TELEMETRY_DB_URL", "").strip() or DEFAULT_TELEMETRY_URL
    api_key = os.environ.get("TELEMETRY_DB_KEY", "").strip() or DEFAULT_TELEMETRY_KEY

    payload = {
        "session_id": SESSION_ID,
        "tool_name": tool_name,
        "status": "error" if status == "error" else "success",
        "error_code": str(error_code)[:100] if error_code else None,
        "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
        "server_version": SERVER_VERSION,
        "dataset_ids": _normalize_dataset_ids(dataset_ids or []),
    }

    # Dispatch to background thread pool (non-blocking)
    try:
        _executor.submit(_post_event_task, endpoint_url, api_key, payload)
    except Exception as e:
        logger.debug(f"Could not submit telemetry task: {e}")


def _normalize_dataset_id(value: Any) -> Optional[str]:
    """Return a safe public dataset identifier, never a complete URL."""
    if value is None:
        return None
    text = str(value)
    url_match = re.search(r"/dataset/([0-9a-z_-]{1,100})", text, re.IGNORECASE)
    if url_match:
        return url_match.group(1)
    if re.fullmatch(r"[0-9a-z_-]{1,30}:[0-9a-z_-]{1,120}", text, re.IGNORECASE):
        return text.lower()
    if re.fullmatch(r"[0-9a-z_-]{1,120}", text, re.IGNORECASE):
        return text
    return None


def _normalize_dataset_ids(values: list[Any]) -> list[str]:
    """Return at most 25 unique, safe public dataset identifiers."""
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        dataset_id = _normalize_dataset_id(value)
        if not dataset_id or dataset_id in seen:
            continue
        seen.add(dataset_id)
        normalized.append(dataset_id)
        if len(normalized) == 25:
            break
    return normalized


def _dataset_ids_from_result(result: Any) -> list[str]:
    """Extract public dataset IDs from a tool result without retaining its text."""
    if isinstance(result, str):
        return _normalize_dataset_ids(
            re.findall(r"/dataset/([0-9a-z_-]{1,100})", result, re.IGNORECASE)
        )

    structured = getattr(result, "structuredContent", None)
    if not isinstance(structured, dict):
        return []
    candidates = []
    for dataset in structured.get("datasets", []):
        if isinstance(dataset, dict):
            candidates.append(dataset.get("id"))
    for source in structured.get("sources", []):
        if isinstance(source, dict):
            candidates.append(source.get("dataset_id"))
    return _normalize_dataset_ids(candidates)


def _structured_error_code(result: Any) -> Optional[str]:
    """Return a stable code when a structured MCP tool result represents an error."""
    structured = getattr(result, "structuredContent", None)
    if not isinstance(structured, dict):
        return None
    error = structured.get("error")
    if isinstance(error, dict) and error.get("code"):
        return str(error["code"])[:100]
    if getattr(result, "isError", False):
        return "ToolReturnedError"
    return None


def _resource_key(value: Any) -> Optional[str]:
    """Create an in-memory lookup key without retaining a resource ID or URL."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def register_dataset_resources(dataset_id: Any, resources: list[dict]) -> None:
    """Associate resource IDs and URLs with a public dataset for this process run."""
    normalized_dataset_id = _normalize_dataset_id(dataset_id)
    if not normalized_dataset_id:
        return

    associations: Dict[str, str] = {}
    for resource in resources:
        for field in ("id", "url"):
            key = _resource_key(resource.get(field))
            if key:
                associations[key] = normalized_dataset_id

    if associations:
        with _resource_dataset_lock:
            _resource_dataset_map.update(associations)


def _dataset_id_for_resource(value: Any) -> Optional[str]:
    """Resolve a resource locally without transmitting its ID or complete URL."""
    key = _resource_key(value)
    if key:
        with _resource_dataset_lock:
            dataset_id = _resource_dataset_map.get(key)
        if dataset_id:
            return dataset_id

    if isinstance(value, str):
        match = re.search(r"/dataset/([0-9a-z_-]{1,100})", value, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_dataset_id(func: Callable, args: tuple, kwargs: dict) -> Optional[str]:
    """Extract only a public dataset identifier from a wrapped tool call."""
    bound_map: Dict[str, Any] = {}
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        bound_map = bound.arguments
    except Exception:
        bound_map = kwargs.copy()
        if args and isinstance(args[0], str):
            bound_map["_arg0"] = args[0]

    dataset_id = bound_map.get("dataset_id") or bound_map.get("id")
    if dataset_id:
        return _normalize_dataset_id(dataset_id)

    for key in ("resource_id", "file_url", "url", "_arg0"):
        resolved_dataset_id = _dataset_id_for_resource(bound_map.get(key))
        if resolved_dataset_id:
            return resolved_dataset_id
    return None


def log_telemetry(tool_name: str) -> Callable:
    """
    Decorator for FastMCP tool functions to automatically log telemetry and latency.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()
            error_code = None
            status = "success"
            input_dataset_id = _extract_dataset_id(func, args, kwargs)
            dataset_ids = [input_dataset_id] if input_dataset_id else []

            try:
                result = func(*args, **kwargs)
                dataset_ids = _normalize_dataset_ids(
                    dataset_ids + _dataset_ids_from_result(result)
                )
                if isinstance(result, str):
                    normalized_result = result.lstrip()
                    if normalized_result.startswith("Error"):
                        status = "error"
                        error_code = "ToolReturnedError"
                    elif normalized_result.startswith("Query timed out"):
                        status = "error"
                        error_code = "TimeoutError"
                else:
                    structured_error_code = _structured_error_code(result)
                    if structured_error_code:
                        status = "error"
                        error_code = structured_error_code
                return result
            except Exception as ex:
                status = "error"
                error_code = type(ex).__name__
                raise ex
            finally:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                record_telemetry_event(
                    tool_name=tool_name,
                    dataset_ids=dataset_ids,
                    latency_ms=elapsed_ms,
                    status=status,
                    error_code=error_code,
                )

        return wrapper
    return decorator
