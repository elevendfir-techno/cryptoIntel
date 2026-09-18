from fastapi import APIRouter, HTTPException
import asyncio
import time
import httpx

router = APIRouter(
    prefix="/api/fundflow",
    tags=["fund-flow"]
)

BITCOIN_API = "https://blockchain.info"

# Conservative investigation limits
MAX_HOPS = 2
MAX_WALLETS_PER_HOP = 3
MAX_TXS_PER_WALLET = 10

# Public API protection
REQUEST_DELAY = 10.0
RETRY_AFTER_429 = 30.0

# In-memory cache:
# address -> {"data": ..., "expires": ...}
WALLET_CACHE = {}

# Cache successful wallet responses for 5 minutes
CACHE_TTL = 300


async def get_wallet_data(client, address):
    """
    Get wallet data from cache when available.
    Otherwise query Blockchain.com with controlled retry handling.
    """

    now = time.time()

    # ---------------------------------------------------------
    # CACHE CHECK
    # ---------------------------------------------------------

    cached = WALLET_CACHE.get(address)

    if cached and cached["expires"] > now:
        return cached["data"], False

    # ---------------------------------------------------------
    # API REQUEST
    # ---------------------------------------------------------

    response = await client.get(
        f"{BITCOIN_API}/rawaddr/{address}",
        params={
            "limit": MAX_TXS_PER_WALLET
        }
    )

    # ---------------------------------------------------------
    # RATE LIMIT
    # ---------------------------------------------------------

    if response.status_code == 429:

        print(
            f"Blockchain.com rate limit for {address}. "
            f"Waiting {RETRY_AFTER_429}s..."
        )

        await asyncio.sleep(RETRY_AFTER_429)

        response = await client.get(
            f"{BITCOIN_API}/rawaddr/{address}",
            params={
                "limit": MAX_TXS_PER_WALLET
            }
        )

        if response.status_code == 429:
            return None, True

    # ---------------------------------------------------------
    # NOT FOUND
    # ---------------------------------------------------------

    if response.status_code == 404:
        return None, False

    response.raise_for_status()

    data = response.json()

    # ---------------------------------------------------------
    # SAVE TO CACHE
    # ---------------------------------------------------------

    WALLET_CACHE[address] = {
        "data": data,
        "expires": time.time() + CACHE_TTL
    }

    return data, False


