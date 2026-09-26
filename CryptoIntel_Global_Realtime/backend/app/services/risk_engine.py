"""
CryptoIntel Risk Analysis Engine

Consumes detections from the Detection Engine and
calculates an explainable risk score.

This engine does NOT declare an address fraudulent.
It produces analytical risk indicators for investigation.

Flow:

Detection
    ↓
Risk Analysis
    ↓
Risk Correlation
    ↓
Alert Engine
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

from app.services.risk_correlation import correlate_risk_result


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RISK_RECORDS = 500

RISK_LEVEL_LOW = "LOW"
RISK_LEVEL_MEDIUM = "MEDIUM"
RISK_LEVEL_HIGH = "HIGH"
RISK_LEVEL_CRITICAL = "CRITICAL"


# ============================================================
# STORAGE
# ============================================================

RISK_RESULTS: deque[dict[str, Any]] = deque(
    maxlen=MAX_RISK_RECORDS
)

RISK_EVENTS_ANALYZED = 0
RISK_RESULTS_CREATED = 0

CORRELATED_RISK_RESULTS_CREATED = 0


# ============================================================
# HELPERS
# ============================================================

def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def calculate_risk_level(score: int) -> str:
    if score >= 80:
        return RISK_LEVEL_CRITICAL

    if score >= 60:
        return RISK_LEVEL_HIGH

    if score >= 30:
        return RISK_LEVEL_MEDIUM

    return RISK_LEVEL_LOW


# ============================================================
# CORRELATION BRIDGE
# ============================================================

async def _process_correlation(
    risk_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Send an individual risk result to the
    Risk Correlation Engine.

    If multiple risk indicators belong to the same
    transaction/address inside the correlation window,
    the correlation engine returns a combined result.

    The combined result is then forwarded to the
    Alert Engine.
    """

    global CORRELATED_RISK_RESULTS_CREATED

    try:

        correlated_result = await correlate_risk_result(
            risk_result
        )

        if not correlated_result:
            return None

        CORRELATED_RISK_RESULTS_CREATED += 1

        # ----------------------------------------------------
        # Forward correlated risk to Alert Engine
        # ----------------------------------------------------

        try:

            from app.services.alert_engine import (
                process_risk_result,
            )

            await process_risk_result(
                correlated_result
            )

        except Exception:
            # Alert failure must not break
            # Risk Analysis processing.
            pass

        return correlated_result

    except Exception:
        # Correlation failure must not break
        # the main Risk Engine.
        return None


def _schedule_correlation(
    risk_result: dict[str, Any],
) -> None:
    """
    Schedule the asynchronous correlation bridge.

    Risk analysis itself remains synchronous so existing
    Detection Engine behavior is preserved.
    """

    try:

        loop = asyncio.get_running_loop()

    except RuntimeError:
        return

    loop.create_task(
        _process_correlation(
            risk_result
        )
    )


# ============================================================
# RISK RULES
# ============================================================

