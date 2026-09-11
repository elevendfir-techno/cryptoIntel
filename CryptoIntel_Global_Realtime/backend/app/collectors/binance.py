import asyncio
import json
import websockets

from datetime import datetime, timezone

from app.services.state import state


SYMBOLS = ["btcusdt", "ethusdt", "solusdt", "xrpusdt", "bnbusdt"]


async def run_binance():

    streams = "/".join(
        [f"{s}@miniTicker" for s in SYMBOLS]
        + [f"{s}@trade" for s in SYMBOLS]
    )

    url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    while True:

        try:

            print("Binance collector connecting...")

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            ) as ws:

                print("Binance collector connected")

                async for raw in ws:

                    msg = json.loads(raw)

                    data = msg.get("data", {})

                    event = data.get("e")

                    if event == "24hrMiniTicker":

                        await state.update_market({
                            "symbol": data["s"],
                            "exchange": "Binance",
                            "price": float(data["c"]),
                            "volume": float(data["v"]),
                            "change24h": float(data["P"]),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

                    elif event == "trade":

                        await state.add_trade({
                            "exchange": "Binance",
                            "symbol": data["s"],
                            "price": float(data["p"]),
                            "quantity": float(data["q"]),
                            "side": "SELL" if data["m"] else "BUY",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })

        except Exception as e:

            print(f"Binance collector error: {e}")

            await asyncio.sleep(5)