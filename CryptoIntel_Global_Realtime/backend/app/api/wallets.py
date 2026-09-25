from fastapi import APIRouter, HTTPException, Query
import httpx
import time

router = APIRouter(prefix="/api/wallets", tags=["wallets"])

# ---------------------------------------------------------
# Bitcoin data provider
# ---------------------------------------------------------

MEMPOOL_API = "https://mempool.space/api"

# Mempool address transaction endpoint returns 25 transactions
# per request.
MEMPOOL_PAGE_SIZE = 25

# Keep wallet data in memory for 5 minutes.
CACHE_TTL = 300


# ---------------------------------------------------------
# Wallet history cache
# ---------------------------------------------------------
#
# address -> {
#     "transactions": [...],
#     "incoming": int,
#     "outgoing": int,
#     "timestamp": float
# }
#
# The complete wallet history is cached so that:
#
# Page 1 -> does not refetch history
# Page 2 -> does not refetch history
# Page 3 -> does not refetch history
# Page 4 -> does not refetch history
#
# ---------------------------------------------------------

WALLET_CACHE = {}


def get_cached_wallet(address: str):
    cached = WALLET_CACHE.get(address)

    if not cached:
        return None

    if time.time() - cached["timestamp"] > CACHE_TTL:
        WALLET_CACHE.pop(address, None)
        return None

    return cached


def save_cached_wallet(
    address: str,
    transactions: list,
    incoming: int,
    outgoing: int
):
    WALLET_CACHE[address] = {
        "transactions": transactions,
        "incoming": incoming,
        "outgoing": outgoing,
        "timestamp": time.time()
    }


# ---------------------------------------------------------
# Fetch complete confirmed Bitcoin wallet history
# ---------------------------------------------------------

async def fetch_wallet_history(
    client: httpx.AsyncClient,
    address: str
):
    """
    Fetch the complete confirmed transaction history
    for a Bitcoin address from Mempool.space.

    Mempool.space uses cursor-based pagination:

        /address/{address}/txs/chain

    followed by:

        /address/{address}/txs/chain/{last_seen_txid}
    """

    transactions = []
    next_txid = None

    while True:

        if next_txid:
            url = (
                f"{MEMPOOL_API}/address/{address}"
                f"/txs/chain/{next_txid}"
            )
        else:
            url = (
                f"{MEMPOOL_API}/address/{address}"
                f"/txs/chain"
            )

        try:
            response = await client.get(url)

        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Mempool.space connection failed: "
                    f"{str(e)}"
                )
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail="Bitcoin address not found."
            )

        if response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Mempool.space rate limit reached. "
                    "Please try again later."
                )
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Mempool.space request failed: "
                    f"{str(e)}"
                )
            )

        batch = response.json()

        if not isinstance(batch, list):
            raise HTTPException(
                status_code=502,
                detail=(
                    "Unexpected response received from "
                    "Mempool.space."
                )
            )

        if not batch:
            break

        transactions.extend(batch)

        # Mempool returns 25 transactions per batch.
        # If fewer than 25 are returned, we reached the end.
        if len(batch) < MEMPOOL_PAGE_SIZE:
            break

        last_tx = batch[-1]
        next_txid = last_tx.get("txid")

        if not next_txid:
            break

        # Safety guard against an unexpected repeated cursor.
        if len(transactions) >= 10000:
            break

    return transactions


# ---------------------------------------------------------
# Calculate wallet-wide incoming / outgoing transactions
# ---------------------------------------------------------

def calculate_transaction_directions(
    address: str,
    transactions: list
):
    """
    Calculate wallet-wide transaction counts.

    Incoming:
        Target address appears in transaction outputs.

    Outgoing:
        Target address appears in transaction inputs.

    A transaction can technically be counted in both categories
    if the same wallet appears on both sides of the transaction.
    This preserves the behavior of the previous implementation.
    """

    incoming_transactions = 0
    outgoing_transactions = 0

    for tx in transactions:

        # -------------------------------------------------
        # Incoming
        # -------------------------------------------------

        is_incoming = any(
            output.get("scriptpubkey_address") == address
            for output in tx.get("vout", [])
        )

        # -------------------------------------------------
        # Outgoing
        # -------------------------------------------------

        is_outgoing = any(
            input_data.get("prevout", {}).get(
                "scriptpubkey_address"
            ) == address
            for input_data in tx.get("vin", [])
        )

        if is_incoming:
            incoming_transactions += 1

        if is_outgoing:
            outgoing_transactions += 1

    return (
        incoming_transactions,
        outgoing_transactions
    )


# ---------------------------------------------------------
# Normalize Mempool transaction
# ---------------------------------------------------------

def normalize_transaction(tx: dict):
    """
    Keep Mempool transaction data while adding compatibility
    fields expected by the existing CryptoIntel frontend.

    Existing frontend supports:
        tx.hash
        tx.txid
    """

    normalized = dict(tx)

    txid = tx.get("txid")

    # Existing frontend already checks tx.hash || tx.txid.
    # Adding hash keeps compatibility with older API shape.
    normalized["hash"] = txid

    status = tx.get("status") or {}

    normalized["confirmed"] = status.get(
        "confirmed",
        False
    )

    normalized["block_height"] = status.get(
        "block_height"
    )

    normalized["block_hash"] = status.get(
        "block_hash"
    )

    normalized["timestamp"] = status.get(
        "block_time"
    )

    return normalized


# ---------------------------------------------------------
# Wallet endpoint
# ---------------------------------------------------------

