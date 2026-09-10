from fastapi import APIRouter
from app.services.state import state

router = APIRouter(prefix="/api/markets", tags=["markets"])

@router.get("")
async def markets():
    return list(state.market.values())

@router.get("/trades")
async def trades():
    return list(state.trades)
