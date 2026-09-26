import asyncio
from collections import deque
from typing import Any


class State:
    def __init__(self):
        # Exchange + symbol ni unique key ga maintain chestham.
        #
        # Examples:
        # binance:BTCUSDT
        # coinbase:BTC-USD
        # kraken:BTC/USD
        # okx:BTC-USDT
        self.market: dict[str, dict[str, Any]] = {}

        self.trades = deque(maxlen=500)

        self.alerts = deque(maxlen=300)

        # Shared real-time detection storage.
        self.detections = deque(maxlen=500)

        self.blockchain_events = deque(
            maxlen=300
        )

        self.connections = set()

        self.lock = asyncio.Lock()

    async def update_market(
        self,
        item: dict[str, Any],
    ):
        exchange = str(
            item.get("exchange", "unknown")
        ).strip().lower()

        symbol = str(
            item.get("symbol", "unknown")
        ).strip()

        key = f"{exchange}:{symbol}"

        async with self.lock:
            self.market[key] = item

    async def add_trade(
        self,
        item: dict[str, Any],
    ):
        async with self.lock:
            self.trades.appendleft(item)

    async def add_alert(
        self,
        item: dict[str, Any],
    ):
        async with self.lock:
            self.alerts.appendleft(item)


state = State()