"""
core/network.py — Resilient HTTP networking with timeouts and exponential backoff.
"""
from __future__ import annotations

import time
from typing import Any, Optional
import requests

from core.logger import get_logger

logger = get_logger("network")

DEFAULT_TIMEOUT = 12.0  # seconds
MAX_RETRIES = 3
BACKOFF_BASE = 1.5      # seconds


def http_get(
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    backoff: float = BACKOFF_BASE,
) -> Optional[requests.Response]:
    """Execute GET request with exponential backoff on transient errors."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code < 500:
                return resp
            logger.warning(f"HTTP GET {url} returned status {resp.status_code} (attempt {attempt}/{retries})")
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"HTTP GET {url} failed: {e} (attempt {attempt}/{retries})")
        except Exception as e:
            logger.error(f"Unexpected HTTP GET error for {url}: {e}")
            return None

        if attempt < retries:
            sleep_time = backoff ** attempt
            time.sleep(sleep_time)

    return None


def http_post(
    url: str,
    data: Any = None,
    json: Any = None,
    headers: Optional[dict] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    backoff: float = BACKOFF_BASE,
) -> Optional[requests.Response]:
    """Execute POST request with exponential backoff on transient errors."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, data=data, json=json, headers=headers, timeout=timeout)
            if resp.status_code < 500:
                return resp
            logger.warning(f"HTTP POST {url} returned status {resp.status_code} (attempt {attempt}/{retries})")
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"HTTP POST {url} failed: {e} (attempt {attempt}/{retries})")
        except Exception as e:
            logger.error(f"Unexpected HTTP POST error for {url}: {e}")
            return None

        if attempt < retries:
            sleep_time = backoff ** attempt
            time.sleep(sleep_time)

    return None


def is_connected(test_host: str = "https://www.google.com", timeout: float = 3.0) -> bool:
    """Quick check for Internet connectivity."""
    try:
        r = requests.head(test_host, timeout=timeout)
        return r.status_code < 400
    except Exception:
        return False

