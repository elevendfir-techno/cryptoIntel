from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException


router = APIRouter(
    prefix="/api/xrpl",
    tags=["xrpl"],
)


# ============================================================
# XRPL CONFIG
# ============================================================

XRPL_RPC = "https://xrplcluster.com"
XRPL_EXPLORER = "https://xrpscan.com"


# ============================================================
# FUND-FLOW SAFETY / INVESTIGATION LIMITS
# ============================================================

MAX_HOPS = 2

# Maximum number of wallets expanded at the next level.
MAX_WALLETS_PER_HOP = 10

# Maximum transactions requested for each wallet.
MAX_TRANSACTIONS_PER_WALLET = 25

# Maximum total transaction records processed by fund-flow.
MAX_TOTAL_TRANSACTIONS = 100

# Maximum graph edges returned.
MAX_EDGES = 150


# ============================================================
# XRPL RPC
# ============================================================

async def rpc_call(
    method: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """
    Execute a JSON-RPC request against XRPL Mainnet.
    """

    payload = {
        "method": method,
        "params": [params or {}],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                XRPL_RPC,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                },
            )

        response.raise_for_status()

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"XRPL RPC request failed: {exc}",
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="XRPL RPC returned invalid JSON.",
        )

    if data.get("status") == "error":
        raise HTTPException(
            status_code=502,
            detail=f"XRPL RPC error: {data}",
        )

    result = data.get("result")

    if result is None:
        raise HTTPException(
            status_code=502,
            detail="XRPL RPC returned no result.",
        )

    return result


# ============================================================
# ADDRESS VALIDATION
# ============================================================

def validate_xrpl_address(address: str) -> bool:
    """
    Basic XRPL classic-address validation.

    Classic XRPL accounts normally begin with 'r'.
    """

    return (
        isinstance(address, str)
        and address.startswith("r")
        and 25 <= len(address) <= 35
    )


# ============================================================
# XRP CONVERSION
# ============================================================

def drops_to_xrp(value: str | int) -> float:
    """
    Convert XRP drops to XRP.

    1 XRP = 1,000,000 drops.
    """

    try:
        return int(value) / 1_000_000
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# PAYMENT AMOUNT NORMALIZATION
# ============================================================

def extract_payment_amount(amount: Any) -> dict[str, Any]:
    """
    Normalize XRPL Payment Amount.

    Native XRP:

        "1000000"

    Issued currency:

        {
            "currency": "USD",
            "issuer": "r...",
            "value": "10"
        }
    """

    if isinstance(amount, str):
        return {
            "asset_type": "XRP",
            "currency": "XRP",
            "issuer": None,
            "amount": drops_to_xrp(amount),
            "raw_amount": amount,
            "unit": "XRP",
        }

    if isinstance(amount, dict):
        return {
            "asset_type": "issued_currency",
            "currency": amount.get("currency"),
            "issuer": amount.get("issuer"),
            "amount": amount.get("value"),
            "raw_amount": amount,
            "unit": amount.get("currency"),
        }

    return {
        "asset_type": "unknown",
        "currency": None,
        "issuer": None,
        "amount": None,
        "raw_amount": amount,
        "unit": None,
    }


# ============================================================
# PAYMENT EXTRACTION
# ============================================================

