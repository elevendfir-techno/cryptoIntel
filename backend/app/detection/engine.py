from datetime import datetime, timezone

def detect_market_anomaly(item, previous=None):
    if previous and previous.get("price"):
        change = abs(item["price"] - previous["price"]) / previous["price"] * 100
        if change >= 1.0:
            return {
                "type": "PRICE_ANOMALY",
                "severity": "HIGH",
                "message": f'{item["symbol"]} moved {change:.2f}% between observations',
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    return None

def detect_large_transfer(amount_usd: float, network: str, tx_hash: str):
    if amount_usd >= 1_000_000:
        return {
            "type": "LARGE_TRANSFER",
            "severity": "HIGH" if amount_usd < 10_000_000 else "CRITICAL",
            "message": f"Large {network} transfer: ${amount_usd:,.0f}",
            "tx_hash": tx_hash,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    return None