def analyze_detection(
    detection: dict[str, Any],
) -> dict[str, Any]:

    global RISK_EVENTS_ANALYZED
    global RISK_RESULTS_CREATED

    RISK_EVENTS_ANALYZED += 1

    detection_type = str(
        detection.get("type", "")
    ).upper()

    network = detection.get(
        "network",
        detection.get("source", "Unknown"),
    )

    asset = detection.get(
        "asset",
        "UNKNOWN",
    )

    address = detection.get(
        "from"
    ) or detection.get(
        "address"
    )

    score = 0
    indicators: list[dict[str, Any]] = []

    # --------------------------------------------------------
    # LARGE TRANSFER
    # --------------------------------------------------------

    if detection_type == "LARGE TRANSFER":

        score += 30

        indicators.append(
            {
                "indicator": "LARGE TRANSFER",
                "weight": 30,
                "reason": (
                    "A transaction exceeded the configured "
                    "large-transfer threshold."
                ),
            }
        )

    # --------------------------------------------------------
    # HIGH VALUE TRANSACTION
    # --------------------------------------------------------

    elif detection_type == "HIGH VALUE TRANSACTION":

        score += 40

        indicators.append(
            {
                "indicator": "HIGH VALUE TRANSACTION",
                "weight": 40,
                "reason": (
                    "A high-value blockchain transaction "
                    "was detected."
                ),
            }
        )

    # --------------------------------------------------------
    # RAPID TRANSACTION ACTIVITY
    # --------------------------------------------------------

    elif detection_type == "RAPID TRANSACTION ACTIVITY":

        score += 30

        transaction_count = detection.get(
            "transaction_count"
        )

        if transaction_count is None:
            value_text = str(
                detection.get("value", "")
            )

            try:
                transaction_count = int(
                    value_text.split()[0]
                )
            except (ValueError, IndexError):
                transaction_count = 0

        if transaction_count >= 50:

            score += 20

            indicators.append(
                {
                    "indicator": "EXTREME TRANSACTION VELOCITY",
                    "weight": 20,
                    "reason": (
                        "The address generated at least "
                        "50 transactions within the "
                        "configured short activity window."
                    ),
                }
            )

        indicators.append(
            {
                "indicator": "RAPID TRANSACTION ACTIVITY",
                "weight": 30,
                "reason": (
                    "A single address generated many "
                    "transactions within a short time window."
                ),
            }
        )

    # --------------------------------------------------------
    # PRICE ANOMALY
    # --------------------------------------------------------

    elif detection_type == "PRICE ANOMALY":

        score += 20

        indicators.append(
            {
                "indicator": "PRICE ANOMALY",
                "weight": 20,
                "reason": (
                    "Market price movement exceeded "
                    "the configured anomaly threshold."
                ),
            }
        )

    # --------------------------------------------------------
    # VOLUME SPIKE
    # --------------------------------------------------------

    elif detection_type == "VOLUME SPIKE":

        score += 20

        indicators.append(
            {
                "indicator": "VOLUME SPIKE",
                "weight": 20,
                "reason": (
                    "Trading volume exceeded the "
                    "configured spike threshold."
                ),
            }
        )

    # --------------------------------------------------------
    # EXCHANGE SPREAD
    # --------------------------------------------------------

    elif detection_type == "EXCHANGE SPREAD":

        score += 15

        indicators.append(
            {
                "indicator": "EXCHANGE SPREAD",
                "weight": 15,
                "reason": (
                    "A significant price difference "
                    "was observed between exchanges."
                ),
            }
        )
    # --------------------------------------------------------
    # MULTI-HOP FUND FLOW
    # --------------------------------------------------------

    elif detection_type == "MULTI_HOP_FUND_FLOW":

        score += 20

        hops = int(
            detection.get("hops", 0) or 0
        )

        wallet_count = int(
            detection.get("wallet_count", 0) or 0
        )

        edge_count = int(
            detection.get("edge_count", 0) or 0
        )

        transactions_scanned = int(
            detection.get("transactions_scanned", 0) or 0
        )

        indicators.append(
            {
                "indicator": "MULTI_HOP_FUND_FLOW",
                "weight": 20,
                "reason": (
                    "A multi-hop fund-flow pattern "
                    "was identified across blockchain "
                    "wallet relationships."
                ),
            }
        )

        if hops >= 2:

            score += 10

            indicators.append(
                {
                    "indicator": "MULTI_HOP_DEPTH",
                    "weight": 10,
                    "reason": (
                        f"The fund-flow analysis traced "
                        f"{hops} blockchain hops."
                    ),
                }
            )

        if wallet_count >= 5:

            score += 10

            indicators.append(
                {
                    "indicator": "MULTIPLE_WALLETS",
                    "weight": 10,
                    "reason": (
                        f"The fund-flow analysis identified "
                        f"{wallet_count} wallets."
                    ),
                }
            )

        if edge_count >= 50:

            score += 10

            indicators.append(
                {
                    "indicator": "HIGH_FLOW_CONNECTIVITY",
                    "weight": 10,
                    "reason": (
                        f"The analysis identified "
                        f"{edge_count} wallet connections."
                    ),
                }
            )

        if transactions_scanned >= 50:

            score += 10

            indicators.append(
                {
                    "indicator": "HIGH_TRANSACTION_COVERAGE",
                    "weight": 10,
                    "reason": (
                        f"The fund-flow analysis scanned "
                        f"{transactions_scanned} transactions."
                    ),
                }
            )


    # --------------------------------------------------------
    # GENERIC / UNKNOWN DETECTION
    # --------------------------------------------------------

    else:

        score += 10

        indicators.append(
            {
                "indicator": detection_type
                or "UNKNOWN DETECTION",
                "weight": 10,
                "reason": (
                    "A detection event was received "
                    "without a dedicated risk rule."
                ),
            }
        )

    # --------------------------------------------------------
    # BOUND SCORE
    # --------------------------------------------------------

    score = min(score, 100)

    risk_level = calculate_risk_level(
        score
    )

    # --------------------------------------------------------
    # RISK RESULT
    # --------------------------------------------------------

    result = {
        "risk_score": score,
        "risk_level": risk_level,
        "network": network,
        "asset": asset,
        "address": address,
        "txid": detection.get("txid"),
        "block": detection.get("block"),
        "detection_type": detection_type,
        "indicators": indicators,
        "indicator_count": len(indicators),
        "analyzed_at": utc_now(),
        "source": "CryptoIntel Risk Analysis Engine",
        "status": "ANALYZED",
    }

    # --------------------------------------------------------
    # STORE ORIGINAL RISK RESULT
    # --------------------------------------------------------

    RISK_RESULTS.append(
        result
    )

    RISK_RESULTS_CREATED += 1

    # --------------------------------------------------------
    # SEND TO CORRELATION ENGINE
    # --------------------------------------------------------

    _schedule_correlation(
        result
    )

    return result


# ============================================================
# BATCH ANALYSIS
# ============================================================

def analyze_detections(
    detections: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    results = []

    for detection in detections:

        if isinstance(
            detection,
            dict,
        ):

            results.append(
                analyze_detection(
                    detection
                )
            )

    return results


# ============================================================
# ENGINE HEALTH
# ============================================================

def health() -> dict[str, Any]:

    return {
        "status": "RUNNING",
        "events_analyzed": RISK_EVENTS_ANALYZED,
        "results_created": RISK_RESULTS_CREATED,
        "stored_results": len(
            RISK_RESULTS
        ),
        "correlated_results_created": (
            CORRELATED_RISK_RESULTS_CREATED
        ),
        "engine": "Risk Analysis Engine",
        "correlation_engine": "CONNECTED",
    }


# ============================================================
# LATEST RESULTS
# ============================================================

def latest_results(
    limit: int = 100,
) -> list[dict[str, Any]]:

    limit = max(
        1,
        min(
            limit,
            MAX_RISK_RECORDS,
        ),
    )

    return list(
        RISK_RESULTS
    )[-limit:][::-1]