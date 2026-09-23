"""
CryptoIntel Risk Correlation Engine

Combines multiple risk results that belong to the same
transaction or address within a short time window.

Purpose:
    Individual detections may have separate risk scores.
    This engine correlates them into a combined risk result
    before sending the result to the Alert Engine.

Example:

    LARGE TRANSFER       = 30
    HIGH VALUE           = 40

    Combined Risk        = 70
    Risk Level           = HIGH
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


# Maximum number of correlated groups kept in memory.
MAX_GROUPS = 500

# Correlation window.
# Results for the same transaction/address inside this
# window can be combined.
CORRELATION_WINDOW_SECONDS = 60


# -------------------------------------------------------------------
# STORAGE
# -------------------------------------------------------------------

CORRELATION_GROUPS: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=20)
)

CORRELATED_RESULTS: deque[dict[str, Any]] = deque(
    maxlen=MAX_GROUPS
)

CORRELATION_EVENTS = 0
CORRELATIONS_CREATED = 0


# -------------------------------------------------------------------
# TIME
# -------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: Any) -> float:
    """
    Convert ISO timestamp to Unix timestamp.

    Falls back to current time when the supplied timestamp
    cannot be parsed.
    """

    if not value:
        return datetime.now(timezone.utc).timestamp()

    try:
        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.timestamp()

    except Exception:
        return datetime.now(timezone.utc).timestamp()


# -------------------------------------------------------------------
# CORRELATION KEY
# -------------------------------------------------------------------

def build_correlation_key(
    risk_result: dict[str, Any],
) -> str:
    """
    Build a stable correlation key.

    Priority:

    1. Network + transaction hash
    2. Network + address

    This prevents unrelated networks from being mixed.
    """

    network = str(
        risk_result.get("network") or "UNKNOWN"
    ).strip().lower()

    txid = str(
        risk_result.get("txid") or ""
    ).strip().lower()

    address = str(
        risk_result.get("address") or ""
    ).strip().lower()

    if txid:
        return f"tx:{network}:{txid}"

    if address:
        return f"address:{network}:{address}"

    return (
        f"event:{network}:"
        f"{risk_result.get('detection_type', 'UNKNOWN')}"
    )


# -------------------------------------------------------------------
# RISK LEVEL
# -------------------------------------------------------------------

def calculate_risk_level(score: int) -> str:
    """
    Convert combined risk score into a risk level.
    """

    score = max(0, min(int(score), 100))

    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


# -------------------------------------------------------------------
# INDICATOR DEDUPLICATION
# -------------------------------------------------------------------

def indicator_signature(
    indicator: Any,
) -> str:
    """
    Create a simple signature so identical indicators
    are not counted repeatedly.
    """

    if not isinstance(indicator, dict):
        return str(indicator)

    detection_type = str(
        indicator.get("detection_type")
        or indicator.get("type")
        or ""
    ).strip().upper()

    reason = str(
        indicator.get("reason")
        or ""
    ).strip().lower()

    return f"{detection_type}:{reason}"


def merge_indicators(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge indicators while avoiding exact duplicates.
    """

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for result in results:

        indicators = result.get("indicators", [])

        if not isinstance(indicators, list):
            continue

        for indicator in indicators:

            signature = indicator_signature(indicator)

            if signature in seen:
                continue

            seen.add(signature)

            if isinstance(indicator, dict):
                merged.append(dict(indicator))
            else:
                merged.append(
                    {
                        "reason": str(indicator)
                    }
                )

    return merged


# -------------------------------------------------------------------
# COMBINED SCORE
# -------------------------------------------------------------------

def calculate_combined_score(
    results: list[dict[str, Any]],
) -> int:
    """
    Combine independent risk scores.

    Important:
    The same detection type is counted only once.

    Example:

        LARGE TRANSFER = 30
        HIGH VALUE     = 40

        Combined = 70
    """

    total = 0
    counted_types: set[str] = set()

    for result in results:

        detection_type = str(
            result.get("detection_type")
            or "UNKNOWN"
        ).strip().upper()

        if detection_type in counted_types:
            continue

        counted_types.add(detection_type)

        try:
            score = int(
                result.get("risk_score", 0)
            )
        except Exception:
            score = 0

        total += max(0, score)

    return min(total, 100)


# -------------------------------------------------------------------
# CORRELATION
# -------------------------------------------------------------------

