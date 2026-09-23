import asyncio
import json
from datetime import datetime, timezone

import websockets

from app.services.state import state
from app.services.data_engine import data_engine


INSTRUMENTS = [
    "BTC-USDT",
    "ETH-USDT",
    "SOL-USDT",
]


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


async def publish_market_event(
    event: dict,
):
    """
    Preserve the existing market state while
    also sending the event through DataEngine.
    """

    await state.update_market(event)

    if data_engine.health()["status"] == "RUNNING":
        await data_engine.ingest(
            event,
            source="okx",
        )


async def run_okx():

    url = (
        "wss://ws.okx.com:8443/ws/v5/public"
    )

    while True:

        try:

            print(
                "OKX collector connecting..."
            )

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as ws:

                print(
                    "OKX collector connected"
                )

                # =====================================
                # TICKER SUBSCRIPTION
                # =====================================

                await ws.send(
                    json.dumps(
                        {
                            "op": "subscribe",
                            "args": [
                                {
                                    "channel": "tickers",
                                    "instId": instrument,
                                }
                                for instrument
                                in INSTRUMENTS
                            ],
                        }
                    )
                )

                # =====================================
                # LIVE TICKER EVENTS
                # =====================================

                async for raw in ws:

                    try:

                        msg = json.loads(raw)

                        if (
                            msg.get("arg", {})
                            .get("channel")
                            != "tickers"
                        ):
                            continue

                        for ticker in msg.get(
                            "data",
                            []
                        ):

                            instrument = ticker.get(
                                "instId"
                            )

                            if not instrument:
                                continue

                            market_event = {
                                "event_type": "market_data",
                                "symbol": instrument,
                                "exchange": "OKX",
                                "price": float(
                                    ticker.get(
                                        "last",
                                        0,
                                    )
                                    or 0
                                ),
                                "volume": float(
                                    ticker.get(
                                        "vol24h",
                                        0,
                                    )
                                    or 0
                                ),
                                "change24h": 0.0,
                                "timestamp": utc_now(),
                            }

                            await publish_market_event(
                                market_event
                            )

                    except Exception as event_error:

                        print(
                            "OKX event processing error:",
                            event_error,
                        )

        except Exception as e:

            print(
                f"OKX collector error: {e}"
            )

            await asyncio.sleep(5)