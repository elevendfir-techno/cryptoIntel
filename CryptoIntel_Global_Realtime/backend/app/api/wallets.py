from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

BITCOIN_API = "https://blockstream.info/api"


@router.get("/{address}")
async def wallet(
    address: str,
    network: str = Query("bitcoin")
):
    if network.lower() != "bitcoin":
        raise HTTPException(
            status_code=400,
            detail="Currently only Bitcoin wallet investigation is live."
        )

    try:
        async with httpx.AsyncClient(timeout=15) as client:

            # Get wallet/address information
            address_response = await client.get(
                f"{BITCOIN_API}/address/{address}"
            )

            # Get transaction history
            tx_response = await client.get(
                f"{BITCOIN_API}/address/{address}/txs"
            )

        if address_response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Bitcoin address not found."
            )

        address_response.raise_for_status()
        tx_response.raise_for_status()

        details = address_response.json()
        transactions = tx_response.json()

        chain_stats = details.get("chain_stats", {})
        mempool_stats = details.get("mempool_stats", {})

        return {
            "address": address,
            "network": "Bitcoin",
            "status": "LIVE",

            "balance": {
                "funded": chain_stats.get("funded_txo_sum", 0),
                "spent": chain_stats.get("spent_txo_sum", 0),
                "balance": (
                    chain_stats.get("funded_txo_sum", 0)
                    - chain_stats.get("spent_txo_sum", 0)
                )
            },

            "activity": {
                "funded_transactions": chain_stats.get(
                    "funded_txo_count", 0
                ),
                "spent_transactions": chain_stats.get(
                    "spent_txo_count", 0
                ),
                "confirmed_transactions": chain_stats.get(
                    "tx_count", 0
                ),
                "mempool_funded": mempool_stats.get(
                    "funded_txo_count", 0
                ),
                "mempool_spent": mempool_stats.get(
                    "spent_txo_count", 0
                )
            },

            "transactions": transactions,

            "source": "Blockstream Esplora API"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Wallet lookup failed: {str(e)}"
        )