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

ETHEREUM_PAGE_SIZE = 50
ETHEREUM_MAX_PAGES = 5

ETHEREUM_MAX_TXS = 100
ETHEREUM_MAX_TOKEN_TRANSFERS = 100


# =========================================================
# ETHEREUM ADDRESS VALIDATION
# =========================================================

def is_ethereum_address(address: str) -> bool:
    return bool(
        re.fullmatch(
            r"0x[a-fA-F0-9]{40}",
            address
        )
    )


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

WALLET_CACHE = {}

CACHE_TTL = 300


# =========================================================
# BITCOIN WALLET DATA
# =========================================================

async def get_wallet_data(client, address):

    now = time.time()

    cached = WALLET_CACHE.get(address)

    if cached and cached["expires"] > now:
        return cached["data"], False, True

    response = await client.get(
        f"{BITCOIN_API}/rawaddr/{address}",
        params={
            "limit": MAX_TXS_PER_WALLET
        }
    )

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

    if response.status_code == 404:
        return None, False, False

    response.raise_for_status()

    data = response.json()

    WALLET_CACHE[address] = {
        "data": data,
        "expires": time.time() + CACHE_TTL
    }

    return data, False, False


# =========================================================
# BLOCKSCOUT PAGINATION HELPER
# =========================================================

async def blockscout_paginated_request(
    client,
    endpoint,
    max_pages=ETHEREUM_MAX_PAGES
):
    """
    Fetch Blockscout V2 paginated data.

    Blockscout returns:
        items
        next_page_params

    We continue requesting pages until:
        - no next_page_params
        - max_pages reached
        - no items
    """

    all_items = []

    page_params = None

    for _ in range(max_pages):

        params = {}

        if page_params:
            params.update(page_params)

        else:
            params["items_count"] = ETHEREUM_PAGE_SIZE

        response = await client.get(
            f"{ETHEREUM_API}{endpoint}",
            params=params
        )

        response.raise_for_status()

        data = response.json()

        items = data.get(
            "items",
            []
        )

        if not isinstance(items, list):
            items = []

        all_items.extend(items)

        next_params = data.get(
            "next_page_params"
        )

        if not next_params:
            break

        if not isinstance(next_params, dict):
            break

        page_params = next_params

        if not items:
            break

    return all_items


# =========================================================
# ETHEREUM TRANSACTIONS
# =========================================================

async def get_ethereum_transactions(
    client,
    address
):

    transactions = await blockscout_paginated_request(
        client,
        f"/addresses/{address}/transactions"
    )

    return transactions[:ETHEREUM_MAX_TXS]


# =========================================================
# ETHEREUM TOKEN TRANSFERS
# =========================================================

async def get_ethereum_token_transfers(
    client,
    address
):

    transfers = await blockscout_paginated_request(
        client,
        f"/addresses/{address}/token-transfers"
    )

    return transfers[
        :ETHEREUM_MAX_TOKEN_TRANSFERS
    ]


# =========================================================
# ETHEREUM ADDRESS DETAILS
# =========================================================

