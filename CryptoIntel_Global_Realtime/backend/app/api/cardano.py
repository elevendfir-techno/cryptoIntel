from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/cardano",
    tags=["cardano"],
)


# ============================================================
# CARDANO / KOIOS CONFIG
# ============================================================

CARDANO_API = "https://api.koios.rest/api/v1"
CARDANO_EXPLORER = "https://cardanoscan.io"


# ============================================================
# INVESTIGATION LIMITS
# ============================================================

MAX_HOPS = 2
MAX_WALLETS_PER_HOP = 10
MAX_TRANSACTIONS_PER_WALLET = 25
MAX_TOTAL_TRANSACTIONS = 100
MAX_EDGES = 150
MAX_ADDRESS_TXS = 25


# ============================================================
# HTTP HELPERS
# ============================================================

async def api_get(
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.get(
                f"{CARDANO_API}{path}",
                params=params,
                headers={
                    "Accept": "application/json",
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Koios API error: {exc.response.text[:1000]}",
        ) from exc

    except httpx.RequestError as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach Koios API: {exc}",
        ) from exc


async def api_post(
    path: str,
    payload: list[dict[str, Any]] | dict[str, Any],
) -> Any:

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.post(
                f"{CARDANO_API}{path}",
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Koios API error: {exc.response.text[:1000]}",
        ) from exc

    except httpx.RequestError as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Unable to reach Koios API: {exc}",
        ) from exc


# ============================================================
# GENERAL HELPERS
# ============================================================

def first_item(data: Any) -> dict[str, Any]:

    if isinstance(data, list) and data:

        item = data[0]

        if isinstance(item, dict):
            return item

    return {}


def normalize_list(data: Any) -> list[dict[str, Any]]:

    if not isinstance(data, list):
        return []

    return [
        item
        for item in data
        if isinstance(item, dict)
    ]


def validate_cardano_address(address: str) -> str:

    address = address.strip()

    if not address:
        raise HTTPException(
            status_code=400,
            detail="Cardano address is required",
        )

    if not (
        address.startswith("addr1")
        or address.startswith("stake1")
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid Cardano mainnet address. "
                "Expected addr1 or stake1 address."
            ),
        )

    return address


def validate_tx_hash(tx_hash: str) -> str:

    tx_hash = tx_hash.strip().lower()

    if len(tx_hash) != 64:

        raise HTTPException(
            status_code=400,
            detail="Invalid Cardano transaction hash.",
        )

    return tx_hash


def explorer_address(address: str) -> str:

    return f"{CARDANO_EXPLORER}/address/{address}"


def explorer_transaction(tx_hash: str) -> str:

    return f"{CARDANO_EXPLORER}/transaction/{tx_hash}"


# ============================================================
# ADDRESS EXTRACTION
# ============================================================

def extract_address_from_item(
    item: dict[str, Any],
) -> str | None:

    # --------------------------------------------------------
    # Direct address
    # --------------------------------------------------------

    address = item.get("address")

    if isinstance(address, str) and address:

        return address

    # --------------------------------------------------------
    # Koios payment_addr object
    # --------------------------------------------------------

    payment_addr = item.get("payment_addr")

    if isinstance(payment_addr, dict):

        bech32 = payment_addr.get("bech32")

        if isinstance(bech32, str) and bech32:

            return bech32

    # --------------------------------------------------------
    # payment_addr as string
    # --------------------------------------------------------

    if isinstance(payment_addr, str) and payment_addr:

        return payment_addr

    return None


# ============================================================
# INPUT ADDRESSES
# ============================================================

def extract_input_addresses(
    transaction: dict[str, Any],
) -> list[str]:

    addresses: list[str] = []

    inputs = transaction.get("inputs") or []

    if not isinstance(inputs, list):
        return addresses

    for item in inputs:

        if not isinstance(item, dict):
            continue

        address = extract_address_from_item(item)

        if address:

            addresses.append(address)

    return list(dict.fromkeys(addresses))


# ============================================================
# OUTPUT ADDRESSES
# ============================================================

def extract_output_addresses(
    transaction: dict[str, Any],
) -> list[str]:

    addresses: list[str] = []

    outputs = transaction.get("outputs") or []

    if not isinstance(outputs, list):
        return addresses

    for item in outputs:

        if not isinstance(item, dict):
            continue

        address = extract_address_from_item(item)

        if address:

            addresses.append(address)

    return list(dict.fromkeys(addresses))


# ============================================================
# COLLATERAL ADDRESSES
# ============================================================

