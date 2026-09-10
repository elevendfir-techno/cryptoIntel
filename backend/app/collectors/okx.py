import asyncio, json, websockets
from datetime import datetime, timezone
from app.services.state import state

INSTRUMENTS = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

async def run_okx():
    url = "wss://ws.okx.com:8443/ws/v5/public"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({
                    "op": "subscribe",
                    "args": [{"channel": "tickers", "instId": x} for x in INSTRUMENTS]
                }))
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("arg", {}).get("channel") == "tickers":
                        for t in msg.get("data", []):
                            await state.update_market({
                                "symbol": t.get("instId"),
                                "exchange": "OKX",
                                "price": float(t.get("last", 0)),
                                "volume": float(t.get("vol24h", 0)),
                                "change24h": 0.0,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
        except Exception:
            await asyncio.sleep(5)
