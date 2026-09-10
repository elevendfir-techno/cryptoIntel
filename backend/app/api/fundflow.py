from fastapi import APIRouter

router = APIRouter(prefix="/api/fundflow", tags=["fund-flow"])

@router.get("/{address}")
async def fundflow(address: str, network: str = "ethereum", hops: int = 2):
    return {
        "root": address,
        "network": network,
        "hops": hops,
        "nodes": [{"id": address, "type": "wallet"}],
        "edges": [],
        "status": "GRAPH_ENDPOINT_READY"
    }
