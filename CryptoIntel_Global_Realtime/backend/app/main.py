import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.services.state import state
from app.api.markets import router as markets_router
from app.api.alerts import router as alerts_router
from app.api.blockchain import router as blockchain_router
from app.api.wallets import router as wallets_router
from app.api.fundflow import router as fundflow_router
from app.api.detection import router as detection_router
from app.collectors.binance import run_binance
from app.collectors.coinbase import run_coinbase
from app.collectors.kraken import run_kraken
from app.collectors.okx import run_okx

app = FastAPI(title="CryptoIntel API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets_router)
app.include_router(alerts_router)
app.include_router(blockchain_router)
app.include_router(wallets_router)
app.include_router(fundflow_router)
app.include_router(detection_router)

@app.get("/")
async def root():
    return {"name": "CryptoIntel", "status": "online", "scope": "global real-time crypto intelligence"}

@app.get("/health")
async def health():
    return {"status": "ok", "markets": len(state.market), "trades": len(state.trades)}

@app.websocket("/ws/markets")
async def market_ws(ws: WebSocket):
    await ws.accept()
    state.connections.add(ws)
    try:
        while True:
            await ws.send_json({
                "markets": list(state.market.values())[-100:],
                "trades": list(state.trades)[:50],
                "alerts": list(state.alerts)[:20],
            })
            await asyncio.sleep(1)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        state.connections.discard(ws)

@app.on_event("startup")
async def startup():
    app.state.collectors = [
        asyncio.create_task(run_binance()),
        asyncio.create_task(run_coinbase()),
        asyncio.create_task(run_kraken()),
        asyncio.create_task(run_okx()),
    ]