@router.get("/{address}")
async def wallet(
    address: str,
    network: str = Query("bitcoin"),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=100)
):

    # -----------------------------------------------------
    # Network validation
    # -----------------------------------------------------

    if network.lower() != "bitcoin":
        raise HTTPException(
            status_code=400,
            detail=(
                "Currently only Bitcoin wallet investigation "
                "is live."
            )
        )

    # -----------------------------------------------------
    # Ethereum-style address protection
    # -----------------------------------------------------

    if address.lower().startswith("0x"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ethereum-style address detected. "
                "Please enter a Bitcoin address."
            )
        )

    address = address.strip()

    if not address:
        raise HTTPException(
            status_code=400,
            detail="Bitcoin address is required."
        )

    try:

        async with httpx.AsyncClient(
            timeout=30,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            # -------------------------------------------------
            # 1. Check cached complete wallet history
            # -------------------------------------------------

            cached = get_cached_wallet(address)

            if cached:

                all_transactions = cached["transactions"]

                incoming_transactions = cached[
                    "incoming"
                ]

                outgoing_transactions = cached[
                    "outgoing"
                ]

            else:

                # ---------------------------------------------
                # 2. Get wallet-level statistics
                # ---------------------------------------------

                try:
                    address_response = await client.get(
                        f"{MEMPOOL_API}/address/{address}"
                    )

                except httpx.RequestError as e:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Mempool.space connection failed: "
                            f"{str(e)}"
                        )
                    )

                if address_response.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail="Bitcoin address not found."
                    )

                if address_response.status_code == 429:
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            "Mempool.space rate limit reached. "
                            "Please try again later."
                        )
                    )

                try:
                    address_response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Mempool.space address lookup "
                            f"failed: {str(e)}"
                        )
                    )

                address_details = address_response.json()

                chain_stats = address_details.get(
                    "chain_stats",
                    {}
                )

                mempool_stats = address_details.get(
                    "mempool_stats",
                    {}
                )

                # ---------------------------------------------
                # 3. Fetch complete confirmed transaction history
                # ---------------------------------------------

                raw_transactions = await fetch_wallet_history(
                    client,
                    address
                )

                # ---------------------------------------------
                # 4. Normalize transactions for CryptoIntel
                # ---------------------------------------------

                all_transactions = [
                    normalize_transaction(tx)
                    for tx in raw_transactions
                ]

                # ---------------------------------------------
                # 5. Calculate wallet-wide direction counts
                # ---------------------------------------------

                (
                    incoming_transactions,
                    outgoing_transactions
                ) = calculate_transaction_directions(
                    address,
                    all_transactions
                )

                # ---------------------------------------------
                # 6. Cache complete wallet
                # ---------------------------------------------

                save_cached_wallet(
                    address,
                    all_transactions,
                    incoming_transactions,
                    outgoing_transactions
                )

            # -------------------------------------------------
            # 7. Get fresh wallet statistics
            #
            # These values are available from Mempool.
            # For cached data, the transaction history remains
            # cached while page navigation stays fast.
            # -------------------------------------------------

            if cached:
                try:
                    address_response = await client.get(
                        f"{MEMPOOL_API}/address/{address}"
                    )

                    if address_response.status_code == 200:
                        address_details = (
                            address_response.json()
                        )

                        chain_stats = address_details.get(
                            "chain_stats",
                            {}
                        )

                        mempool_stats = address_details.get(
                            "mempool_stats",
                            {}
                        )
                    else:
                        chain_stats = {}
                        mempool_stats = {}

                except Exception:
                    chain_stats = {}
                    mempool_stats = {}

            # -------------------------------------------------
            # 8. Calculate wallet balance
            # -------------------------------------------------

            funded_sum = int(
                chain_stats.get(
                    "funded_txo_sum",
                    0
                )
            )

            spent_sum = int(
                chain_stats.get(
                    "spent_txo_sum",
                    0
                )
            )

            final_balance = (
                funded_sum - spent_sum
            )

            # -------------------------------------------------
            # 9. Confirmed transaction count
            # -------------------------------------------------

            transaction_count = int(
                chain_stats.get(
                    "tx_count",
                    len(all_transactions)
                )
            )

            # -------------------------------------------------
            # 10. Mempool statistics
            # -------------------------------------------------

            mempool_funded = int(
                mempool_stats.get(
                    "funded_txo_count",
                    0
                )
            )

            mempool_spent = int(
                mempool_stats.get(
                    "spent_txo_count",
                    0
                )
            )

            # -------------------------------------------------
            # 11. Existing CryptoIntel pagination
            #
            # Frontend expects:
            #
            # page=1 -> 100
            # page=2 -> 100
            # page=3 -> 100
            # page=4 -> 30
            #
            # Mempool internally uses 25-item cursor pages,
            # but we expose the existing 100-item API.
            # -------------------------------------------------

            offset = (page - 1) * limit

            page_transactions = all_transactions[
                offset:offset + limit
            ]

            has_more = (
                offset + len(page_transactions)
                < transaction_count
            )

            # -------------------------------------------------
            # 12. Return CryptoIntel wallet response
            # -------------------------------------------------

            return {
                "address": address,
                "network": "Bitcoin",
                "status": "LIVE",

                "balance": {
                    "funded": funded_sum,
                    "spent": spent_sum,
                    "balance": final_balance
                },

                "activity": {
                    "confirmed_transactions": (
                        transaction_count
                    ),
                    "funded_transactions": (
                        incoming_transactions
                    ),
                    "spent_transactions": (
                        outgoing_transactions
                    ),
                    "mempool_funded": (
                        mempool_funded
                    ),
                    "mempool_spent": (
                        mempool_spent
                    )
                },

                "transactions": page_transactions,

                "pagination": {
                    "page": page,
                    "limit": limit,
                    "offset": offset,
                    "total": transaction_count,
                    "has_more": has_more
                },

                "source": "Mempool.space Bitcoin API"
            }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Wallet lookup failed: {str(e)}"
        )