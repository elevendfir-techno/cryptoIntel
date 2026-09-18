from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter(
    prefix="/api/blockchain",
    tags=["blockchain"]
)

BITCOIN_API = "https://blockchain.info"


@router.get("/networks")
async def networks():
    return [
        {
            "name": "Bitcoin",
            "status": "LIVE",
            "provider": "Blockchain.com"
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


# ---------------------------------------------------------
# LATEST BITCOIN BLOCK
# ---------------------------------------------------------

@router.get("/bitcoin/blocks")
async def bitcoin_blocks():

    try:
        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.get(
                f"{BITCOIN_API}/latestblock"
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Latest Bitcoin block not found."
            )

        response.raise_for_status()

        latest = response.json()

        return {
            "network": "Bitcoin",
            "status": "LIVE",
            "blocks": [
                {
                    "hash": latest.get("hash"),
                    "height": latest.get("height"),
                    "time": latest.get("time"),
                    "block_index": latest.get("block_index"),
                    "txIndexes": latest.get(
                        "txIndexes",
                        []
                    )
                }
            ],
            "source": "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Bitcoin data unavailable: {str(e)}"
        )


# ---------------------------------------------------------
# BITCOIN TRANSACTION
# ---------------------------------------------------------

@router.get("/bitcoin/transaction/{txid}")
async def bitcoin_transaction(txid: str):

    try:
        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.get(
                f"{BITCOIN_API}/rawtx/{txid}"
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found."
            )

        response.raise_for_status()

        transaction = response.json()

        return {
            "network": "Bitcoin",
            "status": "LIVE",
            "transaction": transaction,
            "source": "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Transaction lookup failed: {str(e)}"
        )


# ---------------------------------------------------------
# BITCOIN ADDRESS
# ---------------------------------------------------------

@router.get("/bitcoin/address/{address}")
async def bitcoin_address(address: str):

    # Reject Ethereum-style addresses
    if address.lower().startswith("0x"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ethereum-style address detected. "
                "Please enter a Bitcoin address."
            )
        )

    try:
        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.get(
                f"{BITCOIN_API}/rawaddr/{address}",
                params={
                    "limit": 20
                }
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Bitcoin address not found."
            )

        response.raise_for_status()

        details = response.json()

        transactions = details.get(
            "txs",
            []
        )

        return {
            "network": "Bitcoin",
            "status": "LIVE",
            "address": address,

            "details": {
                "address": details.get(
                    "address",
                    address
                ),

                "hash160": details.get(
                    "hash160"
                ),

                "total_received": details.get(
                    "total_received",
                    0
                ),

                "total_sent": details.get(
                    "total_sent",
                    0
                ),

                "final_balance": details.get(
                    "final_balance",
                    0
                ),

                "transaction_count": details.get(
                    "n_tx",
                    0
                )
            },

            "transactions": transactions,

            "source":
                "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Address lookup failed: {str(e)}"
        )