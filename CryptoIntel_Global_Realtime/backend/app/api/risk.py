from fastapi import APIRouter, Query

from app.services.risk_engine import (
    health,
    latest_results,
)


router = APIRouter(
    prefix="/api/risk",
    tags=["Risk Analysis"],
)


@router.get("/health")
async def risk_health():
    return health()


@router.get("")
async def risk_results(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
):
    results = latest_results(limit)

    return {
        "status": "LIVE",
        "total_results": len(results),
        "results": results,
    }