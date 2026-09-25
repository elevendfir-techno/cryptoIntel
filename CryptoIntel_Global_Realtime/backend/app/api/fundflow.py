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
# MEMPOOL.SPACE — BITCOIN
# =========================================================

BITCOIN_API = "https://mempool.space/api"


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

REQUEST_DELAY = 1.0
RETRY_AFTER_429 = 10.0


# =========================================================
# ETHEREUM CONCURRENCY
# =========================================================

# Independent Ethereum API requests can safely run in
# parallel. Keep concurrency bounded to reduce the chance
# of Blockscout rate limiting.

ETHEREUM_REQUEST_CONCURRENCY = 5
ETHEREUM_METADATA_CONCURRENCY = 5


# =========================================================
# IN-MEMORY CACHE
# =========================================================

WALLET_CACHE = {}

CACHE_TTL = 300


# =========================================================
# BITCOIN ADDRESS VALIDATION
# =========================================================

def is_bitcoin_address(address: str) -> bool:

    if not address:
        return False

    if address.lower().startswith("0x"):
        return False

    return 26 <= len(address) <= 62


# =========================================================
# BITCOIN WALLET DATA — MEMPOOL
# =========================================================

async def get_wallet_data(
    client,
    address
):

    now = time.time()

    cached = WALLET_CACHE.get(address)

    if cached and cached["expires"] > now:
        return cached["data"], False, True

    all_transactions = []

    last_txid = None

    try:

        while len(all_transactions) < MAX_TXS_PER_WALLET:

            if last_txid:

                response = await client.get(
                    f"{BITCOIN_API}/address/{address}/txs/chain/"
                    f"{last_txid}",
                    timeout=30
                )

            else:

                response = await client.get(
                    f"{BITCOIN_API}/address/{address}/txs/chain",
                    timeout=30
                )

            if response.status_code == 429:

                print(
                    f"Mempool rate limit for {address}. "
                    f"Waiting {RETRY_AFTER_429}s..."
                )

                await asyncio.sleep(
                    RETRY_AFTER_429
                )

                if last_txid:

                    response = await client.get(
                        f"{BITCOIN_API}/address/{address}/txs/chain/"
                        f"{last_txid}",
                        timeout=30
                    )

                else:

                    response = await client.get(
                        f"{BITCOIN_API}/address/{address}/txs/chain",
                        timeout=30
                    )

                if response.status_code == 429:
                    return None, True, False

            if response.status_code == 404:
                return None, False, False

            response.raise_for_status()

            page = response.json()

            if not isinstance(page, list):
                break

            if not page:
                break

            all_transactions.extend(page)

            if len(page) < 25:
                break

            next_txid = page[-1].get("txid")

            if not next_txid:
                break

            if next_txid == last_txid:
                break

            last_txid = next_txid

            if len(all_transactions) >= MAX_TXS_PER_WALLET:
                break

            await asyncio.sleep(
                REQUEST_DELAY
            )

        transactions = all_transactions[
            :MAX_TXS_PER_WALLET
        ]

        data = {
            "txs": transactions,
            "source": "Mempool.space Bitcoin API"
        }

        WALLET_CACHE[address] = {
            "data": data,
            "expires": time.time() + CACHE_TTL
        }

        return data, False, False

    except httpx.HTTPStatusError as e:

        if e.response.status_code == 429:
            return None, True, False

        raise


# =========================================================
# BLOCKSCOUT PAGINATION
# =========================================================

async def blockscout_paginated_request(
    client,
    endpoint,
    max_pages=ETHEREUM_MAX_PAGES
):

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
            params=params,
            timeout=30
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
# ETHEREUM TOKEN METADATA
# =========================================================

async def get_ethereum_token_metadata(
    client,
    token_address
):

    if not token_address:
        return {}

    try:

        response = await client.get(
            f"{ETHEREUM_API}/?module=token"
            f"&action=getToken"
            f"&contractaddress={token_address}",
            timeout=30
        )

        if response.status_code == 404:
            return {}

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            return {}

        result = data.get("result")

        if not isinstance(result, dict):
            return {}

        name = result.get("name")
        symbol = result.get("symbol")
        decimals = result.get("decimals")

        if decimals is not None:

            try:
                decimals = int(decimals)

            except (TypeError, ValueError):
                decimals = None

        return {

            "name":
                name,

            "symbol":
                symbol,

            "decimals":
                decimals,

            "contract_address":
                result.get(
                    "contractAddress"
                ),

            "type":
                result.get("type"),

            "cataloged":
                result.get("cataloged")

        }

    except Exception as e:

        print(
            f"Ethereum token metadata lookup failed "
            f"for {token_address}: {e}"
        )

        return {}


