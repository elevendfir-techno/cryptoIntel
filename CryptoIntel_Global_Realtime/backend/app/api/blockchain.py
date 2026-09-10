from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])

BITCOIN_API = "https://blockstream.info/api"


@router.get("/networks")
async def networks():
    return [
        {
            "name": "Bitcoin",
            "status": "LIVE",
            "provider": "Blockstream Esplora"
        },
        {
            "name": "Ethereum",
            "status": "READY"
        },
        {
            "name": "Solana",
            "status": "READY"
        },
        {
            "name": "Tron",
            "status": "READY"
        },
        {
            "name": "Polygon",
            "status": "READY"
        }
    ]


@router.get("/bitcoin/blocks")
async def bitcoin_blocks():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{BITCOIN_API}/blocks"
            )

        response.raise_for_status()

        return {
            "network": "Bitcoin",
            "status": "LIVE",
            "blocks": response.json()[:10]
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Bitcoin data unavailable: {str(e)}"
        )


@router.get("/bitcoin/transaction/{txid}")
async def bitcoin_transaction(txid: str):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{BITCOIN_API}/tx/{txid}"
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found"
            )

        response.raise_for_status()

        return {
            "network": "Bitcoin",
            "status": "LIVE",
            "transaction": response.json()
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Transaction lookup failed: {str(e)}"
        )


@router.get("/bitcoin/address/{address}")
async def bitcoin_address(address: str):
    try:
        async with httpx.AsyncClient(timeout=15) as client:

            address_response = await client.get(
                f"{BITCOIN_API}/address/{address}"
            )

            tx_response = await client.get(
                f"{BITCOIN_API}/address/{address}/txs"
            )

        address_response.raise_for_status()
        tx_response.raise_for_status()

        return {
            "network": "Bitcoin",
            "status": "LIVE",
            "address": address,
            "details": address_response.json(),
            "transactions": tx_response.json()
        }

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Address lookup failed: {str(e)}"
        )