async def correlate_risk_result(
    risk_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Add a new risk result to its correlation group.

    Returns a combined risk result when correlation
    contains multiple meaningful signals.
    """

    global CORRELATION_EVENTS
    global CORRELATIONS_CREATED

    if not isinstance(risk_result, dict):
        return None

    CORRELATION_EVENTS += 1

    key = build_correlation_key(risk_result)

    now = datetime.now(timezone.utc).timestamp()

    group = CORRELATION_GROUPS[key]

    # ---------------------------------------------------------------
    # Remove expired entries
    # ---------------------------------------------------------------

    while group:

        oldest = group[0]

        oldest_time = parse_timestamp(
            oldest.get("analyzed_at")
            or oldest.get("created_at")
        )

        if now - oldest_time <= CORRELATION_WINDOW_SECONDS:
            break

        group.popleft()

    # ---------------------------------------------------------------
    # Add current result
    # ---------------------------------------------------------------

    group.append(dict(risk_result))

    # ---------------------------------------------------------------
    # Need at least two different risk signals
    # ---------------------------------------------------------------

    unique_types = {
        str(
            item.get("detection_type")
            or "UNKNOWN"
        ).strip().upper()
        for item in group
    }

    if len(unique_types) < 2:
        return None

    results = list(group)

    # ---------------------------------------------------------------
    # Calculate combined score
    # ---------------------------------------------------------------

    combined_score = calculate_combined_score(
        results
    )

    combined_level = calculate_risk_level(
        combined_score
    )

    # ---------------------------------------------------------------
    # Merge indicators
    # ---------------------------------------------------------------

    indicators = merge_indicators(
        results
    )

    detection_types = sorted(
        unique_types
    )

    # ---------------------------------------------------------------
    # Build combined result
    # ---------------------------------------------------------------

    combined_result = {
        "correlation_id": (
            f"CORR-{abs(hash(key))}"
        ),
        "correlation_key": key,
        "status": "CORRELATED",

        "risk_score": combined_score,
        "risk_level": combined_level,

        "network": risk_result.get(
            "network"
        ),

        "asset": risk_result.get(
            "asset"
        ),

        "address": risk_result.get(
            "address"
        ),

        "txid": risk_result.get(
            "txid"
        ),

        "block": risk_result.get(
            "block"
        ),

        "detection_type": (
            "CORRELATED RISK"
        ),

        "detection_types": detection_types,

        "indicator_count": len(
            indicators
        ),

        "indicators": indicators,

        "correlated_events": len(
            results
        ),

        "reason": (
            "Multiple risk indicators "
            "were correlated within the "
            f"{CORRELATION_WINDOW_SECONDS}-second "
            "correlation window."
        ),

        "correlated_at": utc_now(),

        "source": (
            "CryptoIntel Risk "
            "Correlation Engine"
        ),
    }

    CORRELATED_RESULTS.appendleft(
        combined_result
    )

    CORRELATIONS_CREATED += 1

    return combined_result


# -------------------------------------------------------------------
# LATEST RESULTS
# -------------------------------------------------------------------

def latest_correlations(
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Return latest correlated risk results.
    """

    limit = max(
        1,
        min(int(limit), MAX_GROUPS)
    )

    return list(
        CORRELATED_RESULTS
    )[:limit]


# -------------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------------

def health() -> dict[str, Any]:
    """
    Return Risk Correlation Engine health.
    """

    return {
        "status": "RUNNING",
        "engine": (
            "CryptoIntel Risk "
            "Correlation Engine"
        ),
        "events_received": CORRELATION_EVENTS,
        "correlations_created": CORRELATIONS_CREATED,
        "stored_correlations": len(
            CORRELATED_RESULTS
        ),
        "active_groups": len(
            CORRELATION_GROUPS
        ),
        "correlation_window_seconds": (
            CORRELATION_WINDOW_SECONDS
        ),
        "max_groups": MAX_GROUPS,
    }


# -------------------------------------------------------------------
# CLEAR
# -------------------------------------------------------------------

def clear_correlations() -> None:
    """
    Clear in-memory correlation state.

    Useful for development/testing.
    """

    global CORRELATION_EVENTS
    global CORRELATIONS_CREATED

    CORRELATION_GROUPS.clear()
    CORRELATED_RESULTS.clear()

    CORRELATION_EVENTS = 0
    CORRELATIONS_CREATED = 0