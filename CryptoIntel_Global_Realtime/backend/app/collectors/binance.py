import asyncio
import json
from datetime import datetime, timezone

import httpx
import websockets

from app.services.state import state
from app.services.data_engine import data_engine


SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
]

WS_URL = "wss://stream.binance.com:9443/stream"

REST_URL = "https://data-api.binance.vision/api/v3/aggTrades"


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


async def publish_market_event(event: dict):
    """
    Send market event through the global DataEngine.

    Existing state update is also preserved so the
    current CryptoIntel frontend continues working.
    """

    await state.update_market(event)

    if data_engine.health()["status"] == "RUNNING":
        await data_engine.ingest(
            event,
            source="binance",
        )


async def publish_trade_event(event: dict):
    """
    Send trade event through the global DataEngine.

    Existing trade state is preserved for the current
    WebSocket/frontend implementation.
    """

    await state.add_trade(event)

    if data_engine.health()["status"] == "RUNNING":
        await data_engine.ingest(
            event,
            source="binance",
        )


async def run_binance():

    streams = "/".join(
        [
            f"{symbol.lower()}@miniTicker"
            for symbol in SYMBOLS
        ]
        +
        [
            f"{symbol.lower()}@trade"
            for symbol in SYMBOLS
        ]
    )

    ws_url = f"{WS_URL}?streams={streams}"

    while True:

        try:

            print(
                "Binance WebSocket connecting..."
            )

            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as ws:

                print(
                    "Binance WebSocket connected"
                )

                async for raw in ws:

                    try:

                        msg = json.loads(raw)

                        data = msg.get(
                            "data",
                            {}
                        )

                        event_type = data.get(
                            "e"
                        )

                        # =====================================
                        # 24H MARKET TICKER
                        # =====================================

                        if event_type == "24hrMiniTicker":

                            event = {
                                "event_type": "market_data",
                                "symbol": data["s"],
                                "exchange": "Binance",
                                "price": float(
                                    data["c"]
                                ),
                                "volume": float(
                                    data["v"]
                                ),
                                "change24h": float(
                                    data.get(
                                        "P",
                                        0
                                    )
                                ),
                                "timestamp": utc_now(),
                            }

                            await publish_market_event(
                                event
                            )

                        # =====================================
                        # LIVE TRADE
                        # =====================================

                        elif event_type == "trade":

                            event = {
                                "event_type": "market_trade",
                                "exchange": "Binance",
                                "symbol": data["s"],
                                "price": float(
                                    data["p"]
                                ),
                                "quantity": float(
                                    data["q"]
                                ),
                                "side": (
                                    "SELL"
                                    if data["m"]
                                    else "BUY"
                                ),
                                "timestamp": (
                                    datetime.fromtimestamp(
                                        data["T"] / 1000,
                                        timezone.utc,
                                    ).isoformat()
                                ),
                            }

                            await publish_trade_event(
                                event
                            )

                    except Exception as event_error:

                        print(
                            "Binance event processing error:",
                            event_error,
                        )

        except Exception as e:

            print(
                f"Binance WebSocket unavailable: {e}"
            )

            print(
                "Starting Binance REST market-data fallback..."
            )

            try:
                await run_binance_rest()
            except Exception as fallback_error:
                print(
                    "Binance REST fallback stopped:",
                    fallback_error,
                )

        # Reconnect after connection/fallback failure.
        await asyncio.sleep(5)


async def run_binance_rest():

    print(
        "Binance REST fallback started"
    )

    last_ids = {}

    async with httpx.AsyncClient(
        timeout=15
    ) as client:

        while True:

            try:

                for symbol in SYMBOLS:

                    params = {
                        "symbol": symbol,
                        "limit": 20,
                    }

                    if symbol in last_ids:

                        params["fromId"] = (
                            last_ids[symbol] + 1
                        )

                    response = await client.get(
                        REST_URL,
                        params=params,
                    )

                    response.raise_for_status()

                    trades = response.json()

                    for trade in trades:

                        trade_id = int(
                            trade["a"]
                        )

                        last_ids[symbol] = max(
                            last_ids.get(
                                symbol,
                                0,
                            ),
                            trade_id,
                        )

                        event = {
                            "event_type": "market_trade",
                            "exchange": "Binance",
                            "symbol": symbol,
                            "price": float(
                                trade["p"]
                            ),
                            "quantity": float(
                                trade["q"]
                            ),
                            "side": (
                                "SELL"
                                if trade["m"]
                                else "BUY"
                            ),
                            "timestamp": (
                                datetime.fromtimestamp(
                                    trade["T"] / 1000,
                                    timezone.utc,
                                ).isoformat()
                            ),
                        }

                        await publish_trade_event(
                            event
                        )

                await asyncio.sleep(2)

            except Exception as e:

                print(
                    f"Binance REST fallback error: {e}"
                )

                await asyncio.sleep(10)