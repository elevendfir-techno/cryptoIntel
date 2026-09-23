from fastapi import APIRouter, HTTPException
import asyncio
import httpx
import time

router = APIRouter(
    prefix="/api/blockchain",
    tags=["blockchain"]
)

BITCOIN_API = "https://blockchain.info"
MEMPOOL_API = "https://mempool.space/api"
ETHEREUM_RPC = "https://ethereum-rpc.publicnode.com"


# =========================================================
# BITCOIN CACHE
# =========================================================

BLOCK_CACHE = {
    "network": "Bitcoin",
    "status": "STARTING",
    "latest_height": None,
    "blocks": [],
    "count": 0,
    "source": "Blockchain.com Blockchain Data API",
    "updated_at": 0.0
}

CACHE_TTL = 60


# =========================================================
# NETWORKS
# =========================================================

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
            "status": "LIVE",
            "provider": "PublicNode Ethereum JSON-RPC"
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


# =========================================================
# FETCH BITCOIN BLOCK DATA
# =========================================================

async def fetch_block(client, height):

    try:

        response = await client.get(
            f"{BITCOIN_API}/block-height/{height}",
            params={
                "format": "json"
            }
        )

        if response.status_code != 200:
            return None

        data = response.json()

        blocks = data.get(
            "blocks",
            []
        )

        if not blocks:
            return None

        block = blocks[0]

        return {
            "hash": block.get("hash"),
            "height": block.get("height"),
            "time": block.get("time"),
            "block_index": block.get("block_index"),
            "txIndexes": block.get(
                "txIndexes",
                []
            ),
            "n_tx": block.get(
                "n_tx",
                0
            ),
            "size": block.get(
                "size",
                0
            ),
            "weight": block.get(
                "weight",
                0
            ),
            "prev_block": block.get(
                "prev_block"
            ),
            "main_chain": block.get(
                "main_chain",
                True
            )
        }

    except Exception:
        return None


# =========================================================
# FETCH LATEST BITCOIN BLOCKS
# =========================================================

async def refresh_blocks():

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            response = await client.get(
                f"{MEMPOOL_API}/blocks"
            )

            response.raise_for_status()

            data = response.json()

            if not data:
                return

            blocks = []

            for block in data[:10]:

                blocks.append({
                    "hash": block.get("id"),

                    "height":
                        block.get("height"),

                    "time":
                        block.get("timestamp"),

                    "block_index":
                        block.get("height"),

                    "txIndexes": [],

                    "n_tx":
                        block.get(
                            "tx_count",
                            0
                        ),

                    "size":
                        block.get(
                            "size",
                            0
                        ),

                    "weight":
                        block.get(
                            "weight",
                            0
                        ),

                    "prev_block":
                        block.get(
                            "previousblockhash"
                        ),

                    "main_chain": True
                })

            blocks.sort(
                key=lambda x: x.get(
                    "height",
                    0
                ),
                reverse=True
            )

            if not blocks:
                return

            latest_height = blocks[0][
                "height"
            ]

            BLOCK_CACHE[
                "network"
            ] = "Bitcoin"

            BLOCK_CACHE[
                "status"
            ] = "LIVE"

            BLOCK_CACHE[
                "latest_height"
            ] = latest_height

            BLOCK_CACHE[
                "blocks"
            ] = blocks[:10]

            BLOCK_CACHE[
                "count"
            ] = len(blocks[:10])

            BLOCK_CACHE[
                "source"
            ] = "Mempool.space Bitcoin API"

            BLOCK_CACHE[
                "updated_at"
            ] = time.time()

            print(
                f"Bitcoin blocks updated: "
                f"{latest_height}"
            )

    except Exception as e:

        print(
            f"Bitcoin block refresh error: "
            f"{e}"
        )


# =========================================================
# BITCOIN BACKGROUND BLOCK REFRESH
# =========================================================

