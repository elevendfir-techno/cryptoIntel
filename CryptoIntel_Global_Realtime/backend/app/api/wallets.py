from fastapi import APIRouter, HTTPException, Query
import httpx

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

BITCOIN_API = "https://blockchain.info"


@router.get("/{address}")
async def wallet(
    address: str,
    network: str = Query("bitcoin"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=100)
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

            offset = (page - 1) * limit

            response = await client.get(
                f"{BITCOIN_API}/rawaddr/{address}",
                params={
                     "limit": limit,
                     "offset": offset
                }
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
        
        # Calculate incoming and outgoing transaction counts
        incoming_transactions = 0
        outgoing_transactions = 0

        for tx in transactions:
            is_incoming = any(
                output.get("addr") == address
                for output in tx.get("out", [])
            )

            is_outgoing = any(
                input_data.get("prev_out", {}).get("addr") == address
                for input_data in tx.get("inputs", [])
            )

            if is_incoming:
                incoming_transactions += 1

            if is_outgoing:
                outgoing_transactions += 1
        
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
                "funded_transactions": incoming_transactions,
                "spent_transactions": outgoing_transactions,
                "mempool_funded": None,
                "mempool_spent": None
            },

            "transactions": transactions,

            "pagination": {
                "page": page,
                "limit": limit,
                "offset": offset,
                "total": transaction_count,
                "has_more": offset + len(transactions) < transaction_count
            },

            "source": "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Wallet lookup failed: {str(e)}"
        )