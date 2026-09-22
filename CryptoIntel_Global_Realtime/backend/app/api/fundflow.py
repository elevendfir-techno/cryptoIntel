from fastapi import APIRouter, HTTPException
import asyncio
import time
import httpx
import re


router = APIRouter(
    prefix="/api/fundflow",
    tags=["fund-flow"]
)


# =========================================================
# BLOCKCHAIN.COM — BITCOIN
# =========================================================

BITCOIN_API = "https://blockchain.info"


# =========================================================
# BLOCKSCOUT — ETHEREUM
# =========================================================

ETHEREUM_API = "https://eth.blockscout.com/api/v2"
ETHEREUM_MAX_TXS = 10
ETHEREUM_MAX_TOKEN_TRANSFERS = 10

# =========================================================
# ETHEREUM ADDRESS VALIDATION
# =========================================================

def is_ethereum_address(address: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", address))


# =========================================================
# INVESTIGATION LIMITS
# =========================================================

MAX_HOPS = 2
MAX_WALLETS_PER_HOP = 3
MAX_TXS_PER_WALLET = 10


# =========================================================
# PUBLIC API PROTECTION
# =========================================================

REQUEST_DELAY = 10.0
RETRY_AFTER_429 = 30.0


# =========================================================
# IN-MEMORY CACHE
# =========================================================

# address ->
# {
#     "data": {...},
#     "expires": timestamp
# }

WALLET_CACHE = {}

CACHE_TTL = 300


# =========================================================
# WALLET DATA
# =========================================================

async def get_wallet_data(client, address):
    """
    Get Bitcoin wallet data from Blockchain.com.

    Returns:
        (data, rate_limited, from_cache)
    """

    now = time.time()

    # -----------------------------------------------------
    # CACHE CHECK
    # -----------------------------------------------------

    cached = WALLET_CACHE.get(address)

    if cached and cached["expires"] > now:
        return cached["data"], False, True

    # -----------------------------------------------------
    # API REQUEST
    # -----------------------------------------------------

    response = await client.get(
        f"{BITCOIN_API}/rawaddr/{address}",
        params={
            "limit": MAX_TXS_PER_WALLET
        }
    )

    # -----------------------------------------------------
    # RATE LIMIT
    # -----------------------------------------------------

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
            return None, True, False

    # -----------------------------------------------------
    # NOT FOUND
    # -----------------------------------------------------

    if response.status_code == 404:
        return None, False, False

    # -----------------------------------------------------
    # OTHER HTTP ERRORS
    # -----------------------------------------------------

    response.raise_for_status()

    # -----------------------------------------------------
    # PARSE RESPONSE
    # -----------------------------------------------------

    data = response.json()

    # -----------------------------------------------------
    # SAVE CACHE
    # -----------------------------------------------------

    WALLET_CACHE[address] = {
        "data": data,
        "expires": time.time() + CACHE_TTL
    }

    return data, False, False

# =========================================================
# ETHEREUM TRANSACTIONS
# =========================================================

async def get_ethereum_transactions(client, address):
    response = await client.get(
        f"{ETHEREUM_API}/addresses/{address}/transactions",
        params={
            "items_count": ETHEREUM_MAX_TXS
        }
    )

    response.raise_for_status()

    data = response.json()

    return data.get("items", [])

# =========================================================
# ETHEREUM TOKEN TRANSFERS
# =========================================================

async def get_ethereum_token_transfers(client, address):
    response = await client.get(
        f"{ETHEREUM_API}/addresses/{address}/token-transfers",
        params={
            "items_count": ETHEREUM_MAX_TOKEN_TRANSFERS
        }
    )

    response.raise_for_status()

    data = response.json()

    return data.get("items", [])

# =========================================================
# ETHEREUM FUND FLOW
# =========================================================

async def ethereum_fundflow(client, root_address, hops):
    nodes = {}
    edges = []
    visited = set()
    queue = []

    # Root wallet
    nodes[root_address] = {
        "id": root_address,
        "address": root_address,
        "network": "Ethereum",
        "hop": 0,
        "type": "wallet"
    }

    queue.append((root_address, 0))
    visited.add(root_address)

    while queue:

        current_address, current_hop = queue.pop(0)

        if current_hop >= hops:
            continue

        # -------------------------------------------------
        # NATIVE ETH TRANSACTIONS
        # -------------------------------------------------

        try:
            transactions = await get_ethereum_transactions(
                client,
                current_address
            )
        except Exception:
            transactions = []

        for tx in transactions:

            from_data = tx.get("from") or {}
            to_data = tx.get("to") or {}

            from_address = (
                from_data.get("hash")
                if isinstance(from_data, dict)
                else None
            )

            to_address = (
                to_data.get("hash")
                if isinstance(to_data, dict)
                else None
            )

            tx_hash = (
                tx.get("hash")
                or tx.get("transaction_hash")
            )

            if not from_address or not to_address:
                continue

            if not tx_hash:
                tx_hash = "unknown"

            # Blockscout native value is normally in wei
            raw_value = tx.get("value", "0")

            try:
                value_wei = int(raw_value)
            except (TypeError, ValueError):
                value_wei = 0

            value_eth = value_wei / 10**18

            # Determine direction relative to current wallet
            if from_address.lower() == current_address.lower():
                counterparty = to_address
                direction = "OUTGOING"
            else:
                counterparty = from_address
                direction = "INCOMING"

            # Add counterparty node
            if counterparty not in nodes:
                nodes[counterparty] = {
                    "id": counterparty,
                    "address": counterparty,
                    "network": "Ethereum",
                    "hop": current_hop + 1,
                    "type": "wallet"
                }

            # Add edge
            edges.append({
                "id": f"eth-{tx_hash}-{current_address}",
                "source": from_address,
                "target": to_address,
                "transaction_hash": tx_hash,
                "asset": "ETH",
                "value": value_eth,
                "value_raw": str(raw_value),
                "direction": direction,
                "hop": current_hop + 1,
                "type": "native"
            })

            # Queue next wallet
            if (
                counterparty not in visited
                and current_hop + 1 < hops
            ):
                visited.add(counterparty)
                queue.append(
                    (counterparty, current_hop + 1)
                )

        # -------------------------------------------------
        # ERC-20 TOKEN TRANSFERS
        # -------------------------------------------------

        try:
            token_transfers = await get_ethereum_token_transfers(
                client,
                current_address
            )
        except Exception:
            token_transfers = []

        for transfer in token_transfers:

            from_data = transfer.get("from") or {}
            to_data = transfer.get("to") or {}

            from_address = (
                from_data.get("hash")
                if isinstance(from_data, dict)
                else None
            )

            to_address = (
                to_data.get("hash")
                if isinstance(to_data, dict)
                else None
            )

            if not from_address or not to_address:
                continue

            tx_hash = (
                transfer.get("transaction_hash")
                or transfer.get("tx_hash")
                or transfer.get("hash")
                or "unknown"
            )

            # -------------------------------------------------
            # TOKEN INFORMATION
            # -------------------------------------------------

            token_data = transfer.get("token") or {}

            if not isinstance(token_data, dict):
                token_data = {}

            token_name = token_data.get("name")
            token_symbol = token_data.get("symbol")
            token_address = token_data.get("address")

            if not token_address:
                token_address = token_data.get("hash")

            # -------------------------------------------------
            # TOKEN AMOUNT
            # -------------------------------------------------

            total_data = transfer.get("total") or {}

            if isinstance(total_data, dict):
                raw_token_value = (
                    total_data.get("value")
                    or total_data.get("amount")
                    or "0"
                )
            else:
                raw_token_value = str(total_data)

            decimals = (
                token_data.get("decimals")
                or transfer.get("decimals")
                or 0
            )

            try:
                decimals = int(decimals)
            except (TypeError, ValueError):
                decimals = 0

            try:
                token_value = int(raw_token_value) / (
                    10 ** decimals
                )
            except (TypeError, ValueError, OverflowError):
                token_value = 0

            # Direction
            if from_address.lower() == current_address.lower():
                counterparty = to_address
                direction = "OUTGOING"
            else:
                counterparty = from_address
                direction = "INCOMING"

            # Add token counterparty
            if counterparty not in nodes:
                nodes[counterparty] = {
                    "id": counterparty,
                    "address": counterparty,
                    "network": "Ethereum",
                    "hop": current_hop + 1,
                    "type": "wallet"
                }

            # Add ERC-20 edge
            edges.append({
                "id": f"erc20-{tx_hash}-{current_address}",
                "source": from_address,
                "target": to_address,
                "transaction_hash": tx_hash,
                "asset": "ERC-20",
                "token_name": token_name,
                "token_symbol": token_symbol,
                "token_address": token_address,
                "value": token_value,
                "value_raw": str(raw_token_value),
                "decimals": decimals,
                "direction": direction,
                "hop": current_hop + 1,
                "type": "token"
            })

            # Queue next wallet
            if (
                counterparty not in visited
                and current_hop + 1 < hops
            ):
                visited.add(counterparty)
                queue.append(
                    (counterparty, current_hop + 1)
                )

    return {
        "network": "Ethereum",
        "status": "LIVE",
        "root_wallet": root_address,
        "hops_requested": hops,
        "hops_traced": hops,
        "wallets": len(nodes),
        "edges": len(edges),
        "transactions": len(edges),
        "nodes": list(nodes.values()),
        "edges_data": edges,
        "source": "Blockscout Ethereum API"
    }


# =========================================================
# FUND FLOW
# =========================================================

@router.get("/{address}")
async def fundflow(
    address: str,
    network: str = "bitcoin",
    hops: int = 2
):

    # =====================================================
    # NETWORK VALIDATION
    # =====================================================

    network = network.lower()

    if network not in ("bitcoin", "ethereum"):

        raise HTTPException(
            status_code=400,
            detail=(
                "Supported fund-flow networks: "
                "Bitcoin and Ethereum."
            )
        )

    # =====================================================
    # ETHEREUM FUND FLOW
    # =====================================================

    if network == "ethereum":

        if not is_ethereum_address(address):

            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum address."
            )

        hops = max(
            1,
            min(hops, MAX_HOPS)
        )

        try:

            async with httpx.AsyncClient(
                timeout=30
            ) as client:

                return await ethereum_fundflow(
                    client,
                    address,
                    hops
                )

        except HTTPException:
            raise

        except Exception as e:

            raise HTTPException(
                status_code=502,
                detail=(
                    f"Ethereum fund flow lookup failed: {str(e)}"
                )
            )


    # =====================================================
    # ADDRESS VALIDATION
    # =====================================================

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


    # =====================================================
    # CONTROL HOPS
    # =====================================================

    hops = max(
        1,
        min(hops, MAX_HOPS)
    )


    try:

        async with httpx.AsyncClient(
            timeout=30
        ) as client:

            # =================================================
            # GRAPH STORAGE
            # =================================================

            nodes = {}
            edges = []


            # =================================================
            # ROOT WALLET
            # =================================================

            nodes[address] = {
                "id": address,
                "type": "wallet",
                "label": address[:12] + "...",
                "hop": 0
            }


            # =================================================
            # IMPORTANT:
            #
            # processed_wallets means:
            # wallet has already been investigated.
            #
            # A discovered wallet is NOT marked processed
            # until that wallet is actually analysed.
            # =================================================

            processed_wallets = set()

            current_wallets = [address]


            # =================================================
            # STATISTICS
            # =================================================

            total_transactions = 0

            requests_made = 0

            cached_requests = 0

            rate_limited = False


            # =================================================
            # HOP ANALYSIS
            # =================================================

            for current_hop in range(
                1,
                hops + 1
            ):

                # -------------------------------------------------
                # Wallets to analyse in the NEXT hop
                # -------------------------------------------------

                next_wallets = []


                # =================================================
                # PROCESS CURRENT HOP WALLETS
                # =================================================

                for wallet_address in current_wallets:

                    # -------------------------------------------------
                    # DO NOT PROCESS SAME WALLET TWICE
                    # -------------------------------------------------

                    if wallet_address in processed_wallets:
                        continue


                    # -------------------------------------------------
                    # MARK AS PROCESSED
                    #
                    # This is intentionally done here,
                    # NOT when the wallet is discovered.
                    # -------------------------------------------------

                    processed_wallets.add(
                        wallet_address
                    )


                    # =================================================
                    # REQUEST DELAY
                    # =================================================

                    if requests_made > 0:

                        await asyncio.sleep(
                            REQUEST_DELAY
                        )


                    # =================================================
                    # GET WALLET DATA
                    # =================================================

                    (
                        wallet_data,
                        limited,
                        from_cache
                    ) = await get_wallet_data(
                        client,
                        wallet_address
                    )


                    # -------------------------------------------------
                    # RATE LIMIT
                    # -------------------------------------------------

                    if limited:

                        rate_limited = True

                        break


                    # -------------------------------------------------
                    # REQUEST STATISTICS
                    # -------------------------------------------------

                    if from_cache:

                        cached_requests += 1

                    else:

                        requests_made += 1


                    # -------------------------------------------------
                    # WALLET NOT FOUND
                    # -------------------------------------------------

                    if not wallet_data:
                        continue


                    # =================================================
                    # TRANSACTIONS
                    # =================================================

                    transactions = wallet_data.get(
                        "txs",
                        []
                    )[:MAX_TXS_PER_WALLET]


                    total_transactions += len(
                        transactions
                    )


                    # =================================================
                    # TRANSACTION ANALYSIS
                    # =================================================

                    for tx in transactions:

                        txid = tx.get("hash")


                        if not txid:
                            continue


                        # =================================================
                        # INPUTS
                        #
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


                            # -------------------------------------------------
                            # VALUE
                            # -------------------------------------------------

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


                            # =================================================
                            # SOURCE NODE
                            # =================================================

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

                            else:

                                # Keep the earliest discovered hop

                                existing_hop = nodes[
                                    source_address
                                ].get(
                                    "hop",
                                    current_hop
                                )

                                if current_hop < existing_hop:

                                    nodes[
                                        source_address
                                    ]["hop"] = current_hop


                            # =================================================
                            # INCOMING EDGE
                            # =================================================

                            edges.append({

                                "source":
                                    source_address,

                                "target":
                                    wallet_address,

                                "txid":
                                    txid,

                                "value_sats":
                                    value_sats,

                                "type":
                                    "incoming",

                                "hop":
                                    current_hop

                            })


                            # =================================================
                            # QUEUE SOURCE FOR NEXT HOP
                            # =================================================

                            if (

                                source_address
                                not in processed_wallets

                                and source_address
                                not in next_wallets

                                and len(next_wallets)
                                < MAX_WALLETS_PER_HOP

                            ):

                                next_wallets.append(
                                    source_address
                                )


                        # =================================================
                        # OUTPUTS
                        #
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


                            # -------------------------------------------------
                            # VALUE
                            # -------------------------------------------------

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


                            # =================================================
                            # DESTINATION NODE
                            # =================================================

                            if destination_address not in nodes:

                                nodes[destination_address] = {
                                    "id":
                                        destination_address,

                                    "type":
                                        "wallet",

                                    "label":
                                        (
                                            destination_address[:12]
                                            + "..."
                                        ),

                                    "hop":
                                        current_hop
                                }

                            else:

                                # Keep earliest hop

                                existing_hop = nodes[
                                    destination_address
                                ].get(
                                    "hop",
                                    current_hop
                                )

                                if current_hop < existing_hop:

                                    nodes[
                                        destination_address
                                    ]["hop"] = current_hop


                            # =================================================
                            # OUTGOING EDGE
                            # =================================================

                            edges.append({

                                "source":
                                    wallet_address,

                                "target":
                                    destination_address,

                                "txid":
                                    txid,

                                "value_sats":
                                    value_sats,

                                "type":
                                    "outgoing",

                                "hop":
                                    current_hop

                            })


                            # =================================================
                            # QUEUE DESTINATION FOR NEXT HOP
                            # =================================================

                            if (

                                destination_address
                                not in processed_wallets

                                and destination_address
                                not in next_wallets

                                and len(next_wallets)
                                < MAX_WALLETS_PER_HOP

                            ):

                                next_wallets.append(
                                    destination_address
                                )


                # =================================================
                # STOP IF RATE LIMITED
                # =================================================

                if rate_limited:
                    break


                # =================================================
                # PREPARE NEXT HOP
                #
                # IMPORTANT:
                #
                # DO NOT add next_wallets to a visited set here.
                #
                # They must remain available for actual analysis
                # in the next iteration.
                # =================================================

                current_wallets = next_wallets


                # =================================================
                # NO MORE WALLETS
                # =================================================

                if not current_wallets:
                    break


            # =========================================================
            # REMOVE DUPLICATE EDGES
            # =========================================================

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


            # =========================================================
            # CALCULATE HOPS TRACED
            # =========================================================

            hops_traced = max(
                [
                    node.get("hop", 0)
                    for node in nodes.values()
                ],
                default=0
            )


            hops_traced = min(
                hops,
                hops_traced
            )


            # =========================================================
            # STATUS
            # =========================================================

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


            # =========================================================
            # FINAL RESPONSE
            # =========================================================

            return {

                "root":
                    address,

                "network":
                    "Bitcoin",

                "status":
                    status,

                "message":
                    message,

                "hops_requested":
                    hops,

                "hops_traced":
                    hops_traced,

                "nodes":
                    list(
                        nodes.values()
                    ),

                "edges":
                    final_edges,

                "wallet_count":
                    len(nodes),

                "edge_count":
                    len(final_edges),

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


    # =============================================================
    # HTTP EXCEPTION
    # =============================================================

    except HTTPException:
        raise


    # =============================================================
    # OTHER ERRORS
    # =============================================================

    except Exception as e:

        raise HTTPException(

            status_code=502,

            detail=(
                f"Fund flow lookup failed: {str(e)}"
            )

        )