import asyncio
import json
from datetime import datetime, timezone

import websockets

from app.services.state import state
from app.services.data_engine import data_engine


PAIRS = [
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
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
            source="kraken",
        )


async def run_kraken():

    url = "wss://ws.kraken.com/v2"

    while True:

        try:

            print(
                "Kraken collector connecting..."
            )

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as ws:

                print(
                    "Kraken collector connected"
                )

                # =====================================
                # TICKER SUBSCRIPTION
                # =====================================

                await ws.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "params": {
                                "channel": "ticker",
                                "symbol": PAIRS,
                            },
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
                            msg.get("channel")
                            != "ticker"
                        ):
                            continue

                        for ticker in msg.get(
                            "data",
                            []
                        ):

                            symbol = ticker.get(
                                "symbol"
                            )

                            if not symbol:
                                continue

                            market_event = {
                                "event_type": "market_data",
                                "symbol": symbol,
                                "exchange": "Kraken",
                                "price": float(
                                    ticker.get(
                                        "last",
                                        0,
                                    )
                                    or 0
                                ),
                                "volume": float(
                                    ticker.get(
                                        "volume",
                                        0,
                                    )
                                    or 0
                                ),
                                "change24h": float(
                                    ticker.get(
                                        "change_pct",
                                        0,
                                    )
                                    or 0
                                ),
                                "timestamp": utc_now(),
                            }

                            await publish_market_event(
                                market_event
                            )

                    except Exception as event_error:

                        print(
                            "Kraken event processing error:",
                            event_error,
                        )

        except Exception as e:

            print(
                f"Kraken collector error: {e}"
            )

            await asyncio.sleep(5)