async def block_refresh_loop():

    print(
        "Bitcoin blockchain background "
        "collector started"
    )

    while True:

        try:

            await refresh_blocks()

        except Exception as e:

            print(
                f"Blockchain background error: "
                f"{e}"
            )

        await asyncio.sleep(60)


# =========================================================
# START BITCOIN BACKGROUND COLLECTOR
# =========================================================

def start_blockchain_collector():

    return asyncio.create_task(
        block_refresh_loop()
    )


# =========================================================
# LATEST BITCOIN BLOCKS API
# =========================================================

@router.get("/bitcoin/blocks")
async def bitcoin_blocks():

    if BLOCK_CACHE["blocks"]:

        return {
            "network":
                BLOCK_CACHE["network"],

            "status":
                BLOCK_CACHE["status"],

            "latest_height":
                BLOCK_CACHE["latest_height"],

            "blocks":
                BLOCK_CACHE["blocks"],

            "count":
                BLOCK_CACHE["count"],

            "source":
                BLOCK_CACHE["source"],

            "cached": True
        }

    await refresh_blocks()

    if not BLOCK_CACHE["blocks"]:

        raise HTTPException(
            status_code=502,
            detail=(
                "Bitcoin blockchain data "
                "temporarily unavailable."
            )
        )

    return {
        "network":
            BLOCK_CACHE["network"],

        "status":
            BLOCK_CACHE["status"],

        "latest_height":
            BLOCK_CACHE["latest_height"],

        "blocks":
            BLOCK_CACHE["blocks"],

        "count":
            BLOCK_CACHE["count"],

        "source":
            BLOCK_CACHE["source"],

        "cached": True
    }


# =========================================================
# BITCOIN BLOCK DETAILS
# =========================================================

@router.get("/bitcoin/block/{block_hash}")
async def bitcoin_block_details(
    block_hash: str
):

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            response = await client.get(
                f"{MEMPOOL_API}/block/{block_hash}"
            )

        if response.status_code == 404:

            raise HTTPException(
                status_code=404,
                detail="Bitcoin block not found."
            )

        response.raise_for_status()

        block = response.json()

        return {
            "network": "Bitcoin",
            "status": "LIVE",

            "block": {
                "hash":
                    block.get("id"),

                "height":
                    block.get("height"),

                "timestamp":
                    block.get("timestamp"),

                "tx_count":
                    block.get(
                        "tx_count",
                        0
                    ),

                "size":
                    block.get(
                        "size",
                        0
                    ),

                "weight":
                    block.get(
                        "weight",
                        0
                    ),

                "version":
                    block.get("version"),

                "merkle_root":
                    block.get("merkle_root"),

                "previous_block_hash":
                    block.get(
                        "previousblockhash"
                    ),

                "nonce":
                    block.get("nonce"),

                "bits":
                    block.get("bits"),

                "difficulty":
                    block.get("difficulty")
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
                f"Block lookup failed: "
                f"{str(e)}"
            )
        )


# =========================================================
# BITCOIN TRANSACTION
# =========================================================

@router.get("/bitcoin/transaction/{txid}")
async def bitcoin_transaction(
    txid: str
):

    try:

        async with httpx.AsyncClient(
            timeout=20
        ) as client:

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
            "source":
                "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Transaction lookup failed: "
                f"{str(e)}"
            )
        )


# =========================================================
# BITCOIN ADDRESS
# =========================================================

@router.get("/bitcoin/address/{address}")
async def bitcoin_address(
    address: str
):

    if address.lower().startswith("0x"):

        raise HTTPException(
            status_code=400,
            detail=(
                "Ethereum-style address detected. "
                "Please enter a Bitcoin address."
            )
        )

    try:

        async with httpx.AsyncClient(
            timeout=20
        ) as client:

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

                "address":
                    details.get(
                        "address",
                        address
                    ),

                "hash160":
                    details.get(
                        "hash160"
                    ),

                "total_received":
                    details.get(
                        "total_received",
                        0
                    ),

                "total_sent":
                    details.get(
                        "total_sent",
                        0
                    ),

                "final_balance":
                    details.get(
                        "final_balance",
                        0
                    ),

                "transaction_count":
                    details.get(
                        "n_tx",
                        0
                    )
            },

            "transactions":
                transactions,

            "source":
                "Blockchain.com Blockchain Data API"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Address lookup failed: "
                f"{str(e)}"
            )
        )


