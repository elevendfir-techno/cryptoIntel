import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.services.state import state
from app.services.data_engine import data_engine

from app.api.markets import router as markets_router
from app.api.alerts import router as alerts_router
from app.api.blockchain import (
    router as blockchain_router,
    start_blockchain_collector,
)
from app.api.wallets import router as wallets_router
from app.api.fundflow import router as fundflow_router
from app.api.detection import router as detection_router
from app.api.risk import router as risk_router
from app.api.multichain import router as multichain_router
from app.api.solana import router as solana_router
from app.api.tron import router as tron_router
from app.api.xrpl import router as xrpl_router
from app.api.cardano import router as cardano_router
from app.api.threat_inputs import router as threat_inputs_router

from app.collectors.binance import run_binance
from app.collectors.coinbase import run_coinbase
from app.collectors.kraken import run_kraken
from app.collectors.okx import run_okx

app = FastAPI(
    title="CryptoIntel API",
    version="2.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API ROUTES
# =========================================================

app.include_router(markets_router)
app.include_router(alerts_router)
app.include_router(blockchain_router)
app.include_router(wallets_router)
app.include_router(fundflow_router)
app.include_router(detection_router)
app.include_router(risk_router)
app.include_router(multichain_router)
app.include_router(solana_router)
app.include_router(tron_router)
app.include_router(xrpl_router)
app.include_router(cardano_router)
app.include_router(threat_inputs_router)

# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():
    return {
        "name": "CryptoIntel",
        "status": "online",
        "scope": "global real-time crypto intelligence",
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "markets": len(state.market),
        "trades": len(state.trades),
        "alerts": len(state.alerts),
        "data_engine": data_engine.health(),
    }


# =========================================================
# DATA ENGINE HEALTH
# =========================================================

@app.get("/api/data-engine/health")
async def data_engine_health():
    return data_engine.health()


# =========================================================
# MARKET WEBSOCKET
# =========================================================

@app.websocket("/ws/markets")
async def market_ws(ws: WebSocket):

    await ws.accept()

    state.connections.add(ws)

    try:
        while True:

            await ws.send_json(
                {
                    "markets": list(
                        state.market.values()
                    )[-100:],

                    "trades": list(
                        state.trades
                    )[:50],

                    "alerts": list(
                        state.alerts
                    )[:20],
                }
            )

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass

    except Exception:
        pass

    finally:
        state.connections.discard(ws)


# =========================================================
# STARTUP
# =========================================================

@app.on_event("startup")
async def startup():

    # Start the shared real-time data engine first.
    await data_engine.start()

    # Start existing market collectors.
    app.state.collectors = [
        asyncio.create_task(
            run_binance()
        ),

        asyncio.create_task(
            run_coinbase()
        ),

        asyncio.create_task(
            run_kraken()
        ),

        asyncio.create_task(
            run_okx()
        ),
    ]

    # Start blockchain collector.
    app.state.collectors.append(
        start_blockchain_collector()
    )


# =========================================================
# SHUTDOWN
# =========================================================

@app.on_event("shutdown")
async def shutdown():

    # Stop Data Engine cleanly.
    await data_engine.stop()

    # Cancel running collectors.
    collectors = getattr(
        app.state,
        "collectors",
        [],
    )

    for task in collectors:

        if isinstance(task, asyncio.Task):
            task.cancel()

    if collectors:

        await asyncio.gather(
            *collectors,
            return_exceptions=True,
        )