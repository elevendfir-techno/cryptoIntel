from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.services.state import state
from app.services.risk_engine import analyze_detection
from app.services.alert_engine import process_risk_result


router = APIRouter(
    prefix="/api/threat-inputs",
    tags=["Threat Inputs"],
)


# ============================================================
# HELPERS
# ============================================================

def clean_string(
    value: Any,
    default: str = "",
) -> str:

    if value is None:
        return default

    return str(value).strip()


# ============================================================
# THREAT INPUT → DETECTION → RISK → ALERT
# ============================================================

async def process_threat_input(
    item: dict[str, Any],
) -> dict[str, Any]:

    """
    Process a submitted Threat Intelligence input.

    Flow:

        Threat Input
             ↓
        Detection
             ↓
        Risk Engine
             ↓
        Alert Engine
    """

    detection = {

        "type":
            "THREAT INTELLIGENCE INDICATOR",

        "category":
            "THREAT_INTELLIGENCE",

        "severity":
            item.get(
                "severity",
                "MEDIUM",
            ),

        "asset":
            item.get(
                "indicator_type",
                "UNKNOWN",
            ),

        "network":
            item.get(
                "network",
                "UNKNOWN",
            ),

        "address":
            item.get(
                "indicator",
            ),

        "indicator":
            item.get(
                "indicator",
            ),

        "indicator_type":
            item.get(
                "indicator_type",
            ),

        "confidence":
            item.get(
                "confidence",
                "UNKNOWN",
            ),

        "source":
            item.get(
                "source",
                "External Threat Intelligence",
            ),

        "reason":
            (
                "A threat-intelligence indicator "
                "was submitted to the CryptoIntel "
                "Threat Input Engine."
            ),

        "timestamp":
            item.get(
                "timestamp"
            ),

        "data_source":
            "Threat Input API",

        "detection_mode":
            "THREAT INTELLIGENCE INPUT",

        "status":
            "ACTIVE",
    }

    # --------------------------------------------------------
    # Store detection
    # --------------------------------------------------------

    async with state.lock:

        state.detections.appendleft(
            detection
        )

    # --------------------------------------------------------
    # Detection → Risk
    # --------------------------------------------------------

    risk_result = analyze_detection(
        detection
    )

    alert = None

    # --------------------------------------------------------
    # Risk → Alert
    # --------------------------------------------------------

    if risk_result:

        alert = await process_risk_result(
            risk_result
        )

    return {

        "detection":
            detection,

        "risk":
            risk_result,

        "alert":
            alert,
    }


# ============================================================
# ADD THREAT INPUT
# ============================================================

@router.post("")
async def add_threat_input(
    payload: dict[str, Any],
):

    indicator_type = clean_string(
        payload.get("indicator_type")
    )

    indicator = clean_string(
        payload.get("indicator")
    )

    source = clean_string(
        payload.get(
            "source",
            "External Threat Intelligence",
        )
    )

    confidence = clean_string(
        payload.get(
            "confidence",
            "UNKNOWN",
        )
    )

    severity = clean_string(
        payload.get(
            "severity",
            "MEDIUM",
        )
    )

    network = clean_string(
        payload.get(
            "network",
            "UNKNOWN",
        )
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not indicator_type:

        raise HTTPException(
            status_code=400,
            detail="indicator_type is required",
        )

    if not indicator:

        raise HTTPException(
            status_code=400,
            detail="indicator is required",
        )

    # --------------------------------------------------------
    # CREATE THREAT INPUT
    # --------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    item = {

        "id":
            "TI-"
            + now.strftime(
                "%Y%m%d%H%M%S%f"
            ),

        "indicator_type":
            indicator_type,

        "indicator":
            indicator,

        "source":
            source,

        "confidence":
            confidence,

        "severity":
            severity,

        "network":
            network,

        "timestamp":
            now.isoformat(),

        "status":
            "ACTIVE",

        "data_source":
            "Threat Input API",
    }

    # --------------------------------------------------------
    # STORE THREAT INPUT
    # --------------------------------------------------------

    async with state.lock:

        state.threat_inputs.appendleft(
            item
        )

        total_inputs = len(
            state.threat_inputs
        )

    # --------------------------------------------------------
    # PROCESS THROUGH DETECTION → RISK → ALERT
    # --------------------------------------------------------

    processing = await process_threat_input(
        item
    )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {

        "status":
            "LIVE",

        "message":
            "Threat input accepted",

        "threat_input":
            item,

        "processing":
            processing,

        "total_inputs":
            total_inputs,
    }


# ============================================================
# GET ALL THREAT INPUTS
# ============================================================

@router.get("")
async def get_threat_inputs():

    async with state.lock:

        inputs = list(
            state.threat_inputs
        )

    return {

        "status":
            "LIVE",

        "total_inputs":
            len(inputs),

        "inputs":
            inputs[:100],

        "source":
            "CryptoIntel Threat Input Engine",
    }


# ============================================================
# GET SINGLE INDICATOR
# ============================================================

@router.get("/{indicator}")
async def get_threat_input(
    indicator: str,
):

    indicator = clean_string(
        indicator
    )

    async with state.lock:

        matches = [

            item

            for item
            in state.threat_inputs

            if item.get(
                "indicator"
            ) == indicator
        ]

    return {

        "status":
            "LIVE",

        "indicator":
            indicator,

        "matches":
            matches,

        "count":
            len(matches),
    }