# =========================================================
# ETHEREUM ADDRESS DETAILS
# =========================================================

async def get_ethereum_address_details(
    client,
    address
):

    response = await client.get(
        f"{ETHEREUM_API}/addresses/{address}",
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# SAFE BLOCKSCOUT ADDRESS EXTRACTION
# =========================================================

def get_blockscout_address(data):

    if isinstance(data, str):
        return data

    if not isinstance(data, dict):
        return None

    return (
        data.get("hash")
        or data.get("address_hash")
        or data.get("address")
    )


# =========================================================
# SAFE BLOCKSCOUT TRANSACTION HASH
# =========================================================

def get_transaction_hash(data):

    if not isinstance(data, dict):
        return None

    return (
        data.get("hash")
        or data.get("transaction_hash")
        or data.get("tx_hash")
    )


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

    # Global investigation-level token metadata cache.
    token_metadata_cache = {}

    wallets_per_hop = {
        0: 1
    }

    # =====================================================
    # CONCURRENCY CONTROLS
    # =====================================================

    request_semaphore = asyncio.Semaphore(
        ETHEREUM_REQUEST_CONCURRENCY
    )

    metadata_semaphore = asyncio.Semaphore(
        ETHEREUM_METADATA_CONCURRENCY
    )

    async def limited_metadata_lookup(
        token_address
    ):

        async with metadata_semaphore:

            return await get_ethereum_token_metadata(
                client,
                token_address
            )

    # =====================================================
    # ROOT ADDRESS DETAILS
    # =====================================================

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
        # PARALLEL DATA COLLECTION
        # =================================================
        #
        # Previously:
        #
        # transactions -> wait
        # token transfers -> wait
        #
        # Now:
        #
        # transactions -----\
        #                    > parallel
        # token transfers ---/
        #
        # =================================================

        async def load_transactions():

            try:

                async with request_semaphore:

                    return await get_ethereum_transactions(
                        client,
                        current_address
                    )

            except Exception as e:

                print(
                    f"Ethereum transaction lookup failed "
                    f"for {current_address}: {e}"
                )

                return []

        async def load_token_transfers():

            try:

                async with request_semaphore:

                    return await get_ethereum_token_transfers(
                        client,
                        current_address
                    )

            except Exception as e:

                print(
                    f"Ethereum token transfer lookup failed "
                    f"for {current_address}: {e}"
                )

                return []

        transactions, token_transfers = await asyncio.gather(
            load_transactions(),
            load_token_transfers()
        )

        transactions = transactions[
            :MAX_TXS_PER_WALLET
        ]

        token_transfers = token_transfers[
            :ETHEREUM_MAX_TOKEN_TRANSFERS
        ]

        # =================================================
        # PRE-COLLECT TOKEN ADDRESSES
        # =================================================
        #
        # Instead of requesting metadata one-by-one while
        # processing every transfer, first collect unique
        # token addresses.
        #
        # =================================================

        token_addresses = set()

        for transfer in token_transfers:

            token_data = transfer.get("token") or {}

            if not isinstance(token_data, dict):
                token_data = {}

            token_address = (
                token_data.get("address")
                or token_data.get("hash")
                or token_data.get("address_hash")
                or transfer.get("token_address")
            )

            if token_address:

                token_addresses.add(
                    token_address.lower()
                )

        # =================================================
        # PARALLEL TOKEN METADATA
        # =================================================

        metadata_addresses_to_fetch = [

            token_address

            for token_address in token_addresses

            if token_address
            not in token_metadata_cache
        ]

        if metadata_addresses_to_fetch:

            metadata_results = await asyncio.gather(

                *[
                    limited_metadata_lookup(
                        token_address
                    )

                    for token_address
                    in metadata_addresses_to_fetch
                ],

                return_exceptions=True
            )

            for (
                token_address,
                metadata
            ) in zip(
                metadata_addresses_to_fetch,
                metadata_results
            ):

                if isinstance(
                    metadata,
                    Exception
                ):

                    print(
                        "Ethereum token metadata "
                        f"parallel lookup failed for "
                        f"{token_address}: {metadata}"
                    )

                    token_metadata_cache[
                        token_address
                    ] = {}

                else:

                    token_metadata_cache[
                        token_address
                    ] = metadata

        # =================================================
        # NATIVE ETH TRANSACTIONS
        # =================================================

        for tx in transactions:

            from_address = get_blockscout_address(
                tx.get("from")
            )

            to_address = get_blockscout_address(
                tx.get("to")
            )

            if not from_address or not to_address:
                continue

            tx_hash = get_transaction_hash(tx)

            if not tx_hash:
                continue

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
            # TRANSACTION CLASSIFICATION
            # =============================================

            tx_method = (
                tx.get("method")
                or tx.get("method_name")
                or tx.get("function_name")
            )

            has_native_value = (
                value_wei > 0
            )

            if has_native_value:

                transfer_type = "native"
                edge_type = "native"
                asset = "ETH"

            else:

                transfer_type = "contract_interaction"
                edge_type = "contract_interaction"
                asset = "ETH"

            # =============================================
            # ETHEREUM EDGE
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

                "txid":
                    tx_hash,

                "hash":
                    tx_hash,

                "asset":
                    asset,

                "token_symbol":
                    "ETH",

                "token_name":
                    "Ethereum",

                "token_address":
                    None,

                "value":
                    value_eth,

                "value_eth":
                    value_eth,

                "value_raw":
                    str(raw_value),

                "decimals":
                    18,

                "direction":
                    direction,

                "transfer_type":
                    transfer_type,

                "type":
                    edge_type,

                "method":
                    tx_method,

                "hop":
                    next_hop

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

        for transfer in token_transfers:

            from_address = get_blockscout_address(
                transfer.get("from")
            )

            to_address = get_blockscout_address(
                transfer.get("to")
            )

            if not from_address or not to_address:
                continue

            tx_hash = get_transaction_hash(
                transfer
            )

            if not tx_hash:
                continue

            # =============================================
            # TOKEN INFORMATION
            # =============================================

            token_data = transfer.get("token") or {}

            if not isinstance(token_data, dict):
                token_data = {}

            token_name = (
                token_data.get("name")
                or transfer.get("token_name")
            )

            token_symbol = (
                token_data.get("symbol")
                or transfer.get("token_symbol")
            )

            token_address = (
                token_data.get("address")
                or token_data.get("hash")
                or token_data.get("address_hash")
                or transfer.get("token_address")
            )

            # =============================================
            # TOKEN METADATA ENRICHMENT
            # =============================================

            if token_address:

                token_key = token_address.lower()

                metadata = token_metadata_cache.get(
                    token_key,
                    {}
                )

                if not token_name:
                    token_name = (
                        metadata.get("name")
                    )

                if not token_symbol:
                    token_symbol = (
                        metadata.get("symbol")
                    )

                metadata_decimals = (
                    metadata.get("decimals")
                )

            else:

                metadata_decimals = None

            # =============================================
            # TOKEN VALUE
            # =============================================

            total_data = (
                transfer.get("total")
                or {}
            )

            if isinstance(total_data, dict):

                raw_token_value = (
                    total_data.get("value")
                    if total_data.get("value") is not None
                    else total_data.get("amount")
                )

                transfer_decimals = (
                    total_data.get("decimals")
                )

            else:

                raw_token_value = str(
                    total_data
                )

                transfer_decimals = None

            if raw_token_value is None:
                raw_token_value = "0"

            # IMPORTANT:
            # Do not use "or" here.
            # 0 is a valid ERC-20 decimals value.

            decimals_value = (
                metadata_decimals
                if metadata_decimals is not None
                else (
                    token_data.get("decimals")
                    if token_data.get("decimals") is not None
                    else (
                        transfer_decimals
                        if transfer_decimals is not None
                        else transfer.get("decimals")
                    )
                )
            )

            decimals = None

            try:

                if decimals_value is not None:

                    decimals = int(
                        decimals_value
                    )

                    if (
                        decimals < 0
                        or decimals > 36
                    ):
                        decimals = None

            except (
                TypeError,
                ValueError
            ):

                decimals = None

            # =============================================
            # HUMAN READABLE TOKEN VALUE
            # =============================================

            token_value = None

            if decimals is not None:

                try:

                    raw_integer = int(
                        raw_token_value
                    )

                    token_value = (
                        raw_integer
                        / (10 ** decimals)
                    )

                except (
                    TypeError,
                    ValueError,
                    OverflowError
                ):

                    token_value = None

            # =============================================
            # SAFE TOKEN LABEL
            # =============================================

            if not token_symbol:
                token_symbol = "UNKNOWN"

            if not token_name:
                token_name = "Unknown Token"

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
                    "id":
                        counterparty,

                    "address":
                        counterparty,

                    "network":
                        "Ethereum",

                    "hop":
                        next_hop,

                    "type":
                        "wallet"
                }

                wallets_per_hop[next_hop] += 1

            # =============================================
            # ERC-20 EDGE
            # =============================================

            edges.append({

                "id":
                    f"erc20-{tx_hash}-{current_address}-"
                    f"{token_address or 'unknown'}",

                "source":
                    from_address,

                "target":
                    to_address,

                "transaction_hash":
                    tx_hash,

                "txid":
                    tx_hash,

                "hash":
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

                "value_token":
                    token_value,

                "value_raw":
                    str(raw_token_value),

                "decimals":
                    decimals,

                "metadata_status":
                    (
                        "VERIFIED"
                        if (
                            token_address
                            and decimals is not None
                            and token_symbol != "UNKNOWN"
                        )
                        else "PARTIAL"
                    ),

                "direction":
                    direction,

                "transfer_type":
                    "token",

                "type":
                    "token",

                "hop":
                    next_hop
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
            edge.get("token_address"),
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

        edge.get("transaction_hash")

        for edge in final_edges

        if edge.get("transaction_hash")
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

        if edge.get("type") == "native"
    ]

    contract_interaction_edges = [

        edge

        for edge in final_edges

        if edge.get("type") == "contract_interaction"
    ]

    token_edges = [

        edge

        for edge in final_edges

        if edge.get("type") == "token"
    ]

    # =====================================================
    # FINAL ETHEREUM RESPONSE
    # =====================================================

    return {

        "root":
            root_address,

        "root_wallet":
            root_address,

        "network":
            "Ethereum",

        "status":
            "LIVE",

        "message":
            "Live Ethereum fund-flow analysis completed.",

        "address_details":
            address_details,

        "hops_requested":
            hops,

        "hops_traced":
            hops_traced,

        "wallet_count":
            len(nodes),

        "wallets":
            len(nodes),

        "edge_count":
            len(final_edges),

        "edges":
            final_edges,

        "transactions_scanned":
            len(unique_transaction_hashes),

        "transactions":
            len(unique_transaction_hashes),

        "native_eth_transfers":
            len(native_edges),

        "contract_interactions":
            len(contract_interaction_edges),

        "erc20_transfers":
            len(token_edges),

        "nodes":
            list(nodes.values()),

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

        if not is_ethereum_address(address):

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

    if not is_bitcoin_address(address):

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

                        txid = tx.get("txid")

                        if not txid:
                            continue

                        # =================================
                        # INPUTS
                        # =================================

                        for vin in tx.get(
                            "vin",
                            []
                        ):

                            prevout = (
                                vin.get("prevout")
                                or {}
                            )

                            source_address = (
                                prevout.get(
                                    "scriptpubkey_address"
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
                                    prevout.get(
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

                                "value_btc":
                                    value_sats / 100000000,

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
                            "vout",
                            []
                        ):

                            destination_address = (
                                vout.get(
                                    "scriptpubkey_address"
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

                                "value_btc":
                                    value_sats / 100000000,

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

            # =================================================
            # HOPS
            # =================================================

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

            # =================================================
            # STATUS
            # =================================================

            if rate_limited:

                status = "PARTIAL"

                message = (
                    "Mempool.space rate limit reached. "
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
                    "Mempool.space Bitcoin API"
            }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Fund flow lookup failed: {str(e)}"
            )
        )