# =========================================================
# ETHEREUM LIVE BLOCKCHAIN
# =========================================================

ETHEREUM_CACHE = {
    "network": "Ethereum",
    "status": "STARTING",
    "latest_height": None,
    "blocks": [],
    "count": 0,
    "source": "PublicNode Ethereum JSON-RPC",
    "updated_at": 0.0
}


# =========================================================
# ETHEREUM RPC
# =========================================================

async def ethereum_rpc(
    client,
    method,
    params
):

    response = await client.post(
        ETHEREUM_RPC,
        json={
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:

        raise Exception(
            data["error"].get(
                "message",
                "Ethereum RPC error"
            )
        )

    return data.get("result")


# =========================================================
# REFRESH ETHEREUM BLOCK CACHE
# =========================================================

async def refresh_ethereum_blocks():

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            latest_hex = await ethereum_rpc(
                client,
                "eth_blockNumber",
                []
            )

            latest_height = int(
                latest_hex,
                16
            )

            blocks = []

            for height in range(
                latest_height,
                latest_height - 10,
                -1
            ):

                block = await ethereum_rpc(
                    client,
                    "eth_getBlockByNumber",
                    [
                        hex(height),
                        False
                    ]
                )

                if not block:
                    continue

                timestamp = int(
                    block.get(
                        "timestamp",
                        "0x0"
                    ),
                    16
                )

                transactions = block.get(
                    "transactions",
                    []
                )

                blocks.append({

                    "hash":
                        block.get("hash"),

                    "height":
                        int(
                            block.get(
                                "number",
                                "0x0"
                            ),
                            16
                        ),

                    "time":
                        timestamp,

                    "block_index":
                        int(
                            block.get(
                                "number",
                                "0x0"
                            ),
                            16
                        ),

                    "txIndexes":
                        transactions,

                    "n_tx":
                        len(transactions),

                    "size":
                        int(
                            block.get(
                                "size",
                                "0x0"
                            ),
                            16
                        ),

                    "weight": 0,

                    "prev_block":
                        block.get(
                            "parentHash"
                        ),

                    "main_chain": True,

                    "gas_used":
                        int(
                            block.get(
                                "gasUsed",
                                "0x0"
                            ),
                            16
                        ),

                    "gas_limit":
                        int(
                            block.get(
                                "gasLimit",
                                "0x0"
                            ),
                            16
                        ),

                    "base_fee_per_gas": (
                        int(
                            block[
                                "baseFeePerGas"
                            ],
                            16
                        )
                        if block.get(
                            "baseFeePerGas"
                        )
                        else None
                    )
                })

            if not blocks:
                return

            blocks.sort(
                key=lambda x: x.get(
                    "height",
                    0
                ),
                reverse=True
            )

            ETHEREUM_CACHE[
                "network"
            ] = "Ethereum"

            ETHEREUM_CACHE[
                "status"
            ] = "LIVE"

            ETHEREUM_CACHE[
                "latest_height"
            ] = latest_height

            ETHEREUM_CACHE[
                "blocks"
            ] = blocks[:10]

            ETHEREUM_CACHE[
                "count"
            ] = len(blocks[:10])

            ETHEREUM_CACHE[
                "source"
            ] = "PublicNode Ethereum JSON-RPC"

            ETHEREUM_CACHE[
                "updated_at"
            ] = time.time()

            print(
                f"Ethereum blocks updated: "
                f"{latest_height}"
            )

    except Exception as e:

        print(
            f"Ethereum block refresh error: "
            f"{e}"
        )


# =========================================================
# ETHEREUM LIVE BLOCKS API
# =========================================================

@router.get("/ethereum/blocks")
async def ethereum_blocks():

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            latest_block_hex = await ethereum_rpc(
                client,
                "eth_blockNumber",
                []
            )

            latest_block = int(
                latest_block_hex,
                16
            )

            blocks = []

            for block_number in range(
                latest_block,
                latest_block - 10,
                -1
            ):

                block = await ethereum_rpc(
                    client,
                    "eth_getBlockByNumber",
                    [
                        hex(block_number),
                        False
                    ]
                )

                if not block:
                    continue

                transactions = block.get(
                    "transactions",
                    []
                )

                blocks.append({

                    "hash":
                        block.get("hash"),

                    "height":
                        int(
                            block.get(
                                "number",
                                "0x0"
                            ),
                            16
                        ),

                    "timestamp":
                        int(
                            block.get(
                                "timestamp",
                                "0x0"
                            ),
                            16
                        ),

                    "tx_count":
                        len(transactions),

                    "transactions":
                        transactions,

                    "size":
                        int(
                            block.get(
                                "size",
                                "0x0"
                            ),
                            16
                        ),

                    "gas_used":
                        int(
                            block.get(
                                "gasUsed",
                                "0x0"
                            ),
                            16
                        ),

                    "gas_limit":
                        int(
                            block.get(
                                "gasLimit",
                                "0x0"
                            ),
                            16
                        ),

                    "base_fee_per_gas": (
                        int(
                            block[
                                "baseFeePerGas"
                            ],
                            16
                        )
                        if block.get(
                            "baseFeePerGas"
                        )
                        else None
                    ),

                    "parent_hash":
                        block.get(
                            "parentHash"
                        )
                })

        return {
            "network": "Ethereum",
            "status": "LIVE",
            "latest_block": latest_block,
            "count": len(blocks),
            "blocks": blocks,
            "source":
                "PublicNode Ethereum JSON-RPC"
        }

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum blocks fetch "
                f"failed: {str(e)}"
            )
        )