def extract_collateral_addresses(
    transaction: dict[str, Any],
) -> list[str]:

    addresses: list[str] = []

    # --------------------------------------------------------
    # Collateral inputs
    # --------------------------------------------------------

    collateral_inputs = (
        transaction.get("collateral_inputs") or []
    )

    if isinstance(collateral_inputs, list):

        for item in collateral_inputs:

            if not isinstance(item, dict):
                continue

            address = extract_address_from_item(item)

            if address:

                addresses.append(address)

    # --------------------------------------------------------
    # Collateral output
    # --------------------------------------------------------

    collateral_output = (
        transaction.get("collateral_output")
    )

    if isinstance(collateral_output, dict):

        address = extract_address_from_item(
            collateral_output
        )

        if address:

            addresses.append(address)

    return list(dict.fromkeys(addresses))


# ============================================================
# FETCH ADDRESS TRANSACTIONS
# ============================================================

async def fetch_address_transactions(
    address: str,
    limit: int = MAX_TRANSACTIONS_PER_WALLET,
) -> list[dict[str, Any]]:

    address = validate_cardano_address(address)

    limit = max(
        1,
        min(limit, MAX_ADDRESS_TXS),
    )

    data = await api_post(
        "/address_txs",
        [
            {
                "_addresses": [address],
            }
        ],
    )

    transactions = normalize_list(data)

    return transactions[:limit]


# ============================================================
# FETCH SINGLE TRANSACTION
# ============================================================

async def fetch_transaction_details(
    tx_hash: str,
) -> dict[str, Any]:

    if not tx_hash:
        return {}

    data = await api_post(
        "/tx_info",
        [
            {
                "_tx_hashes": [tx_hash],
            }
        ],
    )

    return first_item(data)


# ============================================================
# FETCH TRANSACTIONS IN BATCH
# ============================================================

async def fetch_transactions_batch(
    tx_hashes: list[str],
) -> list[dict[str, Any]]:

    cleaned: list[str] = []

    seen: set[str] = set()

    for tx_hash in tx_hashes:

        if not isinstance(tx_hash, str):
            continue

        tx_hash = tx_hash.strip().lower()

        if len(tx_hash) != 64:
            continue

        if tx_hash in seen:
            continue

        seen.add(tx_hash)
        cleaned.append(tx_hash)

        if len(cleaned) >= MAX_TOTAL_TRANSACTIONS:
            break

    if not cleaned:
        return []

    try:

        data = await api_post(
            "/tx_info",
            [
                {
                    "_tx_hashes": cleaned,
                }
            ],
        )

        return normalize_list(data)

    except Exception:

        # Fallback to individual requests
        results: list[dict[str, Any]] = []

        for tx_hash in cleaned:

            try:

                transaction = (
                    await fetch_transaction_details(
                        tx_hash
                    )
                )

                if transaction:
                    results.append(transaction)

            except Exception:
                continue

        return results


# ============================================================
# EXTRACT COUNTERPARTIES
# ============================================================

def extract_counterparties(
    root_address: str,
    transaction: dict[str, Any],
) -> list[dict[str, Any]]:

    root_address = root_address.strip()

    results: dict[
        str,
        dict[str, Any]
    ] = {}

    # --------------------------------------------------------
    # INPUT SIDE
    # --------------------------------------------------------

    input_addresses = extract_input_addresses(
        transaction
    )

    for address in input_addresses:

        if not address:
            continue

        if address == root_address:
            continue

        results[address] = {
            "address": address,
            "direction": "input",
        }

    # --------------------------------------------------------
    # OUTPUT SIDE
    # --------------------------------------------------------

    output_addresses = extract_output_addresses(
        transaction
    )

    for address in output_addresses:

        if not address:
            continue

        if address == root_address:
            continue

        if address in results:

            results[address]["direction"] = (
                "input_and_output"
            )

        else:

            results[address] = {
                "address": address,
                "direction": "output",
            }

    # --------------------------------------------------------
    # COLLATERAL SIDE
    # --------------------------------------------------------

    collateral_addresses = (
        extract_collateral_addresses(
            transaction
        )
    )

    for address in collateral_addresses:

        if not address:
            continue

        if address == root_address:
            continue

        if address in results:

            existing_direction = results[
                address
            ].get("direction")

            if existing_direction != "collateral":

                results[address]["direction"] = (
                    f"{existing_direction}_and_collateral"
                )

        else:

            results[address] = {
                "address": address,
                "direction": "collateral",
            }

    return list(results.values())


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
async def health():

    try:

        data = await api_get("/tip")

        tip = first_item(data)

        return {
            "network": "Cardano",
            "status": "LIVE",
            "epoch": tip.get("epoch_no"),
            "block": tip.get("block_no"),
            "slot": tip.get("abs_slot"),
            "hash": tip.get("hash"),
            "epoch_slot": tip.get("epoch_slot"),
            "block_time": tip.get("block_time"),
            "source": CARDANO_API,
            "explorer": CARDANO_EXPLORER,
        }

    except Exception as exc:

        return {
            "network": "Cardano",
            "status": "UNAVAILABLE",
            "source": CARDANO_API,
            "error": str(exc),
        }


