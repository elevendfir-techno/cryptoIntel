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
# CACHE
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


# =========================================================
# FETCH BLOCK DATA
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

        blocks = data.get("blocks", [])

        if not blocks:
            return None

        block = blocks[0]

        return {
            "hash": block.get("hash"),
            "height": block.get("height"),
            "time": block.get("time"),
            "block_index": block.get("block_index"),
            "txIndexes": block.get("txIndexes", []),
            "n_tx": block.get("n_tx", 0),
            "size": block.get("size", 0),
            "prev_block": block.get("prev_block"),
            "main_chain": block.get(
                "main_chain",
                True
            )
        }

    except Exception:

        return None


# =========================================================
# FETCH LATEST 10 BLOCKS
# =========================================================

async def refresh_blocks():

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            # -------------------------------------------------
            # Get latest 10 Bitcoin blocks
            # -------------------------------------------------

            response = await client.get(
                f"{MEMPOOL_API}/blocks"
            )

            response.raise_for_status()

            data = response.json()

            if not data:
                return

            # -------------------------------------------------
            # Build block records
            # -------------------------------------------------

            blocks = []

            for block in data[:10]:

                blocks.append({
                    "hash": block.get("id"),
                    "height": block.get("height"),
                    "time": block.get("timestamp"),
                    "block_index": block.get("height"),

                    "txIndexes": [],

                    "n_tx": block.get(
                        "tx_count",
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
                        "previousblockhash"
                    ),

                    "main_chain": True
                })

            # -------------------------------------------------
            # Sort newest first
            # -------------------------------------------------

            blocks.sort(
                key=lambda x: x.get(
                    "height",
                    0
                ),
                reverse=True
            )

            if not blocks:
                return

            latest_height = blocks[0]["height"]

            # -------------------------------------------------
            # Update cache
            # -------------------------------------------------

            BLOCK_CACHE["network"] = "Bitcoin"

            BLOCK_CACHE["status"] = "LIVE"

            BLOCK_CACHE["latest_height"] = latest_height

            BLOCK_CACHE["blocks"] = blocks[:10]

            BLOCK_CACHE["count"] = len(
                blocks[:10]
            )

            BLOCK_CACHE["source"] = (
                "Mempool.space Bitcoin API"
            )

            BLOCK_CACHE["updated_at"] = time.time()

            print(
                f"Bitcoin blocks updated: "
                f"{latest_height}"
            )

    except Exception as e:

        print(
            f"Bitcoin block refresh error: {e}"
        )

# =========================================================
# BACKGROUND BLOCK REFRESH
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
                f"Blockchain background error: {e}"
            )

        # -------------------------------------------------
        # Refresh every 60 seconds
        # -------------------------------------------------

        await asyncio.sleep(60)


# =========================================================
# START BACKGROUND COLLECTOR
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

    # -----------------------------------------------------
    # If cache already exists, return immediately
    # -----------------------------------------------------

    if BLOCK_CACHE["blocks"]:

        return {
            "network": BLOCK_CACHE["network"],
            "status": BLOCK_CACHE["status"],
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

    # -----------------------------------------------------
    # First request
    # -----------------------------------------------------

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
        "network": BLOCK_CACHE["network"],
        "status": BLOCK_CACHE["status"],
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
async def bitcoin_block_details(block_hash: str):

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
                "hash": block.get("id"),
                "height": block.get("height"),
                "timestamp": block.get("timestamp"),
                "tx_count": block.get("tx_count", 0),
                "size": block.get("size", 0),
                "weight": block.get("weight", 0),
                "version": block.get("version"),
                "merkle_root": block.get("merkle_root"),
                "previous_block_hash": block.get(
                    "previousblockhash"
                ),
                "nonce": block.get("nonce"),
                "bits": block.get("bits"),
                "difficulty": block.get("difficulty")
            },
            "source": "Mempool.space Bitcoin API"
        }

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=f"Block lookup failed: {str(e)}"
        )
# BITCOIN TRANSACTION
# =========================================================

@router.get("/bitcoin/transaction/{txid}")
async def bitcoin_transaction(txid: str):

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
                f"Transaction lookup failed: {str(e)}"
            )
        )


# =========================================================
# BITCOIN ADDRESS
# =========================================================

@router.get("/bitcoin/address/{address}")
async def bitcoin_address(address: str):

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
                f"Address lookup failed: {str(e)}"
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