# =========================================================
# ETHEREUM BLOCK DETAILS
# =========================================================

@router.get("/ethereum/block/{block_number}")
async def ethereum_block_details(
    block_number: str
):

    try:

        if block_number.startswith("0x"):

            block_param = block_number

        else:

            block_param = hex(
                int(block_number)
            )

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            block = await ethereum_rpc(
                client,
                "eth_getBlockByNumber",
                [
                    block_param,
                    False
                ]
            )

        if not block:

            raise HTTPException(
                status_code=404,
                detail="Ethereum block not found."
            )

        transactions = block.get(
            "transactions",
            []
        )

        return {

            "network":
                "Ethereum",

            "status":
                "LIVE",

            "block": {

                "hash":
                    block.get("hash"),

                "height":
                    int(
                        block.get(
                            "number",
                            "0x0"
                        ),
                        16
                    ),

                "timestamp":
                    int(
                        block.get(
                            "timestamp",
                            "0x0"
                        ),
                        16
                    ),

                "tx_count":
                    len(transactions),

                "transactions":
                    transactions,

                "size":
                    int(
                        block.get(
                            "size",
                            "0x0"
                        ),
                        16
                    ),

                "gas_used":
                    int(
                        block.get(
                            "gasUsed",
                            "0x0"
                        ),
                        16
                    ),

                "gas_limit":
                    int(
                        block.get(
                            "gasLimit",
                            "0x0"
                        ),
                        16
                    ),

                "base_fee_per_gas": (
                    int(
                        block[
                            "baseFeePerGas"
                        ],
                        16
                    )
                    if block.get(
                        "baseFeePerGas"
                    )
                    else None
                ),

                "parent_hash":
                    block.get(
                        "parentHash"
                    ),

                "state_root":
                    block.get(
                        "stateRoot"
                    ),

                "transactions_root":
                    block.get(
                        "transactionsRoot"
                    ),

                "receipts_root":
                    block.get(
                        "receiptsRoot"
                    )
            },

            "source":
                "PublicNode Ethereum JSON-RPC"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum block lookup "
                f"failed: {str(e)}"
            )
        )