# ============================================================
# LATEST BLOCK
# ============================================================

@router.get("/latest-block")
async def latest_block():

    try:

        data = await api_get("/tip")

        tip = first_item(data)

        block_hash = tip.get("hash")

        return {
            "network": "Cardano",
            "status": "LIVE",
            "epoch": tip.get("epoch_no"),
            "block": tip.get("block_no"),
            "slot": tip.get("abs_slot"),
            "epoch_slot": tip.get("epoch_slot"),
            "block_hash": block_hash,
            "block_time": tip.get("block_time"),
            "source": CARDANO_API,
            "explorer": (
                f"{CARDANO_EXPLORER}/block/{block_hash}"
                if block_hash
                else CARDANO_EXPLORER
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc


# ============================================================
# ADDRESS
# ============================================================

@router.get("/address/{address}")
async def address(address: str):

    address = validate_cardano_address(address)

    try:

        data = await api_post(
            "/address_info",
            [
                {
                    "_addresses": [address],
                }
            ],
        )

        if not data:

            raise HTTPException(
                status_code=404,
                detail="Cardano address not found",
            )

        return {
            "address": address,
            "network": "Cardano",
            "status": "LIVE",
            "address_info": data[0],
            "source": CARDANO_API,
            "explorer": explorer_address(address),
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Cardano address lookup failed: {exc}",
        ) from exc


# ============================================================
# TRANSACTIONS
# ============================================================

@router.get("/transactions/{address}")
async def transactions(
    address: str,
    limit: int = 25,
):

    address = validate_cardano_address(address)

    limit = max(
        1,
        min(limit, MAX_ADDRESS_TXS),
    )

    try:

        data = await api_post(
            "/address_txs",
            [
                {
                    "_addresses": [address],
                }
            ],
        )

        transaction_list = normalize_list(data)

        transaction_list = transaction_list[:limit]

        return {
            "network": "Cardano",
            "status": "LIVE",
            "address": address,
            "count": len(transaction_list),
            "transactions": transaction_list,
            "source": CARDANO_API,
            "explorer": explorer_address(address),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Cardano transaction history "
                f"lookup failed: {exc}"
            ),
        ) from exc


# ============================================================
# ASSETS
# ============================================================

@router.get("/assets/{address}")
async def assets(address: str):

    address = validate_cardano_address(address)

    try:

        data = await api_post(
            "/address_assets",
            [
                {
                    "_addresses": [address],
                }
            ],
        )

        asset_list = (
            data
            if isinstance(data, list)
            else []
        )

        return {
            "network": "Cardano",
            "status": "LIVE",
            "address": address,
            "count": len(asset_list),
            "assets": asset_list,
            "source": CARDANO_API,
            "explorer": explorer_address(address),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Cardano asset lookup failed: {exc}"
            ),
        ) from exc


# ============================================================
# TRANSACTION
# ============================================================

@router.get("/transaction/{tx_hash}")
async def transaction(tx_hash: str):

    tx_hash = tx_hash.strip()

    if not tx_hash:

        raise HTTPException(
            status_code=400,
            detail="Cardano transaction hash is required",
        )

    try:

        data = await api_post(
            "/tx_info",
            [
                {
                    "_tx_hashes": [tx_hash],
                }
            ],
        )

        if not data:

            raise HTTPException(
                status_code=404,
                detail="Cardano transaction not found",
            )

        return {
            "network": "Cardano",
            "status": "LIVE",
            "transaction": data[0],
            "source": CARDANO_API,
            "explorer": explorer_transaction(tx_hash),
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Cardano transaction lookup failed: {exc}"
            ),
        ) from exc


# ============================================================
# COUNTERPARTIES
# ============================================================

