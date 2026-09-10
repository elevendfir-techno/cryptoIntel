import asyncio, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
from app.collectors.binance import run_binance
from app.collectors.coinbase import run_coinbase
from app.collectors.kraken import run_kraken
from app.collectors.okx import run_okx

async def main():
    await asyncio.gather(
        run_binance(),
        run_coinbase(),
        run_kraken(),
        run_okx(),
    )

if __name__ == "__main__":
    asyncio.run(main())