# =========================================================
# ETHEREUM WALLET INVESTIGATION
# =========================================================

@router.get("/ethereum/wallet/{address}")
async def ethereum_wallet(
    address: str
):

    try:

        if (
            not address.startswith("0x")
            or len(address) != 42
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum wallet address."
            )

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            balance_hex = await ethereum_rpc(
                client,
                "eth_getBalance",
                [
                    address,
                    "latest"
                ]
            )

            transaction_count_hex = await ethereum_rpc(
                client,
                "eth_getTransactionCount",
                [
                    address,
                    "latest"
                ]
            )

        balance_wei = int(
            balance_hex,
            16
        )

        balance_eth = (
            balance_wei / 10**18
        )

        transaction_count = int(
            transaction_count_hex,
            16
        )

        return {

            "network":
                "Ethereum",

            "status":
                "LIVE",

            "wallet": {

                "address":
                    address,

                "balance_wei":
                    balance_wei,

                "balance_eth":
                    balance_eth,

                "transaction_count":
                    transaction_count
            },

            "source":
                "PublicNode Ethereum JSON-RPC"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum wallet lookup "
                f"failed: {str(e)}"
            )
        )


# =========================================================
# ETHEREUM WALLET TRANSACTION HISTORY
# =========================================================

@router.get("/ethereum/wallet/{address}/transactions")
async def ethereum_wallet_transactions(
    address: str,
    items_count: int = 50,
    page: str | None = None,
    block_number: str | None = None,
    index: str | None = None,
    filter: str | None = None
):

    try:

        if (
            not address.startswith("0x")
            or len(address) != 42
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum wallet address."
            )

        url = (
            f"https://eth.blockscout.com/"
            f"api/v2/addresses/{address}/transactions"
        )

        params = {
            "items_count":
                min(
                    max(
                        items_count,
                        1
                    ),
                    50
                )
        }

        if page:
            params["page"] = page

        if block_number:
            params["block_number"] = block_number

        if index:
            params["index"] = index

        if filter:
            params["filter"] = filter

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            response = await client.get(
                url,
                params=params
            )

        response.raise_for_status()

        data = response.json()

        items = data.get(
            "items",
            []
        )

        transactions = []

        for tx in items:

            from_data = (
                tx.get("from")
                or {}
            )

            to_data = (
                tx.get("to")
                or {}
            )

            from_address = (
                from_data.get("hash")
            )

            to_address = (
                to_data.get("hash")
            )

            value = tx.get(
                "value"
            )

            direction = (
                "INCOMING"
                if (
                    to_address
                    and to_address.lower()
                    == address.lower()
                )
                else "OUTGOING"
            )

            transactions.append({

                "hash":
                    tx.get("hash"),

                "timestamp":
                    tx.get("timestamp"),

                "from":
                    from_address,

                "to":
                    to_address,

                "value":
                    value,

                "success":
                    tx.get("status") == "ok",

                "direction":
                    direction,

                "block":
                    tx.get("block"),

                "fee":
                    tx.get("fee")
            })

        next_page_params = data.get(
            "next_page_params"
        )

        return {

            "network":
                "Ethereum",

            "status":
                "LIVE",

            "wallet":
                address,

            "count":
                len(transactions),

            "transactions":
                transactions,

            "next_page_params":
                next_page_params,

            "has_more":
                bool(
                    next_page_params
                ),

            "source":
                "Blockscout Ethereum API"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum transaction history "
                f"failed: {str(e)}"
            )
        )


# =========================================================
# ETHEREUM ERC-20 TOKEN TRANSFERS
# =========================================================

