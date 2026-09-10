import asyncio
from collections import deque
from typing import Any

class State:
    def __init__(self):
        self.market = {}
        self.trades = deque(maxlen=500)
        self.alerts = deque(maxlen=300)
        self.blockchain_events = deque(maxlen=300)
        self.connections = set()
        self.lock = asyncio.Lock()

    async def update_market(self, item: dict[str, Any]):
        async with self.lock:
            self.market[item["symbol"]] = item

    async def add_trade(self, item: dict[str, Any]):
        async with self.lock:
            self.trades.appendleft(item)

    async def add_alert(self, item: dict[str, Any]):
        async with self.lock:
            self.alerts.appendleft(item)

state = State()
