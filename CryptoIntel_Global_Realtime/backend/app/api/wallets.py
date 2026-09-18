from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

BITCOIN_API = "https://blockchain.info"


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

    # Basic validation
    if address.startswith("0x"):
        raise HTTPException(
            status_code=400,
            detail="Ethereum-style address detected. Please enter a Bitcoin address."
        )

    try:
        async with httpx.AsyncClient(timeout=20) as client:

            response = await client.get(
                f"{BITCOIN_API}/rawaddr/{address}"
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Bitcoin address not found."
            )

        response.raise_for_status()

        details = response.json()

        # Blockchain.com returns balance values in satoshis
        total_received = int(
            details.get("total_received", 0)
        )

        total_sent = int(
            details.get("total_sent", 0)
        )

        final_balance = int(
            details.get("final_balance", 0)
        )

        transaction_count = int(
            details.get("n_tx", 0)
        )

        transactions = details.get(
            "txs",
            []
        )

        return {
            "address": address,
            "network": "Bitcoin",
            "status": "LIVE",

            "balance": {
                "funded": total_received,
                "spent": total_sent,
                "balance": final_balance
            },

            "activity": {
                "confirmed_transactions": transaction_count,
                "funded_transactions": None,
                "spent_transactions": None,
                "mempool_funded": None,
                "mempool_spent": None
            },

            "transactions": transactions,

            "source": "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Wallet lookup failed: {str(e)}"
        )