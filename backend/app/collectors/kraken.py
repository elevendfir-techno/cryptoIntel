import asyncio, json, websockets
from datetime import datetime, timezone
from app.services.state import state

PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD"]

async def run_kraken():
    url = "wss://ws.kraken.com/v2"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({
                    "method": "subscribe",
                    "params": {"channel": "ticker", "symbol": PAIRS}
                }))
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("channel") == "ticker":
                        for t in msg.get("data", []):
                            await state.update_market({
                                "symbol": t.get("symbol"),
                                "exchange": "Kraken",
                                "price": float(t.get("last", 0)),
                                "volume": float(t.get("volume", 0)),
                                "change24h": float(t.get("change_pct", 0)),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
        except Exception:
            await asyncio.sleep(5)
