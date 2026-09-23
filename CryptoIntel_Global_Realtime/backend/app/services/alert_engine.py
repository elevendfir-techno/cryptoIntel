"""
CryptoIntel Alert Engine

Converts Risk Analysis results into investigator-facing alerts.

Alerts are analytical notifications.
They do NOT automatically declare fraud or criminal activity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.state import state


# ============================================================
# CONFIGURATION
# ============================================================

MAX_ALERTS = 300

# Risk score at or above this value creates an alert.
ALERT_RISK_SCORE_THRESHOLD = 60


# ============================================================
# STORAGE / METRICS
# ============================================================

ALERTS_CREATED = 0
ALERTS_SUPPRESSED = 0


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def generate_alert_id() -> str:
    return f"ALT-{uuid4().hex[:12].upper()}"


def normalize_severity(
    risk_level: Any,
) -> str:

    level = str(
        risk_level or ""
    ).upper()

    if level in {
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
    }:
        return level

    return "LOW"


# ============================================================
# ALERT CREATION
# ============================================================

async def create_alert(
    risk_result: dict[str, Any],
) -> dict[str, Any]:

    global ALERTS_CREATED

    risk_score = int(
        risk_result.get(
            "risk_score",
            0,
        )
    )

    risk_level = normalize_severity(
        risk_result.get(
            "risk_level",
        )
    )

    indicators = risk_result.get(
        "indicators",
        [],
    )

    detection_type = risk_result.get(
        "detection_type",
        "UNKNOWN",
    )

    # --------------------------------------------------------
    # Human-readable reason
    # --------------------------------------------------------

    if indicators:

        reasons = []

        for indicator in indicators:

            if not isinstance(
                indicator,
                dict,
            ):
                continue

            reason = indicator.get(
                "reason"
            )

            if reason:
                reasons.append(
                    str(reason)
                )

        if reasons:
            reason_text = " ".join(
                reasons
            )

        else:
            reason_text = (
                f"Risk condition detected: "
                f"{detection_type}"
            )

    else:

        reason_text = (
            f"Risk condition detected: "
            f"{detection_type}"
        )

    # --------------------------------------------------------
    # Create alert object
    # --------------------------------------------------------

    alert = {

        "alert_id":
            generate_alert_id(),

        "alert_type":
            "RISK ALERT",

        "severity":
            risk_level,

        "risk_score":
            risk_score,

        "risk_level":
            risk_level,

        "network":
            risk_result.get(
                "network"
            ),

        "asset":
            risk_result.get(
                "asset"
            ),

        "address":
            risk_result.get(
                "address"
            ),

        "txid":
            risk_result.get(
                "txid"
            ),

        "block":
            risk_result.get(
                "block"
            ),

        "detection_type":
            detection_type,

        "indicator_count":
            risk_result.get(
                "indicator_count",
                0,
            ),

        "indicators":
            indicators,

        "reason":
            reason_text,

        "status":
            "NEW",

        "created_at":
            utc_now(),

        "source":
            "CryptoIntel Alert Engine",
    }

    # --------------------------------------------------------
    # Store in existing global state
    # --------------------------------------------------------

    await state.add_alert(
        alert
    )

    ALERTS_CREATED += 1

    return alert


# ============================================================
# RISK RESULT PROCESSING
# ============================================================

async def process_risk_result(
    risk_result: dict[str, Any],
) -> dict[str, Any] | None:

    global ALERTS_SUPPRESSED

    if not isinstance(
        risk_result,
        dict,
    ):
        return None

    risk_score = int(
        risk_result.get(
            "risk_score",
            0,
        )
    )

    # --------------------------------------------------------
    # Only create an alert when the configured threshold
    # is reached.
    # --------------------------------------------------------

    if (
        risk_score
        < ALERT_RISK_SCORE_THRESHOLD
    ):

        ALERTS_SUPPRESSED += 1

        return None

    return await create_alert(
        risk_result
    )


# ============================================================
# ALERT HEALTH
# ============================================================

def health() -> dict[str, Any]:

    return {

        "status":
            "RUNNING",

        "engine":
            "CryptoIntel Alert Engine",

        "alerts_created":
            ALERTS_CREATED,

        "alerts_suppressed":
            ALERTS_SUPPRESSED,

        "stored_alerts":
            len(state.alerts),

        "alert_threshold":
            ALERT_RISK_SCORE_THRESHOLD,

        "storage":
            "state.alerts",

    }


# ============================================================
# LATEST ALERTS
# ============================================================

def latest_alerts(
    limit: int = 100,
) -> list[dict[str, Any]]:

    limit = max(
        1,
        min(
            limit,
            MAX_ALERTS,
        ),
    )

    return list(
        state.alerts
    )[:limit]