async def ethereum_rpc(client, method, params):

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


async def refresh_ethereum_blocks():

    try:

        async with httpx.AsyncClient(
            timeout=20,
            headers={
                "User-Agent": "CryptoIntel/1.0"
            }
        ) as client:

            # -------------------------------------------------
            # Get latest Ethereum block number
            # -------------------------------------------------

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

            # -------------------------------------------------
            # Get latest 10 blocks
            # -------------------------------------------------

            for height in range(
                latest_height,
                latest_height - 10,
                -1
            ):

                block_hex = hex(height)

                block = await ethereum_rpc(
                    client,
                    "eth_getBlockByNumber",
                    [
                        block_hex,
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

                blocks.append({
                    "hash": block.get("hash"),

                    "height": int(
                        block.get(
                            "number",
                            "0x0"
                        ),
                        16
                    ),

                    "time": timestamp,

                    "block_index": int(
                        block.get(
                            "number",
                            "0x0"
                        ),
                        16
                    ),

                    "txIndexes":
                        block.get(
                            "transactions",
                            []
                        ),

                    "n_tx":
                        len(
                            block.get(
                                "transactions",
                                []
                            )
                        ),

                    "size": int(
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

                    "gas_used": int(
                        block.get(
                            "gasUsed",
                            "0x0"
                        ),
                        16
                    ),

                    "gas_limit": int(
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

            # -------------------------------------------------
            # Update Ethereum cache
            # -------------------------------------------------

            ETHEREUM_CACHE["network"] = (
                "Ethereum"
            )

            ETHEREUM_CACHE["status"] = (
                "LIVE"
            )

            ETHEREUM_CACHE["latest_height"] = (
                latest_height
            )

            ETHEREUM_CACHE["blocks"] = (
                blocks[:10]
            )

            ETHEREUM_CACHE["count"] = len(
                blocks[:10]
            )

            ETHEREUM_CACHE["source"] = (
                "PublicNode Ethereum JSON-RPC"
            )

            ETHEREUM_CACHE["updated_at"] = (
                time.time()
            )

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
# ETHEREUM LATEST BLOCKS API
# =========================================================

@router.get("/ethereum/blocks")
async def ethereum_blocks():

    if ETHEREUM_CACHE["blocks"]:

        return {
            "network":
                ETHEREUM_CACHE["network"],

            "status":
                ETHEREUM_CACHE["status"],

            "latest_height":
                ETHEREUM_CACHE["latest_height"],

            "blocks":
                ETHEREUM_CACHE["blocks"],

            "count":
                ETHEREUM_CACHE["count"],

            "source":
                ETHEREUM_CACHE["source"],

            "cached": True
        }

    await refresh_ethereum_blocks()

    if not ETHEREUM_CACHE["blocks"]:

        raise HTTPException(
            status_code=502,
            detail=(
                "Ethereum blockchain data "
                "temporarily unavailable."
            )
        )

    return {
        "network":
            ETHEREUM_CACHE["network"],

        "status":
            ETHEREUM_CACHE["status"],

        "latest_height":
            ETHEREUM_CACHE["latest_height"],

        "blocks":
            ETHEREUM_CACHE["blocks"],

        "count":
            ETHEREUM_CACHE["count"],

        "source":
            ETHEREUM_CACHE["source"],

        "cached": True
    }

# =========================================================
# ETHEREUM LIVE BLOCKS
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

            # Get latest Ethereum block number
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

            # Fetch latest 10 blocks
            for block_number in range(
                latest_block,
                latest_block - 10,
                -1
            ):

                block_hex = hex(block_number)

                block = await ethereum_rpc(
                    client,
                    "eth_getBlockByNumber",
                    [
                        block_hex,
                        False
                    ]
                )

                if not block:
                    continue

                blocks.append({
                    "hash": block.get("hash"),

                    "height": int(
                        block.get(
                            "number",
                            "0x0"
                        ),
                        16
                    ),

                    "timestamp": int(
                        block.get(
                            "timestamp",
                            "0x0"
                        ),
                        16
                    ),

                    "tx_count": len(
                        block.get(
                            "transactions",
                            []
                        )
                    ),

                    "size": int(
                        block.get(
                            "size",
                            "0x0"
                        ),
                        16
                    ),

                    "gas_used": int(
                        block.get(
                            "gasUsed",
                            "0x0"
                        ),
                        16
                    ),

                    "gas_limit": int(
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

                    "parent_hash": block.get(
                        "parentHash"
                    )
                })

        return {
            "network": "Ethereum",
            "status": "LIVE",
            "latest_block": latest_block,
            "count": len(blocks),
            "blocks": blocks,
            "source": "PublicNode Ethereum JSON-RPC"
        }

    except Exception as e:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Ethereum blocks fetch "
                f"failed: {str(e)}"
            )
        )
@router.get("/ethereum/block/{block_number}")
async def ethereum_block_details(
    block_number: str
):

    try:

        if block_number.startswith(
            "0x"
        ):

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

        return {
            "network": "Ethereum",

            "status": "LIVE",

            "block": {
                "hash":
                    block.get("hash"),

                "height": int(
                    block.get(
                        "number",
                        "0x0"
                    ),
                    16
                ),

                "timestamp": int(
                    block.get(
                        "timestamp",
                        "0x0"
                    ),
                    16
                ),

                "tx_count": len(
                    block.get(
                        "transactions",
                        []
                    )
                ),

                "size": int(
                    block.get(
                        "size",
                        "0x0"
                    ),
                    16
                ),

                "gas_used": int(
                    block.get(
                        "gasUsed",
                        "0x0"
                    ),
                    16
                ),

                "gas_limit": int(
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
async def ethereum_wallet(address: str):

    try:

        # Basic Ethereum address validation
        if not address.startswith("0x") or len(address) != 42:

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

            # Get current ETH balance
            balance_hex = await ethereum_rpc(
                client,
                "eth_getBalance",
                [
                    address,
                    "latest"
                ]
            )

            # Get transaction nonce/count
            transaction_count_hex = await ethereum_rpc(
                client,
                "eth_getTransactionCount",
                [
                    address,
                    "latest"
                ]
            )

        # Convert Wei → ETH
        balance_wei = int(
            balance_hex,
            16
        )

        balance_eth = balance_wei / 10**18

        transaction_count = int(
            transaction_count_hex,
            16
        )

        return {
            "network": "Ethereum",

            "status": "LIVE",

            "wallet": {
                "address": address,

                "balance_wei": balance_wei,

                "balance_eth": balance_eth,

                "transaction_count": transaction_count
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
async def ethereum_wallet_transactions(address: str):

    try:

        if not address.startswith("0x") or len(address) != 42:
            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum wallet address."
            )

        url = (
            f"https://api.ethplorer.io/"
            f"getAddressTransactions/{address}"
        )

        params = {
            "apiKey": "freekey",
            "limit": 50,
            "showZeroValues": "false"
        }

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

        return {
            "network": "Ethereum",

            "status": "LIVE",

            "wallet": address,

            "count": len(data),

            "transactions": [
    {
        "hash": tx.get("hash"),
        "timestamp": tx.get("timestamp"),
        "from": tx.get("from"),
        "to": tx.get("to"),
        "value": tx.get("value"),
        "success": tx.get("success"),
        "direction": (
            "INCOMING"
            if tx.get("to", "").lower() == address.lower()
            else "OUTGOING"
        )
    }
    for tx in data
],
            "source":
                "Ethplorer Ethereum Address API"
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
async def ethereum_wallet_tokens(address: str):

    try:

        if not address.startswith("0x") or len(address) != 42:
            raise HTTPException(
                status_code=400,
                detail="Invalid Ethereum wallet address."
            )

        url = (
            f"https://api.ethplorer.io/"
            f"getAddressHistory/{address}"
        )

        params = {
            "apiKey": "freekey",
            "type": "transfer",
            "limit": 50
        }

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

        operations = data.get(
            "operations",
            []
        )

        transfers = []

        for tx in operations:

            token_info = tx.get(
                "tokenInfo",
                {}
            )

            transfers.append({
                "hash": tx.get("transactionHash"),
                "timestamp": tx.get("timestamp"),
                "from": tx.get("from"),
                "to": tx.get("to"),
                "token": token_info.get("name"),
                "symbol": token_info.get("symbol"),
                "token_address": token_info.get("address"),
                "value": tx.get("value"),
                "direction": (
                    "INCOMING"
                    if tx.get("to", "").lower()
                    == address.lower()
                    else "OUTGOING"
                )
            })

        return {
            "network": "Ethereum",
            "status": "LIVE",
            "wallet": address,
            "count": len(transfers),
            "token_transfers": transfers,
            "source": "Ethplorer Ethereum Address API"
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