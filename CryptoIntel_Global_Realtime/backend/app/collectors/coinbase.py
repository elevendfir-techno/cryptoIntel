import asyncio
import json
import websockets

from datetime import datetime, timezone

from app.services.state import state


PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]


async def run_coinbase():

    url = "wss://advanced-trade-ws.coinbase.com"

    while True:

        try:

            print("Coinbase collector connecting...")

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            ) as ws:

                print("Coinbase collector connected")

                # Subscribe to ticker
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": PRODUCTS,
                    "channel": "ticker"
                }))

                # Subscribe to market trades
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": PRODUCTS,
                    "channel": "market_trades"
                }))

                async for raw in ws:

                    msg = json.loads(raw)

                    # Ticker data
                    for event in msg.get("events", []):

                        for ticker in event.get("tickers", []):

                            p = ticker.get("price")

                            if p:

                                await state.update_market({
                                    "symbol": ticker["product_id"],
                                    "exchange": "Coinbase",
                                    "price": float(p),
                                    "volume": float(
                                        ticker.get("volume_24_h", 0)
                                    ),
                                    "change24h": 0.0,
                                    "timestamp": datetime.now(
                                        timezone.utc
                                    ).isoformat()
                                })

                        # Market trade data
                        for trade in event.get("trades", []):

                            price = trade.get("price")
                            quantity = trade.get("size")

                            if price and quantity:

                                await state.add_trade({
                                    "exchange": "Coinbase",
                                    "symbol": trade.get(
                                        "product_id",
                                        ""
                                    ),
                                    "price": float(price),
                                    "quantity": float(quantity),
                                    "side": trade.get(
                                        "side",
                                        "UNKNOWN"
                                    ),
                                    "timestamp": datetime.now(
                                        timezone.utc
                                    ).isoformat()
                                })

        except Exception as e:

            print(f"Coinbase collector error: {e}")

            await asyncio.sleep(5)