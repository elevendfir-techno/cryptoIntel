import asyncio
import json
from datetime import datetime, timezone

import websockets

from app.services.state import state
from app.services.data_engine import data_engine


PRODUCTS = [
    "BTC-USD",
    "ETH-USD",
    "SOL-USD",
    "XRP-USD",
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
            source="coinbase",
        )


async def publish_trade_event(
    event: dict,
):
    """
    Preserve the existing trade state while
    also sending the event through DataEngine.
    """

    await state.add_trade(event)

    if data_engine.health()["status"] == "RUNNING":
        await data_engine.ingest(
            event,
            source="coinbase",
        )


async def run_coinbase():

    url = (
        "wss://advanced-trade-ws.coinbase.com"
    )

    while True:

        try:

            print(
                "Coinbase collector connecting..."
            )

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10,
            ) as ws:

                print(
                    "Coinbase collector connected"
                )

                # =====================================
                # TICKER SUBSCRIPTION
                # =====================================

                await ws.send(
                    json.dumps(
                        {
                            "type": "subscribe",
                            "product_ids": PRODUCTS,
                            "channel": "ticker",
                        }
                    )
                )

                # =====================================
                # MARKET TRADE SUBSCRIPTION
                # =====================================

                await ws.send(
                    json.dumps(
                        {
                            "type": "subscribe",
                            "product_ids": PRODUCTS,
                            "channel": "market_trades",
                        }
                    )
                )

                # =====================================
                # LIVE EVENTS
                # =====================================

                async for raw in ws:

                    try:

                        msg = json.loads(raw)

                        events = msg.get(
                            "events",
                            []
                        )

                        for event in events:

                            # =================================
                            # TICKER DATA
                            # =================================

                            for ticker in event.get(
                                "tickers",
                                []
                            ):

                                product_id = ticker.get(
                                    "product_id"
                                )

                                price = ticker.get(
                                    "price"
                                )

                                if (
                                    not product_id
                                    or not price
                                ):
                                    continue

                                market_event = {
                                    "event_type": "market_data",
                                    "symbol": product_id,
                                    "exchange": "Coinbase",
                                    "price": float(
                                        price
                                    ),
                                    "volume": float(
                                        ticker.get(
                                            "volume_24_h",
                                            0,
                                        )
                                    ),
                                    "change24h": 0.0,
                                    "timestamp": utc_now(),
                                }

                                await publish_market_event(
                                    market_event
                                )

                            # =================================
                            # MARKET TRADE DATA
                            # =================================

                            for trade in event.get(
                                "trades",
                                []
                            ):

                                product_id = trade.get(
                                    "product_id",
                                    ""
                                )

                                price = trade.get(
                                    "price"
                                )

                                quantity = trade.get(
                                    "size"
                                )

                                if (
                                    not product_id
                                    or not price
                                    or not quantity
                                ):
                                    continue

                                trade_event = {
                                    "event_type": "market_trade",
                                    "exchange": "Coinbase",
                                    "symbol": product_id,
                                    "price": float(
                                        price
                                    ),
                                    "quantity": float(
                                        quantity
                                    ),
                                    "side": trade.get(
                                        "side",
                                        "UNKNOWN",
                                    ),
                                    "timestamp": utc_now(),
                                }

                                await publish_trade_event(
                                    trade_event
                                )

                    except Exception as event_error:

                        print(
                            "Coinbase event processing error:",
                            event_error,
                        )

        except Exception as e:

            print(
                f"Coinbase collector error: {e}"
            )

            await asyncio.sleep(5)