@router.get("/counterparties/{address}")
async def counterparties(
    address: str,
    limit: int = 25,
):

    address = validate_cardano_address(address)

    limit = max(
        1,
        min(
            limit,
            MAX_TRANSACTIONS_PER_WALLET,
        ),
    )

    try:

        # ----------------------------------------------------
        # Step 1: Get address transaction history
        # ----------------------------------------------------

        transaction_history = (
            await fetch_address_transactions(
                address,
                limit,
            )
        )

        tx_hashes: list[str] = []

        for item in transaction_history:

            tx_hash = item.get("tx_hash")

            if isinstance(tx_hash, str):

                tx_hashes.append(tx_hash)

        # ----------------------------------------------------
        # Step 2: Get transaction details
        # ----------------------------------------------------

        transaction_details = (
            await fetch_transactions_batch(
                tx_hashes
            )
        )

        # ----------------------------------------------------
        # Step 3: Extract wallets
        # ----------------------------------------------------

        wallet_map: dict[
            str,
            dict[str, Any]
        ] = {}

        transaction_analysis: list[
            dict[str, Any]
        ] = []

        for tx in transaction_details:

            tx_hash = tx.get("tx_hash")

            tx_counterparties = (
                extract_counterparties(
                    address,
                    tx,
                )
            )

            transaction_analysis.append(
                {
                    "tx_hash": tx_hash,
                    "counterparties":
                        tx_counterparties,
                }
            )

            for item in tx_counterparties:

                wallet = item.get("address")

                if not wallet:
                    continue

                if wallet not in wallet_map:

                    wallet_map[wallet] = {
                        "address": wallet,
                        "transactions": [],
                        "directions": [],
                    }

                if tx_hash:

                    if (
                        tx_hash
                        not in wallet_map[wallet][
                            "transactions"
                        ]
                    ):

                        wallet_map[wallet][
                            "transactions"
                        ].append(tx_hash)

                direction = item.get(
                    "direction",
                    "unknown",
                )

                if (
                    direction
                    not in wallet_map[wallet][
                        "directions"
                    ]
                ):

                    wallet_map[wallet][
                        "directions"
                    ].append(direction)

        wallets = list(wallet_map.values())

        return {
            "network": "Cardano",
            "status": "LIVE",
            "root_wallet": address,
            "transactions_checked": len(
                transaction_details
            ),
            "counterparties": len(wallets),
            "wallets": wallets,
            "transaction_analysis":
                transaction_analysis,
            "source": CARDANO_API,
            "explorer": explorer_address(address),
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Cardano counterparty lookup failed: "
                f"{exc}"
            ),
        ) from exc


# ============================================================
# FUND FLOW — 2 HOPS
# ============================================================