def extract_payment(
    tx: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Convert an XRPL Payment transaction into
    investigation-friendly data.
    """

    if tx.get("TransactionType") != "Payment":
        return None

    sender = tx.get("Account")
    receiver = tx.get("Destination")

    if not sender or not receiver:
        return None

    return {
        "transaction_type": "Payment",
        "hash": tx.get("hash") or tx.get("tx_hash"),
        "sender": sender,
        "receiver": receiver,
        "amount": extract_payment_amount(
            tx.get("Amount")
        ),
        "ledger_index": (
            tx.get("ledger_index")
            or tx.get("inLedger")
        ),
        "date": tx.get("date"),
        "validated": tx.get(
            "validated",
            False,
        ),
        "destination_tag": tx.get(
            "DestinationTag"
        ),
        "source_tag": tx.get(
            "SourceTag"
        ),
    }


# ============================================================
# NORMALIZE ACCOUNT_TX RECORD
# ============================================================

def normalize_transaction(
    item: dict[str, Any],
) -> dict[str, Any] | None:
    """
    XRPL account_tx can return transaction fields
    directly or inside tx.
    """

    if not isinstance(item, dict):
        return None

    tx = item.get("tx", item)

    if not isinstance(tx, dict):
        return None

    return {
        **tx,
        "validated": item.get(
            "validated",
            tx.get("validated", False),
        ),
    }


# ============================================================
# EXTRACT COUNTERPARTIES
# ============================================================

def extract_counterparties(
    address: str,
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build direct counterparties for an XRPL wallet.
    """

    counterparty_map: dict[
        str,
        dict[str, Any],
    ] = {}

    for tx in transactions:
        payment = extract_payment(tx)

        if not payment:
            continue

        sender = payment["sender"]
        receiver = payment["receiver"]

        if sender == address:
            counterparty = receiver
            direction = "outgoing"

        elif receiver == address:
            counterparty = sender
            direction = "incoming"

        else:
            continue

        key = f"{counterparty}:{direction}"

        if key not in counterparty_map:
            counterparty_map[key] = {
                "address": counterparty,
                "direction": direction,
                "payments": 0,
                "total_xrp": 0.0,
                "transactions": [],
            }

        item = counterparty_map[key]

        item["payments"] += 1

        amount = payment["amount"]

        if (
            amount["asset_type"] == "XRP"
            and isinstance(
                amount["amount"],
                (int, float),
            )
        ):
            item["total_xrp"] += amount["amount"]

        if payment["hash"]:
            item["transactions"].append(
                payment["hash"]
            )

    return list(
        counterparty_map.values()
    )


# ============================================================
# FETCH ACCOUNT TRANSACTIONS
# ============================================================

async def fetch_account_transactions(
    address: str,
    limit: int = MAX_TRANSACTIONS_PER_WALLET,
) -> list[dict[str, Any]]:
    """
    Fetch a page of validated account transactions.

    Used internally by fund-flow.
    """

    result = await rpc_call(
        "account_tx",
        {
            "account": address,
            "ledger_index_min": -1,
            "ledger_index_max": -1,
            "binary": False,
            "forward": False,
            "limit": limit,
        },
    )

    raw_transactions = result.get(
        "transactions",
        [],
    )

    transactions: list[dict[str, Any]] = []

    for item in raw_transactions:
        tx = normalize_transaction(item)

        if tx:
            transactions.append(tx)

    return transactions


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
async def health():
    """
    Check XRPL Mainnet connectivity.
    """

    result = await rpc_call(
        "server_info",
        {},
    )

    info = result.get(
        "info",
        result,
    )

    validated_ledger = info.get(
        "validated_ledger",
        {},
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "ledger_index": validated_ledger.get(
            "seq"
        ),
        "server_state": info.get(
            "server_state"
        ),
        "source": XRPL_RPC,
        "explorer": XRPL_EXPLORER,
    }


# ============================================================
# LATEST LEDGER
# ============================================================

@router.get("/latest-ledger")
async def latest_ledger():
    """
    Return the latest validated XRPL ledger.
    """

    result = await rpc_call(
        "ledger",
        {
            "ledger_index": "validated",
            "transactions": True,
            "expand": True,
        },
    )

    ledger = result.get(
        "ledger",
        {},
    )

    transactions = ledger.get(
        "transactions",
        [],
    )

    ledger_index = ledger.get(
        "ledger_index"
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "ledger_index": ledger_index,
        "ledger_hash": ledger.get(
            "ledger_hash"
        ),
        "close_time": ledger.get(
            "close_time"
        ),
        "transaction_count": len(
            transactions
        ),
        "source": XRPL_RPC,
        "explorer": (
            f"{XRPL_EXPLORER}/ledger/"
            f"{ledger_index}"
        ),
    }


# ============================================================
# ACCOUNT
# ============================================================

@router.get("/account/{address}")
async def account(
    address: str,
):
    """
    Get live XRPL account information.
    """

    if not validate_xrpl_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid XRPL classic address.",
        )

    result = await rpc_call(
        "account_info",
        {
            "account": address,
            "ledger_index": "validated",
        },
    )

    account_data = result.get(
        "account",
        {},
    )

    balance_drops = account_data.get(
        "Balance",
        "0",
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "address": address,
        "account": account_data,
        "balance_xrp": drops_to_xrp(
            balance_drops
        ),
        "balance_drops": balance_drops,
        "ledger_index": result.get(
            "ledger_index"
        ),
        "source": XRPL_RPC,
        "explorer": (
            f"{XRPL_EXPLORER}/account/"
            f"{address}"
        ),
    }


