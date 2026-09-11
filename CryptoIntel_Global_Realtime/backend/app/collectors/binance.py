import asyncio
import json
import websockets
import httpx

from datetime import datetime, timezone

from app.services.state import state


SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]

WS_URL = "wss://stream.binance.com:9443/stream"

REST_URL = "https://data-api.binance.vision/api/v3/aggTrades"


async def run_binance():

    streams = "/".join(
        [f"{symbol.lower()}@miniTicker" for symbol in SYMBOLS]
        + [f"{symbol.lower()}@trade" for symbol in SYMBOLS]
    )

    ws_url = f"{WS_URL}?streams={streams}"

    try:

        print("Binance WebSocket connecting...")

        async with websockets.connect(
            ws_url,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=10
        ) as ws:

            print("Binance WebSocket connected")

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
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat()
                    })

                elif event == "trade":

                    await state.add_trade({
                        "exchange": "Binance",
                        "symbol": data["s"],
                        "price": float(data["p"]),
                        "quantity": float(data["q"]),
                        "side": "SELL" if data["m"] else "BUY",
                        "timestamp": datetime.now(
                            timezone.utc
                        ).isoformat()
                    })

    except Exception as e:

        print(f"Binance WebSocket unavailable: {e}")
        print("Starting Binance REST market-data fallback...")

        await run_binance_rest()


async def run_binance_rest():

    print("Binance REST fallback started")

    last_ids = {}

    async with httpx.AsyncClient(timeout=15) as client:

        while True:

            try:

                for symbol in SYMBOLS:

                    params = {
                        "symbol": symbol,
                        "limit": 20
                    }

                    if symbol in last_ids:
                        params["fromId"] = last_ids[symbol] + 1

                    response = await client.get(
                        REST_URL,
                        params=params
                    )

                    response.raise_for_status()

                    trades = response.json()

                    for trade in trades:

                        trade_id = int(trade["a"])

                        last_ids[symbol] = max(
                            last_ids.get(symbol, 0),
                            trade_id
                        )

                        await state.add_trade({
                            "exchange": "Binance",
                            "symbol": symbol,
                            "price": float(trade["p"]),
                            "quantity": float(trade["q"]),
                            "side": "SELL" if trade["m"] else "BUY",
                            "timestamp": datetime.fromtimestamp(
                                trade["T"] / 1000,
                                timezone.utc
                            ).isoformat()
                        })

                await asyncio.sleep(2)

            except Exception as e:

                print(f"Binance REST fallback error: {e}")

                await asyncio.sleep(10)