@router.get("/ethereum/wallet/{address}/tokens")
async def ethereum_wallet_tokens(
    address: str,
    items_count: int = 50,
    block_number: str | None = None,
    index: str | None = None,
    unique_token: str | None = None
):

    try:

        if (
            not address.startswith("0x")
            or len(address) != 42
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum wallet address."
            )

        url = (
            f"https://eth.blockscout.com/"
            f"api/v2/addresses/{address}/token-transfers"
        )

        params = {

            "type":
                "ERC-20",

            "items_count":
                min(
                    max(
                        items_count,
                        1
                    ),
                    50
                )
        }

        if block_number:
            params["block_number"] = block_number

        if index:
            params["index"] = index

        if unique_token:
            params["unique_token"] = unique_token

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            response = await client.get(
                url,
                params=params
            )

        response.raise_for_status()

        data = response.json()

        items = data.get(
            "items",
            []
        )

        transfers = []

        for tx in items:

            from_data = (
                tx.get("from")
                or {}
            )

            to_data = (
                tx.get("to")
                or {}
            )

            token = (
                tx.get("token")
                or {}
            )

            total = (
                tx.get("total")
                or {}
            )

            from_address = (
                from_data.get("hash")
            )

            to_address = (
                to_data.get("hash")
            )

            direction = (
                "INCOMING"
                if (
                    to_address
                    and to_address.lower()
                    == address.lower()
                )
                else "OUTGOING"
            )

            transfers.append({

                "hash":
                    tx.get(
                        "transaction_hash"
                    ),

                "timestamp":
                    tx.get(
                        "timestamp"
                    ),

                "from":
                    from_address,

                "to":
                    to_address,

                "token":
                    token.get(
                        "name"
                    ),

                "symbol":
                    token.get(
                        "symbol"
                    ),

                "token_address":
                    token.get(
                        "address"
                    ),

                "value":
                    total.get(
                        "value"
                    ),

                "decimals":
                    total.get(
                        "decimals"
                    ),

                "direction":
                    direction
            })

        next_page_params = data.get(
            "next_page_params"
        )

        return {

            "network":
                "Ethereum",

            "status":
                "LIVE",

            "wallet":
                address,

            "count":
                len(transfers),

            "token_transfers":
                transfers,

            "next_page_params":
                next_page_params,

            "has_more":
                bool(
                    next_page_params
                ),

            "source":
                "Blockscout Ethereum API"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum token transfer "
                f"lookup failed: {str(e)}"
            )
        )


# =========================================================
# ETHEREUM LIVE TRANSACTIONS
# =========================================================

@router.get("/ethereum/live-transactions")
async def ethereum_live_transactions():

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            latest_block_hex = await ethereum_rpc(
                client,
                "eth_blockNumber",
                []
            )

            latest_block = int(
                latest_block_hex,
                16
            )

            block = await ethereum_rpc(
                client,
                "eth_getBlockByNumber",
                [
                    latest_block_hex,
                    True
                ]
            )

            if not block:

                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Latest Ethereum block "
                        "not found"
                    )
                )

            transactions = []

            for tx in block.get(
                "transactions",
                []
            ):

                transactions.append({

                    "hash":
                        tx.get("hash"),

                    "from":
                        tx.get("from"),

                    "to":
                        tx.get("to"),

                    "value":
                        int(
                            tx.get(
                                "value",
                                "0x0"
                            ),
                            16
                        ),

                    "gas":
                        int(
                            tx.get(
                                "gas",
                                "0x0"
                            ),
                            16
                        ),

                    "gas_price":
                        int(
                            tx.get(
                                "gasPrice",
                                "0x0"
                            ),
                            16
                        ),

                    "nonce":
                        int(
                            tx.get(
                                "nonce",
                                "0x0"
                            ),
                            16
                        ),

                    "block_number":
                        latest_block
                })

        return {

            "network":
                "Ethereum",

            "status":
                "LIVE",

            "block":
                latest_block,

            "transaction_count":
                len(transactions),

            "transactions":
                transactions,

            "source":
                "PublicNode Ethereum JSON-RPC"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum live transactions "
                f"fetch failed: {str(e)}"
            )
        )