# ============================================================
# SINGLE TRANSACTION
# ============================================================

@router.get("/transaction/{tx_hash}")
async def transaction(
    tx_hash: str,
):
    """
    Get one XRPL transaction.
    """

    result = await rpc_call(
        "tx",
        {
            "transaction": tx_hash,
            "binary": False,
        },
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "transaction": result,
        "source": XRPL_RPC,
        "explorer": (
            f"{XRPL_EXPLORER}/tx/"
            f"{tx_hash}"
        ),
    }


# ============================================================
# TRANSACTION HISTORY + PAGINATION
# ============================================================

@router.get("/transactions/{address}")
async def transactions(
    address: str,
    limit: int = 20,
    marker: str | None = None,
):
    """
    Get XRPL account transaction history.

    marker must be passed as JSON string.

    Example:

        {"ledger":106492264,"seq":46}
    """

    if not validate_xrpl_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid XRPL classic address.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100.",
        )

    params: dict[str, Any] = {
        "account": address,
        "ledger_index_min": -1,
        "ledger_index_max": -1,
        "binary": False,
        "forward": False,
        "limit": limit,
    }

    if marker:
        try:
            parsed_marker = json.loads(
                marker
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid marker. "
                    "Copy the complete marker "
                    "object from the previous "
                    "response as JSON."
                ),
            )

        if not isinstance(
            parsed_marker,
            dict,
        ):
            raise HTTPException(
                status_code=400,
                detail="Marker must be a JSON object.",
            )

        params["marker"] = parsed_marker

    result = await rpc_call(
        "account_tx",
        params,
    )

    raw_transactions = result.get(
        "transactions",
        [],
    )

    txs: list[dict[str, Any]] = []

    for item in raw_transactions:
        tx = normalize_transaction(item)

        if tx:
            txs.append(tx)

    next_marker = result.get(
        "marker"
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "address": address,
        "limit": limit,
        "transactions_returned": len(
            txs
        ),
        "transactions": txs,
        "marker": next_marker,
        "has_more": (
            next_marker is not None
        ),
        "source": XRPL_RPC,
        "explorer": (
            f"{XRPL_EXPLORER}/account/"
            f"{address}"
        ),
    }


# ============================================================
# PAYMENTS + PAGINATION
# ============================================================

@router.get("/payments/{address}")
async def payments(
    address: str,
    limit: int = 20,
    marker: str | None = None,
):
    """
    Extract real XRPL Payment transactions.
    """

    if not validate_xrpl_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid XRPL classic address.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100.",
        )

    params: dict[str, Any] = {
        "account": address,
        "ledger_index_min": -1,
        "ledger_index_max": -1,
        "binary": False,
        "forward": False,
        "limit": limit,
    }

    if marker:
        try:
            parsed_marker = json.loads(
                marker
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid marker JSON.",
            )

        if not isinstance(
            parsed_marker,
            dict,
        ):
            raise HTTPException(
                status_code=400,
                detail="Marker must be a JSON object.",
            )

        params["marker"] = parsed_marker

    result = await rpc_call(
        "account_tx",
        params,
    )

    raw_transactions = result.get(
        "transactions",
        [],
    )

    payment_transactions: list[
        dict[str, Any]
    ] = []

    for item in raw_transactions:
        tx = normalize_transaction(item)

        if not tx:
            continue

        payment = extract_payment(tx)

        if payment:
            payment_transactions.append(
                payment
            )

    next_marker = result.get(
        "marker"
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "address": address,
        "limit": limit,
        "payments_returned": len(
            payment_transactions
        ),
        "payments": payment_transactions,
        "marker": next_marker,
        "has_more": (
            next_marker is not None
        ),
        "source": XRPL_RPC,
        "explorer": (
            f"{XRPL_EXPLORER}/account/"
            f"{address}"
        ),
    }