@router.get("/{address}")
async def fundflow(
    address: str,
    network: str = "bitcoin",
    hops: int = 2
):

    # ---------------------------------------------------------
    # NETWORK VALIDATION
    # ---------------------------------------------------------

    if network.lower() != "bitcoin":
        raise HTTPException(
            status_code=400,
            detail="Currently only Bitcoin fund flow is live."
        )

    # ---------------------------------------------------------
    # ADDRESS VALIDATION
    # ---------------------------------------------------------

    if address.lower().startswith("0x"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Ethereum-style address detected. "
                "Please enter a Bitcoin address."
            )
        )

    if len(address) < 26 or len(address) > 62:
        raise HTTPException(
            status_code=400,
            detail="Invalid Bitcoin address format."
        )

    # ---------------------------------------------------------
    # CONTROL HOPS
    # ---------------------------------------------------------

    hops = max(1, min(hops, MAX_HOPS))

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            nodes = {}
            edges = []

            # -------------------------------------------------
            # ROOT WALLET
            # -------------------------------------------------

            nodes[address] = {
                "id": address,
                "type": "wallet",
                "label": address[:12] + "...",
                "hop": 0
            }

            visited = {address}
            current_wallets = [address]

            total_transactions = 0
            requests_made = 0
            cached_requests = 0
            rate_limited = False

            # -------------------------------------------------
            # HOP ANALYSIS
            # -------------------------------------------------

            for current_hop in range(1, hops + 1):

                next_wallets = []

                for wallet_address in current_wallets:

                    # Prevent duplicate processing
                    if (
                        wallet_address in visited
                        and current_hop > 1
                    ):
                        continue

                    # -------------------------------------------------
                    # CONTROLLED REQUEST DELAY
                    # -------------------------------------------------

                    if requests_made > 0:
                        await asyncio.sleep(
                            REQUEST_DELAY
                        )

                    wallet_data, limited = await get_wallet_data(
                        client,
                        wallet_address
                    )

                    if limited:
                        rate_limited = True
                        break

                    # Determine whether cache was used
                    cache_entry = WALLET_CACHE.get(
                        wallet_address
                    )

                    if (
                        cache_entry
                        and cache_entry["expires"] > time.time()
                    ):
                        cached_requests += 1

                    requests_made += 1

                    if not wallet_data:
                        continue

                    # -------------------------------------------------
                    # TRANSACTIONS
                    # -------------------------------------------------

                    transactions = wallet_data.get(
                        "txs",
                        []
                    )[:MAX_TXS_PER_WALLET]

                    total_transactions += len(
                        transactions
                    )

                    # -------------------------------------------------
                    # TRANSACTION ANALYSIS
                    # -------------------------------------------------

                    for tx in transactions:

                        txid = tx.get("hash")

                        if not txid:
                            continue

                        # =================================================
                        # INPUTS
                        # source wallet -> current wallet
                        # =================================================

                        for vin in tx.get(
                            "inputs",
                            []
                        ):

                            prev_out = (
                                vin.get("prev_out")
                                or {}
                            )

                            source_address = (
                                prev_out.get("addr")
                            )

                            if not source_address:
                                continue

                            if source_address == wallet_address:
                                continue

                            try:
                                value_sats = int(
                                    prev_out.get(
                                        "value",
                                        0
                                    )
                                )
                            except (
                                TypeError,
                                ValueError
                            ):
                                value_sats = 0

                            # Add source node
                            if source_address not in nodes:

                                nodes[source_address] = {
                                    "id": source_address,
                                    "type": "wallet",
                                    "label": (
                                        source_address[:12]
                                        + "..."
                                    ),
                                    "hop": current_hop
                                }

                            # Add incoming edge
                            edges.append({
                                "source": source_address,
                                "target": wallet_address,
                                "txid": txid,
                                "value_sats": value_sats,
                                "type": "incoming",
                                "hop": current_hop
                            })

                            # Queue for next hop
                            if (
                                source_address not in visited
                                and source_address not in next_wallets
                                and len(next_wallets)
                                < MAX_WALLETS_PER_HOP
                            ):
                                next_wallets.append(
                                    source_address
                                )

                        # =================================================
                        # OUTPUTS
                        # current wallet -> destination wallet
                        # =================================================

                        for vout in tx.get(
                            "out",
                            []
                        ):

                            destination_address = (
                                vout.get("addr")
                            )

                            if not destination_address:
                                continue

                            if destination_address == wallet_address:
                                continue

                            try:
                                value_sats = int(
                                    vout.get(
                                        "value",
                                        0
                                    )
                                )
                            except (
                                TypeError,
                                ValueError
                            ):
                                value_sats = 0

                            # Add destination node
                            if destination_address not in nodes:

                                nodes[destination_address] = {
                                    "id": destination_address,
                                    "type": "wallet",
                                    "label": (
                                        destination_address[:12]
                                        + "..."
                                    ),
                                    "hop": current_hop
                                }

                            # Add outgoing edge
                            edges.append({
                                "source": wallet_address,
                                "target": destination_address,
                                "txid": txid,
                                "value_sats": value_sats,
                                "type": "outgoing",
                                "hop": current_hop
                            })

                            # Queue for next hop
                            if (
                                destination_address not in visited
                                and destination_address not in next_wallets
                                and len(next_wallets)
                                < MAX_WALLETS_PER_HOP
                            ):
                                next_wallets.append(
                                    destination_address
                                )

                    if rate_limited:
                        break

                # -------------------------------------------------
                # STOP IF RATE LIMITED
                # -------------------------------------------------

                if rate_limited:
                    break

                # -------------------------------------------------
                # PREPARE NEXT HOP
                # -------------------------------------------------

                for wallet in next_wallets:
                    visited.add(wallet)

                current_wallets = next_wallets

                if not current_wallets:
                    break

            # ---------------------------------------------------------
            # REMOVE DUPLICATE EDGES
            # ---------------------------------------------------------

            unique_edges = {}

            for edge in edges:

                key = (
                    edge["source"],
                    edge["target"],
                    edge["txid"],
                    edge["type"],
                    edge["value_sats"]
                )

                unique_edges[key] = edge

            final_edges = list(
                unique_edges.values()
            )

            # ---------------------------------------------------------
            # STATUS
            # ---------------------------------------------------------

            if rate_limited:

                status = "PARTIAL"

                message = (
                    "Blockchain.com rate limit reached. "
                    "Cached and partial fund-flow data returned."
                )

            else:

                status = "LIVE"

                message = (
                    "Live Bitcoin fund-flow analysis completed."
                )

            # ---------------------------------------------------------
            # FINAL RESPONSE
            # ---------------------------------------------------------

            return {

                "root": address,

                "network": "Bitcoin",

                "status": status,

                "message": message,

                "hops_requested": hops,

                "hops_traced": min(
                    hops,
                    max(
                        [
                            node["hop"]
                            for node in nodes.values()
                        ],
                        default=0
                    )
                ),

                "nodes": list(
                    nodes.values()
                ),

                "edges": final_edges,

                "wallet_count": len(nodes),

                "edge_count": len(final_edges),

                "transactions_scanned":
                    total_transactions,

                "requests_made":
                    requests_made,

                "cached_requests":
                    cached_requests,

                "rate_limited":
                    rate_limited,

                "limits": {

                    "max_hops":
                        MAX_HOPS,

                    "max_wallets_per_hop":
                        MAX_WALLETS_PER_HOP,

                    "max_transactions_per_wallet":
                        MAX_TXS_PER_WALLET,

                    "request_delay_seconds":
                        REQUEST_DELAY,

                    "cache_ttl_seconds":
                        CACHE_TTL,

                    "retry_after_429_seconds":
                        RETRY_AFTER_429
                },

                "source":
                    "Blockchain.com Blockchain Data API"
            }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Fund flow lookup failed: {str(e)}"
        )