async def get_ethereum_address_details(
    client,
    address
):

    response = await client.get(
        f"{ETHEREUM_API}/addresses/{address}"
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# ETHEREUM FUND FLOW
# =========================================================

async def ethereum_fundflow(
    client,
    root_address,
    hops
):

    nodes = {}

    edges = []

    nodes[root_address] = {
        "id": root_address,
        "address": root_address,
        "network": "Ethereum",
        "hop": 0,
        "type": "wallet"
    }

    queue = [
        (
            root_address,
            0
        )
    ]

    visited = {
        root_address.lower()
    }

    wallets_per_hop = {
        0: 1
    }

    # =====================================================
    # ROOT ADDRESS DETAILS
    # =====================================================

    address_details = None

    try:

        address_details = (
            await get_ethereum_address_details(
                client,
                root_address
            )
        )

    except Exception as e:

        address_details = {
            "error": str(e)
        }

    # =====================================================
    # FUND FLOW
    # =====================================================

    while queue:

        current_address, current_hop = queue.pop(0)

        if current_hop >= hops:
            continue

        next_hop = current_hop + 1

        if next_hop not in wallets_per_hop:

            wallets_per_hop[next_hop] = 0

        # =================================================
        # NATIVE ETH TRANSACTIONS
        # =================================================

        try:

            transactions = (
                await get_ethereum_transactions(
                    client,
                    current_address
                )
            )

        except Exception:

            transactions = []

        transactions = transactions[
            :MAX_TXS_PER_WALLET
        ]

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

            if not from_address or not to_address:
                continue

            tx_hash = (
                tx.get("hash")
                or tx.get("transaction_hash")
                or "unknown"
            )

            raw_value = tx.get(
                "value",
                "0"
            )

            try:

                value_wei = int(
                    raw_value
                )

            except (
                TypeError,
                ValueError
            ):

                value_wei = 0

            value_eth = (
                value_wei / 10**18
            )

            if (
                from_address.lower()
                == current_address.lower()
            ):

                counterparty = to_address

                direction = "OUTGOING"

            else:

                counterparty = from_address

                direction = "INCOMING"

            # =============================================
            # COUNTERPARTY NODE
            # =============================================

            if counterparty not in nodes:

                if (
                    wallets_per_hop[next_hop]
                    >= MAX_WALLETS_PER_HOP
                ):
                    continue

                nodes[counterparty] = {
                    "id": counterparty,
                    "address": counterparty,
                    "network": "Ethereum",
                    "hop": next_hop,
                    "type": "wallet"
                }

                wallets_per_hop[next_hop] += 1

            # =============================================
            # ETH EDGE
            # =============================================

            edges.append({

                "id":
                    f"eth-{tx_hash}-{current_address}",

                "source":
                    from_address,

                "target":
                    to_address,

                "transaction_hash":
                    tx_hash,

                "asset":
                    "ETH",

                "value":
                    value_eth,

                "value_raw":
                    str(raw_value),

                "direction":
                    direction,

                "hop":
                    next_hop,

                "type":
                    "native"

            })

            # =============================================
            # NEXT WALLET
            # =============================================

            if (

                counterparty in nodes

                and counterparty.lower()
                not in visited

                and next_hop < hops

            ):

                visited.add(
                    counterparty.lower()
                )

                queue.append(
                    (
                        counterparty,
                        next_hop
                    )
                )

        # =================================================
        # ERC-20 TOKEN TRANSFERS
        # =================================================

        try:

            token_transfers = (
                await get_ethereum_token_transfers(
                    client,
                    current_address
                )
            )

        except Exception:

            token_transfers = []

        token_transfers = token_transfers[
            :ETHEREUM_MAX_TOKEN_TRANSFERS
        ]

        for transfer in token_transfers:

            from_data = (
                transfer.get("from")
                or {}
            )

            to_data = (
                transfer.get("to")
                or {}
            )

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
                transfer.get(
                    "transaction_hash"
                )
                or transfer.get(
                    "tx_hash"
                )
                or transfer.get(
                    "hash"
                )
                or "unknown"
            )

            # =============================================
            # TOKEN INFORMATION
            # =============================================

            token_data = (
                transfer.get("token")
                or {}
            )

            if not isinstance(
                token_data,
                dict
            ):

                token_data = {}

            token_name = token_data.get(
                "name"
            )

            token_symbol = token_data.get(
                "symbol"
            )

            token_address = (
                token_data.get(
                    "address"
                )
                or token_data.get(
                    "hash"
                )
            )

            # =============================================
            # TOKEN VALUE
            # =============================================

            total_data = (
                transfer.get("total")
                or {}
            )

            if isinstance(
                total_data,
                dict
            ):

                raw_token_value = (
                    total_data.get(
                        "value"
                    )
                    or total_data.get(
                        "amount"
                    )
                    or "0"
                )

            else:

                raw_token_value = str(
                    total_data
                )

            decimals = (
                token_data.get(
                    "decimals"
                )
                or transfer.get(
                    "decimals"
                )
                or 0
            )

            try:

                decimals = int(
                    decimals
                )

            except (
                TypeError,
                ValueError
            ):

                decimals = 0

            try:

                token_value = (
                    int(raw_token_value)
                    / (
                        10 ** decimals
                    )
                )

            except (
                TypeError,
                ValueError,
                OverflowError
            ):

                token_value = 0

            # =============================================
            # DIRECTION
            # =============================================

            if (
                from_address.lower()
                == current_address.lower()
            ):

                counterparty = to_address

                direction = "OUTGOING"

            else:

                counterparty = from_address

                direction = "INCOMING"

            # =============================================
            # TOKEN COUNTERPARTY
            # =============================================

            if counterparty not in nodes:

                if (
                    wallets_per_hop[next_hop]
                    >= MAX_WALLETS_PER_HOP
                ):
                    continue

                nodes[counterparty] = {
                    "id": counterparty,
                    "address": counterparty,
                    "network": "Ethereum",
                    "hop": next_hop,
                    "type": "wallet"
                }

                wallets_per_hop[next_hop] += 1

            # =============================================
            # TOKEN EDGE
            # =============================================

            edges.append({

                "id":
                    f"erc20-{tx_hash}-{current_address}",

                "source":
                    from_address,

                "target":
                    to_address,

                "transaction_hash":
                    tx_hash,

                "asset":
                    "ERC-20",

                "token_name":
                    token_name,

                "token_symbol":
                    token_symbol,

                "token_address":
                    token_address,

                "value":
                    token_value,

                "value_raw":
                    str(
                        raw_token_value
                    ),

                "decimals":
                    decimals,

                "direction":
                    direction,

                "hop":
                    next_hop,

                "type":
                    "token"

            })

            # =============================================
            # NEXT WALLET
            # =============================================

            if (

                counterparty in nodes

                and counterparty.lower()
                not in visited

                and next_hop < hops

            ):

                visited.add(
                    counterparty.lower()
                )

                queue.append(
                    (
                        counterparty,
                        next_hop
                    )
                )

    # =====================================================
    # REMOVE DUPLICATE EDGES
    # =====================================================

    unique_edges = {}

    for edge in edges:

        key = (

            edge.get("source"),

            edge.get("target"),

            edge.get("transaction_hash"),

            edge.get("type"),

            edge.get("value_raw")

        )

        unique_edges[key] = edge

    final_edges = list(
        unique_edges.values()
    )

    # =====================================================
    # UNIQUE TRANSACTIONS
    # =====================================================

    unique_transaction_hashes = {

        edge.get(
            "transaction_hash"
        )

        for edge in final_edges

        if edge.get(
            "transaction_hash"
        )
        and edge.get(
            "transaction_hash"
        ) != "unknown"

    }

    # =====================================================
    # HOPS
    # =====================================================

    hops_traced = max(

        [
            node.get(
                "hop",
                0
            )

            for node in nodes.values()
        ],

        default=0

    )

    hops_traced = min(
        hops,
        hops_traced
    )

    # =====================================================
    # TRANSFER TYPES
    # =====================================================

    native_edges = [

        edge

        for edge in final_edges

        if edge.get(
            "type"
        ) == "native"

    ]

    token_edges = [

        edge

        for edge in final_edges

        if edge.get(
            "type"
        ) == "token"

    ]

    # =====================================================
    # FINAL RESPONSE
    # =====================================================

    return {

        "network":
            "Ethereum",

        "status":
            "LIVE",

        "root_wallet":
            root_address,

        "address_details":
            address_details,

        "hops_requested":
            hops,

        "hops_traced":
            hops_traced,

        "wallets":
            len(nodes),

        "edges":
            len(final_edges),

        "transactions":
            len(unique_transaction_hashes),

        "native_eth_transfers":
            len(native_edges),

        "erc20_transfers":
            len(token_edges),

        "nodes":
            list(
                nodes.values()
            ),

        "edges_data":
            final_edges,

        "limits": {

            "max_hops":
                MAX_HOPS,

            "max_wallets_per_hop":
                MAX_WALLETS_PER_HOP,

            "max_transactions_per_wallet":
                MAX_TXS_PER_WALLET,

            "max_token_transfers_per_wallet":
                ETHEREUM_MAX_TOKEN_TRANSFERS,

            "ethereum_page_size":
                ETHEREUM_PAGE_SIZE,

            "ethereum_max_pages":
                ETHEREUM_MAX_PAGES

        },

        "source":
            "Blockscout Ethereum API"

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

    network = network.lower()

    # =====================================================
    # NETWORK VALIDATION
    # =====================================================

    if network not in (
        "bitcoin",
        "ethereum"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Supported fund-flow networks: "
                "Bitcoin and Ethereum."
            )
        )

    # =====================================================
    # ETHEREUM
    # =====================================================

    if network == "ethereum":

        if not is_ethereum_address(
            address
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum address."
            )

        hops = max(
            1,
            min(
                hops,
                MAX_HOPS
            )
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
                    "Ethereum fund flow lookup failed: "
                    f"{str(e)}"
                )
            )

    # =====================================================
    # BITCOIN ADDRESS VALIDATION
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
    # BITCOIN HOPS
    # =====================================================

    hops = max(
        1,
        min(
            hops,
            MAX_HOPS
        )
    )

    try:

        async with httpx.AsyncClient(
            timeout=30
        ) as client:

            nodes = {}

            edges = []

            nodes[address] = {
                "id": address,
                "type": "wallet",
                "label":
                    address[:12] + "...",
                "hop": 0
            }

            processed_wallets = set()

            current_wallets = [
                address
            ]

            total_transactions = 0

            requests_made = 0

            cached_requests = 0

            rate_limited = False

            # =================================================
            # BITCOIN HOP ANALYSIS
            # =================================================

            for current_hop in range(
                1,
                hops + 1
            ):

                next_wallets = []

                for wallet_address in current_wallets:

                    if (
                        wallet_address
                        in processed_wallets
                    ):
                        continue

                    processed_wallets.add(
                        wallet_address
                    )

                    if requests_made > 0:

                        await asyncio.sleep(
                            REQUEST_DELAY
                        )

                    (
                        wallet_data,
                        limited,
                        from_cache
                    ) = await get_wallet_data(
                        client,
                        wallet_address
                    )

                    if limited:

                        rate_limited = True

                        break

                    if from_cache:

                        cached_requests += 1

                    else:

                        requests_made += 1

                    if not wallet_data:
                        continue

                    transactions = (
                        wallet_data.get(
                            "txs",
                            []
                        )
                    )[
                        :MAX_TXS_PER_WALLET
                    ]

                    total_transactions += len(
                        transactions
                    )

                    for tx in transactions:

                        txid = tx.get(
                            "hash"
                        )

                        if not txid:
                            continue

                        # =================================
                        # INPUTS
                        # =================================

                        for vin in tx.get(
                            "inputs",
                            []
                        ):

                            prev_out = (
                                vin.get(
                                    "prev_out"
                                )
                                or {}
                            )

                            source_address = (
                                prev_out.get(
                                    "addr"
                                )
                            )

                            if not source_address:
                                continue

                            if (
                                source_address
                                == wallet_address
                            ):
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

                            if source_address not in nodes:

                                nodes[source_address] = {
                                    "id":
                                        source_address,
                                    "type":
                                        "wallet",
                                    "label":
                                        (
                                            source_address[:12]
                                            + "..."
                                        ),
                                    "hop":
                                        current_hop
                                }

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

                        # =================================
                        # OUTPUTS
                        # =================================

                        for vout in tx.get(
                            "out",
                            []
                        ):

                            destination_address = (
                                vout.get(
                                    "addr"
                                )
                            )

                            if not destination_address:
                                continue

                            if (
                                destination_address
                                == wallet_address
                            ):
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

                if rate_limited:
                    break

                current_wallets = next_wallets

                if not current_wallets:
                    break

            # =================================================
            # BITCOIN DUPLICATES
            # =================================================

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

            hops_traced = max(
                [
                    node.get(
                        "hop",
                        0
                    )
                    for node in nodes.values()
                ],
                default=0
            )

            hops_traced = min(
                hops,
                hops_traced
            )

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

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(f"Fund flow lookup failed: {str(e)}"
    )
)