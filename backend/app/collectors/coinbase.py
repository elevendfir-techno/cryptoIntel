import asyncio, json, websockets
from datetime import datetime, timezone
from app.services.state import state

PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]

async def run_coinbase():
    url = "wss://advanced-trade-ws.coinbase.com"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": PRODUCTS,
                    "channel": "ticker"
                }))
                async for raw in ws:
                    msg = json.loads(raw)
                    for event in msg.get("events", []):
                        for ticker in event.get("tickers", []):
                            p = ticker.get("price")
                            if p:
                                await state.update_market({
                                    "symbol": ticker["product_id"],
                                    "exchange": "Coinbase",
                                    "price": float(p),
                                    "volume": float(ticker.get("volume_24_h", 0)),
                                    "change24h": 0.0,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                })
        except Exception:
            await asyncio.sleep(5)
