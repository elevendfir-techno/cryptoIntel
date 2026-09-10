from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

@router.get("/{address}")
async def wallet(address: str, network: str = Query("ethereum")):
    return {
        "address": address,
        "network": network,
        "status": "LOOKUP_ENDPOINT_READY",
        "note": "Connect a blockchain node/indexer provider for live wallet history."
    }
