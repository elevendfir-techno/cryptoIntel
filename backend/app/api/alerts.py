from fastapi import APIRouter
from app.services.state import state

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("")
async def alerts():
    return list(state.alerts)
