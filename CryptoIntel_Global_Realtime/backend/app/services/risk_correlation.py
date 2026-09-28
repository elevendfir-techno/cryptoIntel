"""
CryptoIntel Risk Correlation Engine

Combines multiple independent risk results that belong to the same
transaction or address within a short time window.

Purpose:
    Individual detections may have separate risk scores.
    This engine correlates different detection types into one
    combined risk result before sending it to the Alert Engine.

Example:

    LARGE TRANSFER       = 30
    HIGH VALUE TRANSACTION = 40

    Combined Risk        = 70
    Risk Level           = HIGH

Duplicate protection:
    The same detection type is NOT added repeatedly inside the
    active correlation window.

    A correlated result is created only when a NEW detection type
    appears for the same transaction/address.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------

# Maximum number of correlation groups kept in memory.
MAX_GROUPS = 500

# Results belonging to the same transaction/address are correlated
# only inside this time window.
CORRELATION_WINDOW_SECONDS = 60


# -------------------------------------------------------------------
# STORAGE
# -------------------------------------------------------------------

# Each transaction/address gets its own correlation group.
#
# Example:
#
# tx:ethereum:0x123...
#     ├── LARGE TRANSFER
#     └── HIGH VALUE TRANSACTION
#
CORRELATION_GROUPS: dict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=20)
)


# Latest combined correlation results.
CORRELATED_RESULTS: deque[dict[str, Any]] = deque(
    maxlen=MAX_GROUPS
)


# Runtime counters.
CORRELATION_EVENTS = 0
CORRELATIONS_CREATED = 0


# -------------------------------------------------------------------
# TIME
# -------------------------------------------------------------------

def utc_now() -> str:
    """
    Return current UTC time as ISO-8601 string.
    """

    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: Any) -> float:
    """
    Convert an ISO timestamp into Unix timestamp.

    If the timestamp is missing or invalid, current UTC time
    is used as a safe fallback.
    """

    if not value:
        return datetime.now(timezone.utc).timestamp()

    try:
        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

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
        3. Network + detection type

    This prevents unrelated networks or entities from being
    mixed together.
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

    detection_type = normalize_detection_type(
        risk_result
    )

    return (
        f"event:{network}:{detection_type}"
    )


# -------------------------------------------------------------------
# RISK LEVEL
# -------------------------------------------------------------------

def calculate_risk_level(
    score: int,
) -> str:
    """
    Convert a risk score into a risk level.

        80-100 = CRITICAL
        60-79  = HIGH
        30-59  = MEDIUM
        0-29   = LOW
    """

    try:
        score = int(score)
    except Exception:
        score = 0

    score = max(
        0,
        min(score, 100)
    )

    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"


# -------------------------------------------------------------------
# DETECTION TYPE
# -------------------------------------------------------------------

def normalize_detection_type(
    result: dict[str, Any],
) -> str:
    """
    Return a normalized detection type.

    Example:

        "large transfer"
        "LARGE TRANSFER"
        " Large Transfer "

    all become:

        "LARGE TRANSFER"
    """

    return str(
        result.get("detection_type")
        or "UNKNOWN"
    ).strip().upper()


# -------------------------------------------------------------------
# INDICATOR SIGNATURE
# -------------------------------------------------------------------

def indicator_signature(
    indicator: Any,
) -> str:
    """
    Create a stable signature for an indicator.

    This prevents identical indicators from being merged
    multiple times.
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

    return (
        f"{detection_type}:{reason}"
    )


# -------------------------------------------------------------------
# MERGE INDICATORS
# -------------------------------------------------------------------