# ============================================================
# COUNTERPARTIES
# ============================================================

@router.get("/counterparties/{address}")
async def counterparties(
    address: str,
    limit: int = 50,
):
    """
    Find direct payment counterparties.
    """

    if not validate_xrpl_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid XRPL classic address.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100.",
        )

    transactions_data = (
        await fetch_account_transactions(
            address,
            limit,
        )
    )

    payment_count = sum(
        1
        for tx in transactions_data
        if tx.get("TransactionType")
        == "Payment"
    )

    direct_counterparties = (
        extract_counterparties(
            address,
            transactions_data,
        )
    )

    return {
        "network": "XRP Ledger",
        "status": "LIVE",
        "root_wallet": address,
        "transactions_scanned": len(
            transactions_data
        ),
        "payment_transactions": payment_count,
        "counterparties": len(
            direct_counterparties
        ),
        "direct_counterparties": (
            direct_counterparties
        ),
        "source": XRPL_RPC,
        "explorer": (
            f"{XRPL_EXPLORER}/account/"
            f"{address}"
        ),
    }


# ============================================================
# 2-HOP FUND FLOW
# ============================================================

@router.get("/fundflow/{address}")
async def fundflow(
    address: str,
    limit: int = 25,
):
    """
    XRPL 2-hop fund-flow investigation.

    Hop 0:
        Root wallet.

    Hop 1:
        Direct payment counterparties.

    Hop 2:
        Counterparties of Hop-1 wallets.

    Real XRPL Mainnet transaction data is used.

    Investigation budgets prevent uncontrolled
    recursive requests.
    """

    if not validate_xrpl_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid XRPL classic address.",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100.",
        )

    # Use a safe internal limit.
    wallet_tx_limit = min(
        limit,
        MAX_TRANSACTIONS_PER_WALLET,
    )

    # --------------------------------------------------------
    # GRAPH STORAGE
    # --------------------------------------------------------

    wallets: dict[
        str,
        dict[str, Any],
    ] = {}

    edges: list[
        dict[str, Any]
    ] = []

    seen_edges: set[
        tuple[str, str, str]
    ] = set()

    seen_transactions: set[str] = set()

    total_transactions_scanned = 0

    # --------------------------------------------------------
    # HOP 0
    # --------------------------------------------------------

    wallets[address] = {
        "address": address,
        "hop": 0,
        "is_root": True,
    }

    # Current level starts with root.
    current_level = [address]

    # --------------------------------------------------------
    # HOP 1 + HOP 2
    # --------------------------------------------------------

    for current_hop in range(
        0,
        MAX_HOPS,
    ):
        if not current_level:
            break

        next_level_candidates: list[str] = []

        # Avoid expanding too many wallets.
        wallets_to_process = current_level[
            :MAX_WALLETS_PER_HOP
        ]

        for current_wallet in wallets_to_process:

            if (
                total_transactions_scanned
                >= MAX_TOTAL_TRANSACTIONS
            ):
                break

            # ------------------------------------------------
            # Fetch real XRPL transactions
            # ------------------------------------------------

            remaining_budget = (
                MAX_TOTAL_TRANSACTIONS
                - total_transactions_scanned
            )

            wallet_limit = min(
                wallet_tx_limit,
                remaining_budget,
            )

            if wallet_limit <= 0:
                break

            wallet_transactions = (
                await fetch_account_transactions(
                    current_wallet,
                    wallet_limit,
                )
            )

            total_transactions_scanned += len(
                wallet_transactions
            )

            # ------------------------------------------------
            # Extract Payments
            # ------------------------------------------------

            for tx in wallet_transactions:

                payment = extract_payment(tx)

                if not payment:
                    continue

                tx_hash = payment.get(
                    "hash"
                )

                if tx_hash:
                    if tx_hash in seen_transactions:
                        # We already processed this
                        # transaction in another wallet.
                        continue

                    seen_transactions.add(
                        tx_hash
                    )

                sender = payment[
                    "sender"
                ]

                receiver = payment[
                    "receiver"
                ]

                # --------------------------------------------
                # Determine the other wallet
                # --------------------------------------------

                if sender == current_wallet:
                    counterparty = receiver
                    direction = "outgoing"

                elif receiver == current_wallet:
                    counterparty = sender
                    direction = "incoming"

                else:
                    continue

                # --------------------------------------------
                # Prevent duplicate graph edges
                # --------------------------------------------

                edge_key = (
                    sender,
                    receiver,
                    tx_hash or "",
                )

                if edge_key in seen_edges:
                    continue

                seen_edges.add(
                    edge_key
                )

                # --------------------------------------------
                # Add counterparty wallet
                # --------------------------------------------

                if counterparty not in wallets:
                    wallets[counterparty] = {
                        "address": counterparty,
                        "hop": current_hop + 1,
                        "is_root": False,
                    }

                # --------------------------------------------
                # Add next-level wallet
                # --------------------------------------------

                if (
                    current_hop + 1
                    <= MAX_HOPS
                ):
                    if (
                        counterparty
                        not in next_level_candidates
                    ):
                        next_level_candidates.append(
                            counterparty
                        )

                # --------------------------------------------
                # Add graph edge
                # --------------------------------------------

                if len(edges) < MAX_EDGES:
                    edges.append(
                        {
                            "from": sender,
                            "to": receiver,
                            "direction_from_current_wallet": (
                                direction
                            ),
                            "amount": payment[
                                "amount"
                            ],
                            "hash": payment[
                                "hash"
                            ],
                            "ledger_index": payment[
                                "ledger_index"
                            ],
                            "date": payment[
                                "date"
                            ],
                            "validated": payment[
                                "validated"
                            ],
                            "source_wallet": (
                                current_wallet
                            ),
                            "hop_from": current_hop,
                            "hop_to": (
                                current_hop + 1
                            ),
                        }
                    )

        # ----------------------------------------------------
        # Prepare next hop
        # ----------------------------------------------------

        # Remove already known wallets and keep
        # only a controlled number.
        unique_next_level: list[str] = []

        for wallet in next_level_candidates:
            if wallet not in unique_next_level:
                unique_next_level.append(
                    wallet
                )

        # Do not recursively expand root again.
        unique_next_level = [
            wallet
            for wallet in unique_next_level
            if wallet != address
        ]

        current_level = unique_next_level[
            :MAX_WALLETS_PER_HOP
        ]

    # --------------------------------------------------------
    # Calculate actual hops reached
    # --------------------------------------------------------

    hop_values = [
        node["hop"]
        for node in wallets.values()
    ]

    hops_traced = (
        max(hop_values)
        if hop_values
        else 0
    )

    # --------------------------------------------------------
    # Separate nodes by hop
    # --------------------------------------------------------

    hop_0_wallets = [
        node
        for node in wallets.values()
        if node["hop"] == 0
    ]

    hop_1_wallets = [
        node
        for node in wallets.values()
        if node["hop"] == 1
    ]

    hop_2_wallets = [
        node
        for node in wallets.values()
        if node["hop"] == 2
    ]

    # --------------------------------------------------------
    # Count payments
    # --------------------------------------------------------

    payment_edges = [
        edge
        for edge in edges
        if edge.get("amount")
    ]

    return {
        "network": "XRP Ledger",
        "status": "LIVE",

        "root_wallet": address,

        "hops_requested": MAX_HOPS,
        "hops_traced": hops_traced,

        "wallets": len(wallets),
        "edges": len(edges),

        "transactions": total_transactions_scanned,
        "payments": len(payment_edges),

        "wallets_by_hop": {
            "hop_0": len(hop_0_wallets),
            "hop_1": len(hop_1_wallets),
            "hop_2": len(hop_2_wallets),
        },

        "wallet_nodes": list(
            wallets.values()
        ),

        "edges_data": edges,

        "investigation_limits": {
            "max_hops": MAX_HOPS,
            "max_wallets_per_hop": (
                MAX_WALLETS_PER_HOP
            ),
            "max_transactions_per_wallet": (
                MAX_TRANSACTIONS_PER_WALLET
            ),
            "max_total_transactions": (
                MAX_TOTAL_TRANSACTIONS
            ),
            "max_edges": MAX_EDGES,
        },

        "source": XRPL_RPC,

        "explorer": (
            f"{XRPL_EXPLORER}/account/"
            f"{address}"
        ),
    }