@router.get("/fundflow/{address}")
async def fundflow(
    address: str,
    hops: int = 2,
    limit: int = 25,
):

    address = validate_cardano_address(address)

    hops = max(
        1,
        min(hops, MAX_HOPS),
    )

    limit = max(
        1,
        min(
            limit,
            MAX_TRANSACTIONS_PER_WALLET,
        ),
    )

    # --------------------------------------------------------
    # Graph structures
    # --------------------------------------------------------

    wallet_nodes: dict[
        str,
        dict[str, Any]
    ] = {
        address: {
            "address": address,
            "hop": 0,
        }
    }

    edges_data: list[
        dict[str, Any]
    ] = []

    seen_transactions: set[str] = set()

    seen_edges: set[
        tuple[str, str, str]
    ] = set()

    processed_wallets: set[str] = set()

    current_level = [address]

    wallets_by_hop = {
        "hop_0": 1,
        "hop_1": 0,
        "hop_2": 0,
    }

    # --------------------------------------------------------
    # Hop loop
    # --------------------------------------------------------

    for current_hop in range(
        1,
        hops + 1,
    ):

        if not current_level:
            break

        next_level: list[str] = []

        next_level_seen: set[str] = set()

        wallets_to_process = (
            current_level[
                :MAX_WALLETS_PER_HOP
            ]
        )

        for wallet in wallets_to_process:

            if wallet in processed_wallets:
                continue

            processed_wallets.add(wallet)

            # ------------------------------------------------
            # Get wallet transactions
            # ------------------------------------------------

            try:

                history = (
                    await fetch_address_transactions(
                        wallet,
                        limit,
                    )
                )

            except Exception:

                continue

            tx_hashes: list[str] = []

            for item in history:

                tx_hash = item.get("tx_hash")

                if not isinstance(tx_hash, str):
                    continue

                if tx_hash in seen_transactions:
                    continue

                tx_hashes.append(tx_hash)

                if len(tx_hashes) >= (
                    MAX_TRANSACTIONS_PER_WALLET
                ):
                    break

            # ------------------------------------------------
            # Global transaction budget
            # ------------------------------------------------

            remaining = (
                MAX_TOTAL_TRANSACTIONS
                - len(seen_transactions)
            )

            if remaining <= 0:
                break

            tx_hashes = tx_hashes[:remaining]

            if not tx_hashes:
                continue

            # ------------------------------------------------
            # Fetch details
            # ------------------------------------------------

            try:

                transaction_details = (
                    await fetch_transactions_batch(
                        tx_hashes
                    )
                )

            except Exception:

                continue

            # ------------------------------------------------
            # Process transactions
            # ------------------------------------------------

            for tx in transaction_details:

                tx_hash = tx.get("tx_hash")

                if not isinstance(tx_hash, str):
                    continue

                if tx_hash in seen_transactions:
                    continue

                seen_transactions.add(tx_hash)

                counterparties_list = (
                    extract_counterparties(
                        wallet,
                        tx,
                    )
                )

                for counterparty in (
                    counterparties_list
                ):

                    other_wallet = (
                        counterparty.get(
                            "address"
                        )
                    )

                    if not other_wallet:
                        continue

                    if other_wallet == wallet:
                        continue

                    # ----------------------------------------
                    # Add wallet node
                    # ----------------------------------------

                    if (
                        other_wallet
                        not in wallet_nodes
                    ):

                        wallet_nodes[
                            other_wallet
                        ] = {
                            "address":
                                other_wallet,
                            "hop":
                                current_hop,
                        }

                    # ----------------------------------------
                    # Add edge
                    # ----------------------------------------

                    edge_key = (
                        wallet,
                        other_wallet,
                        tx_hash,
                    )

                    if (
                        edge_key
                        not in seen_edges
                    ):

                        if len(edges_data) < MAX_EDGES:

                            seen_edges.add(
                                edge_key
                            )

                            edges_data.append(
                                {
                                    "from":
                                        wallet,
                                    "to":
                                        other_wallet,
                                    "tx_hash":
                                        tx_hash,
                                    "direction":
                                        counterparty.get(
                                            "direction",
                                            "unknown",
                                        ),
                                    "hop":
                                        current_hop,
                                    "block_height":
                                        tx.get(
                                            "block_height"
                                        ),
                                    "block_time":
                                        tx.get(
                                            "block_time"
                                        ),
                                }
                            )

                    # ----------------------------------------
                    # Prepare next hop
                    # ----------------------------------------

                    if current_hop < hops:

                        if (
                            other_wallet
                            not in processed_wallets
                            and other_wallet
                            not in next_level_seen
                        ):

                            if (
                                len(next_level)
                                < MAX_WALLETS_PER_HOP
                            ):

                                next_level_seen.add(
                                    other_wallet
                                )

                                next_level.append(
                                    other_wallet
                                )

        wallets_by_hop[
            f"hop_{current_hop}"
        ] = len(
            [
                node
                for node in wallet_nodes.values()
                if node.get("hop")
                == current_hop
            ]
        )

        current_level = next_level

        if (
            len(seen_transactions)
            >= MAX_TOTAL_TRANSACTIONS
        ):
            break

    # --------------------------------------------------------
    # Calculate hops actually traced
    # --------------------------------------------------------

    hops_traced = 0

    for hop_number in range(
        0,
        MAX_HOPS + 1,
    ):

        if (
            wallets_by_hop[
                f"hop_{hop_number}"
            ]
            > 0
        ):

            hops_traced = hop_number

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "network": "Cardano",
        "status": "LIVE",
        "root_wallet": address,

        "hops_requested": hops,
        "hops_traced": hops_traced,

        "wallets": len(wallet_nodes),
        "edges": len(edges_data),
        "transactions": len(
            seen_transactions
        ),

        "wallets_by_hop": {
            "hop_0":
                wallets_by_hop["hop_0"],
            "hop_1":
                wallets_by_hop["hop_1"],
            "hop_2":
                wallets_by_hop["hop_2"],
        },

        "wallet_nodes": list(
            wallet_nodes.values()
        ),

        "edges_data": edges_data,

        "investigation_limits": {
            "max_hops":
                MAX_HOPS,
            "max_wallets_per_hop":
                MAX_WALLETS_PER_HOP,
            "max_transactions_per_wallet":
                MAX_TRANSACTIONS_PER_WALLET,
            "max_total_transactions":
                MAX_TOTAL_TRANSACTIONS,
            "max_edges":
                MAX_EDGES,
        },

        "source": CARDANO_API,
        "explorer": explorer_address(address),
    }