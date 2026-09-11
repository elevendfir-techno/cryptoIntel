from fastapi import APIRouter
from app.services.state import state

router = APIRouter(prefix="/api/detection", tags=["Detection"])


@router.get("")
async def detection():

    detections = []

    # ---------------------------------------------------------
    # 1. PRICE ANOMALY
    # ---------------------------------------------------------
    for market in state.market.values():

        change = market.get("change24h")

        if change is not None:
            try:
                change = float(change)

                if abs(change) >= 8:
                    detections.append({
                        "type": "PRICE ANOMALY",
                        "severity": "HIGH" if abs(change) >= 15 else "MEDIUM",
                        "asset": market.get("symbol", "UNKNOWN"),
                        "source": market.get("exchange", "UNKNOWN"),
                        "value": f"{change:.2f}%",
                        "reason": "Unusual 24-hour price movement detected."
                    })

            except (TypeError, ValueError):
                pass

    # ---------------------------------------------------------
    # 2. VOLUME SPIKE
    # ---------------------------------------------------------
    for market in state.market.values():

        volume = market.get("volume")

        if volume is not None:
            try:
                volume = float(volume)

                if volume >= 100000000:
                    detections.append({
                        "type": "VOLUME SPIKE",
                        "severity": "MEDIUM",
                        "asset": market.get("symbol", "UNKNOWN"),
                        "source": market.get("exchange", "UNKNOWN"),
                        "value": f"{volume:,.2f}",
                        "reason": "High trading volume detected."
                    })

            except (TypeError, ValueError):
                pass

    # ---------------------------------------------------------
    # 3. RAPID ACTIVITY
    # ---------------------------------------------------------
    if len(state.trades) >= 50:

        detections.append({
            "type": "RAPID ACTIVITY",
            "severity": "MEDIUM",
            "asset": "MULTIPLE",
            "source": "Market Feed",
            "value": f"{len(state.trades)} trades",
            "reason": "High-frequency market activity detected."
        })

    return {
        "status": "LIVE",
        "total_detections": len(detections),
        "detections": detections[:100],
        "source": "Live exchange market feeds"
    }