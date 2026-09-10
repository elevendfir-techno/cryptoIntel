from fastapi import APIRouter

router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])

@router.get("/networks")
async def networks():
    return [
        {"name": "Bitcoin", "status": "READY_FOR_NODE_PROVIDER"},
        {"name": "Ethereum", "status": "READY_FOR_NODE_PROVIDER"},
        {"name": "Solana", "status": "READY_FOR_NODE_PROVIDER"},
        {"name": "Tron", "status": "READY_FOR_NODE_PROVIDER"},
        {"name": "Polygon", "status": "READY_FOR_NODE_PROVIDER"},
    ]
