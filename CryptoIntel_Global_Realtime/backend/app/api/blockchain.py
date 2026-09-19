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