def merge_indicators(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge indicators from all correlated results.

    Exact duplicate indicators are removed.
    """

    merged: list[dict[str, Any]] = []

    seen: set[str] = set()

    for result in results:

        indicators = result.get(
            "indicators",
            []
        )

        if not isinstance(
            indicators,
            list,
        ):
            continue

        for indicator in indicators:

            signature = indicator_signature(
                indicator
            )

            if signature in seen:
                continue

            seen.add(signature)

            if isinstance(
                indicator,
                dict,
            ):
                merged.append(
                    dict(indicator)
                )

            else:
                merged.append(
                    {
                        "reason": str(
                            indicator
                        )
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
    Combine risk scores from different detection types.

    IMPORTANT:

    The same detection type is counted only once.

    Example:

        LARGE TRANSFER = 30
        HIGH VALUE     = 40

        Combined       = 70

    If the same detection arrives multiple times:

        LARGE TRANSFER = 30
        LARGE TRANSFER = 30

    it is counted only once:

        Combined       = 30
    """

    total = 0

    counted_types: set[str] = set()

    for result in results:

        detection_type = normalize_detection_type(
            result
        )

        if detection_type in counted_types:
            continue

        counted_types.add(
            detection_type
        )

        try:
            score = int(
                result.get(
                    "risk_score",
                    0,
                )
            )

        except Exception:
            score = 0

        total += max(
            0,
            score,
        )

    return min(
        total,
        100,
    )


# -------------------------------------------------------------------
# CORRELATION
# -------------------------------------------------------------------

async def correlate_risk_result(
    risk_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Correlate a new risk result.

    Behaviour:

        1. Find the transaction/address group.
        2. Remove expired results.
        3. Check whether this detection type already exists.
        4. Ignore repeated detection types.
        5. Add only NEW detection types.
        6. Require at least two different detection types.
        7. Calculate combined score.
        8. Create a correlated result.
        9. Store and return it.

    This allows real combinations such as:

        LARGE TRANSFER + HIGH VALUE TRANSACTION
        = 30 + 40
        = 70 HIGH
    """

    global CORRELATION_EVENTS
    global CORRELATIONS_CREATED

    if not isinstance(
        risk_result,
        dict,
    ):
        return None

    CORRELATION_EVENTS += 1

    # ---------------------------------------------------------------
    # Build correlation key
    # ---------------------------------------------------------------

    key = build_correlation_key(
        risk_result
    )

    now = datetime.now(
        timezone.utc
    ).timestamp()

    group = CORRELATION_GROUPS[key]

    # ---------------------------------------------------------------
    # Remove expired entries
    # ---------------------------------------------------------------

    while group:

        oldest = group[0]

        oldest_time = parse_timestamp(
            oldest.get("analyzed_at")
            or oldest.get("created_at")
            or oldest.get("timestamp")
        )

        if (
            now - oldest_time
            <= CORRELATION_WINDOW_SECONDS
        ):
            break

        group.popleft()

    # ---------------------------------------------------------------
    # Current detection type
    # ---------------------------------------------------------------

    current_type = normalize_detection_type(
        risk_result
    )

    # ---------------------------------------------------------------
    # Existing detection types
    # ---------------------------------------------------------------

    previous_types = {
        normalize_detection_type(item)
        for item in group
    }

    # ---------------------------------------------------------------
    # DUPLICATE DETECTION PROTECTION
    # ---------------------------------------------------------------

    if current_type in previous_types:

        # IMPORTANT:
        #
        # Do NOT append the duplicate event.
        #
        # Keeping repeated events here would unnecessarily fill
        # the correlation group and could make correlated_events
        # misleading.
        #
        # The original detection has already been recorded.
        return None

    # ---------------------------------------------------------------
    # Add NEW detection type
    # ---------------------------------------------------------------

    group.append(
        dict(risk_result)
    )

    # ---------------------------------------------------------------
    # Need at least two different risk signals
    # ---------------------------------------------------------------

    unique_types = {
        normalize_detection_type(item)
        for item in group
    }

    if len(unique_types) < 2:
        return None

    # ---------------------------------------------------------------
    # Build results used for correlation
    # ---------------------------------------------------------------

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
    # Get stable identifiers
    # ---------------------------------------------------------------

    network = risk_result.get(
        "network"
    )

    asset = risk_result.get(
        "asset"
    )

    address = risk_result.get(
        "address"
    )

    txid = risk_result.get(
        "txid"
    )

    block = risk_result.get(
        "block"
    )

    # ---------------------------------------------------------------
    # Build correlation ID
    # ---------------------------------------------------------------

    correlation_id = (
        f"CORR-{abs(hash(key))}"
    )

    # ---------------------------------------------------------------
    # Build combined result
    # ---------------------------------------------------------------

    combined_result = {

        "correlation_id": correlation_id,

        "correlation_key": key,

        "status": "CORRELATED",

        "risk_score": combined_score,

        "risk_level": combined_level,

        "network": network,

        "asset": asset,

        "address": address,

        "txid": txid,

        "block": block,

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
            "Multiple independent risk "
            "indicators were correlated "
            "within the "
            f"{CORRELATION_WINDOW_SECONDS}-second "
            "correlation window."
        ),

        "correlated_at": utc_now(),

        "source": (
            "CryptoIntel Risk "
            "Correlation Engine"
        ),
    }

    # ---------------------------------------------------------------
    # Store latest correlated result
    # ---------------------------------------------------------------

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
    Return the latest correlated risk results.
    """

    try:
        limit = int(limit)

    except Exception:
        limit = 100

    limit = max(
        1,
        min(
            limit,
            MAX_GROUPS,
        ),
    )

    return list(
        CORRELATED_RESULTS
    )[:limit]


# -------------------------------------------------------------------
# HEALTH
# -------------------------------------------------------------------

def health() -> dict[str, Any]:
    """
    Return Risk Correlation Engine health information.
    """

    return {

        "status": "RUNNING",

        "engine": (
            "CryptoIntel Risk "
            "Correlation Engine"
        ),

        "events_received": (
            CORRELATION_EVENTS
        ),

        "correlations_created": (
            CORRELATIONS_CREATED
        ),

        "stored_correlations": (
            len(CORRELATED_RESULTS)
        ),

        "active_groups": (
            len(CORRELATION_GROUPS)
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
    Clear all in-memory correlation state.

    Useful for development/testing or after changing
    correlation logic.
    """

    global CORRELATION_EVENTS
    global CORRELATIONS_CREATED

    CORRELATION_GROUPS.clear()

    CORRELATED_RESULTS.clear()

    CORRELATION_EVENTS = 0

    CORRELATIONS_CREATED = 0