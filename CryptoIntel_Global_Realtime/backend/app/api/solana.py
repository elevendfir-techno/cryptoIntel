from __future__ import annotations

from typing import Any
import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Query


router = APIRouter(
    prefix="/api/solana",
    tags=["solana"],
)


# ============================================================
# SOLANA CONFIG
# ============================================================

SOLANA_RPC = "https://api.mainnet-beta.solana.com"
SOLANA_EXPLORER = "https://solscan.io"

SPL_TOKEN_PROGRAM = (
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
)

TOKEN_2022_PROGRAM = (
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
)

# Controlled investigation limits.
MAX_HOPS = 2
MAX_WALLETS_PER_HOP = 5
MAX_TRANSACTIONS_PER_WALLET = 10
MAX_TOTAL_TRANSACTIONS = 60
MAX_EDGES = 100


# ============================================================
# RPC HELPER
# ============================================================

async def rpc_call(
    method: str,
    params: list[Any] | None = None,
) -> Any:

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or [],
    }

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        response = await client.post(
            SOLANA_RPC,
            json=payload,
            headers={
                "Content-Type": "application/json"
            },
        )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(
            str(data["error"])
        )

    return data.get("result")


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
async def health():

    try:

        result = await rpc_call(
            "getHealth"
        )

        return {
            "network": "Solana",
            "status": "LIVE",
            "health": result,
            "source": SOLANA_RPC,
            "explorer": SOLANA_EXPLORER,
        }

    except Exception as exc:

        return {
            "network": "Solana",
            "status": "UNAVAILABLE",
            "source": SOLANA_RPC,
            "error": str(exc),
        }


# ============================================================
# LATEST BLOCK
# ============================================================

@router.get("/latest-block")
async def latest_block():

    try:

        slot = await rpc_call(
            "getSlot",
            [
                {
                    "commitment": "finalized"
                }
            ],
        )

        block = await rpc_call(
            "getBlock",
            [
                slot,
                {
                    "commitment": "finalized",
                    "transactionDetails": "signatures",
                    "rewards": False,
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )

        return {
            "network": "Solana",
            "status": "LIVE",
            "slot": slot,
            "block": block,
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/block/{slot}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail={
                "network": "Solana",
                "status": "UNAVAILABLE",
                "error": str(exc),
            },
        )


# ============================================================
# SOL BALANCE
# ============================================================

@router.get("/balance/{address}")
async def balance(address: str):

    if not address:

        raise HTTPException(
            status_code=400,
            detail="Solana address is required",
        )

    try:

        result = await rpc_call(
            "getBalance",
            [
                address,
                {
                    "commitment": "finalized"
                },
            ],
        )

        value = result["value"]

        return {
            "address": address,
            "network": "Solana",
            "status": "LIVE",
            "native_asset": "SOL",
            "balance_lamports": value,
            "balance_sol": value / 1_000_000_000,
            "context": result.get("context"),
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/account/{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Solana balance lookup failed: {exc}"
            ),
        )


# ============================================================
# SINGLE TRANSACTION
# ============================================================

@router.get("/transaction/{signature}")
async def transaction(signature: str):

    if not signature:

        raise HTTPException(
            status_code=400,
            detail="Transaction signature is required",
        )

    try:

        result = await rpc_call(
            "getTransaction",
            [
                signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": "finalized",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )

        if result is None:

            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        return {
            "network": "Solana",
            "status": "LIVE",
            "signature": signature,
            "transaction": result,
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/tx/{signature}"
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Solana transaction lookup failed: {exc}"
            ),
        )


# ============================================================
# WALLET TRANSACTION HISTORY
# PAGINATION
# ============================================================

@router.get("/transactions/{address}")
async def transactions(
    address: str,
    limit: int = 50,
    before: str | None = None,
):

    if not address:

        raise HTTPException(
            status_code=400,
            detail="Solana address is required",
        )

    if limit < 1 or limit > 100:

        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 100",
        )

    try:

        options: dict[str, Any] = {
            "limit": limit
        }

        if before:
            options["before"] = before

        result = await rpc_call(
            "getSignaturesForAddress",
            [
                address,
                options,
            ],
        )

        txs = result or []

        next_cursor = None

        if txs:

            next_cursor = txs[-1].get(
                "signature"
            )

        return {
            "network": "Solana",
            "status": "LIVE",
            "address": address,
            "count": len(txs),
            "limit": limit,
            "before": before,
            "next_cursor": next_cursor,
            "transactions": txs,
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/account/{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Solana transaction history "
                f"lookup failed: {exc}"
            ),
        )


# ============================================================
# TOKEN ACCOUNTS
# ============================================================

@router.get("/token-accounts/{address}")
async def token_accounts(address: str):

    if not address:

        raise HTTPException(
            status_code=400,
            detail="Solana address is required",
        )

    try:

        spl_result = await rpc_call(
            "getTokenAccountsByOwner",
            [
                address,
                {
                    "programId": SPL_TOKEN_PROGRAM
                },
                {
                    "commitment": "finalized",
                    "encoding": "jsonParsed",
                },
            ],
        )

        token2022_result = await rpc_call(
            "getTokenAccountsByOwner",
            [
                address,
                {
                    "programId": TOKEN_2022_PROGRAM
                },
                {
                    "commitment": "finalized",
                    "encoding": "jsonParsed",
                },
            ],
        )

        accounts = []

        for item in (
            spl_result.get("value", [])
            if spl_result
            else []
        ):

            parsed = (
                item
                .get("account", {})
                .get("data", {})
                .get("parsed", {})
            )

            info = parsed.get(
                "info",
                {},
            )

            token_amount = info.get(
                "tokenAmount",
                {},
            )

            accounts.append(
                {
                    "token_account": item.get(
                        "pubkey"
                    ),
                    "program": "spl-token",
                    "program_id": SPL_TOKEN_PROGRAM,
                    "mint": info.get("mint"),
                    "owner": info.get("owner"),
                    "state": info.get("state"),
                    "amount": token_amount.get(
                        "amount"
                    ),
                    "decimals": token_amount.get(
                        "decimals"
                    ),
                    "ui_amount": token_amount.get(
                        "uiAmount"
                    ),
                    "ui_amount_string": token_amount.get(
                        "uiAmountString"
                    ),
                }
            )

        for item in (
            token2022_result.get("value", [])
            if token2022_result
            else []
        ):

            parsed = (
                item
                .get("account", {})
                .get("data", {})
                .get("parsed", {})
            )

            info = parsed.get(
                "info",
                {},
            )

            token_amount = info.get(
                "tokenAmount",
                {},
            )

            accounts.append(
                {
                    "token_account": item.get(
                        "pubkey"
                    ),
                    "program": "spl-token-2022",
                    "program_id": TOKEN_2022_PROGRAM,
                    "mint": info.get("mint"),
                    "owner": info.get("owner"),
                    "state": info.get("state"),
                    "amount": token_amount.get(
                        "amount"
                    ),
                    "decimals": token_amount.get(
                        "decimals"
                    ),
                    "ui_amount": token_amount.get(
                        "uiAmount"
                    ),
                    "ui_amount_string": token_amount.get(
                        "uiAmountString"
                    ),
                }
            )

        return {
            "network": "Solana",
            "status": "LIVE",
            "address": address,
            "count": len(accounts),
            "token_accounts": accounts,
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/account/{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Solana token account lookup "
                f"failed: {exc}"
            ),
        )


# ============================================================
# TOKEN TRANSFER PARSER
# ============================================================

def parse_token_transfers(
    address: str,
    signature: str,
    transaction: dict[str, Any],
) -> list[dict[str, Any]]:

    meta = transaction.get("meta")

    if not meta:
        return []

    if meta.get("err") is not None:
        return []

    pre_balances = (
        meta.get("preTokenBalances")
        or []
    )

    post_balances = (
        meta.get("postTokenBalances")
        or []
    )

    pre_map: dict[tuple, dict] = {}
    post_map: dict[tuple, dict] = {}

    for item in pre_balances:

        key = (
            item.get("accountIndex"),
            item.get("mint"),
            item.get("owner"),
        )

        pre_map[key] = item

    for item in post_balances:

        key = (
            item.get("accountIndex"),
            item.get("mint"),
            item.get("owner"),
        )

        post_map[key] = item

    transfers = []

    all_keys = (
        set(pre_map.keys())
        | set(post_map.keys())
    )

    for key in all_keys:

        pre = pre_map.get(
            key,
            {},
        )

        post = post_map.get(
            key,
            {},
        )

        owner = (
            post.get("owner")
            or pre.get("owner")
        )

        if owner != address:
            continue

        mint = (
            post.get("mint")
            or pre.get("mint")
        )

        if not mint:
            continue

        pre_amount = int(
            pre.get(
                "uiTokenAmount",
                {},
            ).get(
                "amount",
                "0",
            )
        )

        post_amount = int(
            post.get(
                "uiTokenAmount",
                {},
            ).get(
                "amount",
                "0",
            )
        )

        difference = (
            post_amount
            - pre_amount
        )

        if difference == 0:
            continue

        token_data = (
            post.get(
                "uiTokenAmount",
                {},
            )
            or pre.get(
                "uiTokenAmount",
                {},
            )
        )

        decimals = token_data.get(
            "decimals",
            0,
        )

        amount = abs(difference) / (
            10 ** decimals
        )

        direction = (
            "RECEIVED"
            if difference > 0
            else "SENT"
        )

        transfers.append(
            {
                "signature": signature,
                "slot": transaction.get(
                    "slot"
                ),
                "block_time": transaction.get(
                    "blockTime"
                ),
                "mint": mint,
                "owner": owner,
                "direction": direction,
                "amount_raw": abs(
                    difference
                ),
                "amount": amount,
                "decimals": decimals,
                "token_account_index": key[0],
                "status": "SUCCESS",
                "explorer": (
                    f"{SOLANA_EXPLORER}/tx/"
                    f"{signature}"
                ),
            }
        )

    return transfers


# ============================================================
# TOKEN TRANSFERS
# OPTIMIZED VERSION
# ============================================================

@router.get("/token-transfers/{address}")
async def token_transfers(
    address: str,
    limit: int = 20,
    before: str | None = None,
):

    if not address:

        raise HTTPException(
            status_code=400,
            detail="Solana address is required",
        )

    if limit < 1 or limit > 50:

        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 50",
        )

    try:

        signature_options = {
            "limit": limit
        }

        if before:
            signature_options["before"] = before

        signature_result = await rpc_call(
            "getSignaturesForAddress",
            [
                address,
                signature_options,
            ],
        )

        signature_records = (
            signature_result or []
        )

        if not signature_records:

            return {
                "network": "Solana",
                "status": "LIVE",
                "address": address,
                "count": 0,
                "limit": limit,
                "before": before,
                "next_cursor": None,
                "transfers": [],
                "source": SOLANA_RPC,
                "explorer": (
                    f"{SOLANA_EXPLORER}/account/{address}"
                ),
            }

        async def fetch_transaction(
            record: dict[str, Any]
        ):

            signature = record.get(
                "signature"
            )

            if not signature:
                return None

            try:

                transaction = await rpc_call(
                    "getTransaction",
                    [
                        signature,
                        {
                            "encoding": "jsonParsed",
                            "commitment": "finalized",
                            "maxSupportedTransactionVersion": 0,
                        },
                    ],
                )

                return {
                    "signature": signature,
                    "transaction": transaction,
                }

            except Exception:

                return None

        results = await asyncio.gather(
            *[
                fetch_transaction(record)
                for record in signature_records
            ]
        )

        transfers = []

        for result in results:

            if not result:
                continue

            signature = result.get(
                "signature"
            )

            transaction = result.get(
                "transaction"
            )

            if not transaction:
                continue

            parsed = parse_token_transfers(
                address=address,
                signature=signature,
                transaction=transaction,
            )

            transfers.extend(parsed)

        transfers.sort(
            key=lambda item: (
                item.get(
                    "block_time"
                )
                or 0
            ),
            reverse=True,
        )

        next_cursor = None

        if signature_records:

            next_cursor = signature_records[-1].get(
                "signature"
            )

        return {
            "network": "Solana",
            "status": "LIVE",
            "address": address,
            "count": len(transfers),
            "transactions_scanned": len(
                signature_records
            ),
            "limit": limit,
            "before": before,
            "next_cursor": next_cursor,
            "transfers": transfers,
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/account/{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Solana token transfer lookup "
                f"failed: {exc}"
            ),
        )


# ============================================================
# INVESTIGATION HELPERS
# ============================================================

def get_transaction_account_keys(
    transaction: dict[str, Any],
) -> list[str]:

    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    account_keys = (
        message.get("accountKeys")
        or []
    )

    keys: list[str] = []

    for item in account_keys:

        if isinstance(item, str):

            keys.append(item)

        elif isinstance(item, dict):

            pubkey = item.get("pubkey")

            if pubkey:
                keys.append(pubkey)

    return keys


def get_balance_deltas(
    transaction: dict[str, Any],
) -> dict[str, int]:

    meta = transaction.get("meta") or {}

    pre_balances = (
        meta.get("preBalances")
        or []
    )

    post_balances = (
        meta.get("postBalances")
        or []
    )

    keys = get_transaction_account_keys(
        transaction
    )

    deltas: dict[str, int] = {}

    for index, address in enumerate(keys):

        if index >= len(pre_balances):
            continue

        if index >= len(post_balances):
            continue

        difference = (
            int(post_balances[index])
            - int(pre_balances[index])
        )

        if difference == 0:
            continue

        deltas[address] = difference

    return deltas


def get_token_owner_deltas(
    transaction: dict[str, Any],
) -> dict[tuple[str, str], int]:

    meta = transaction.get("meta") or {}

    pre_balances = (
        meta.get("preTokenBalances")
        or []
    )

    post_balances = (
        meta.get("postTokenBalances")
        or []
    )

    pre_map: dict[tuple[str, str], int] = {}
    post_map: dict[tuple[str, str], int] = {}

    for item in pre_balances:

        owner = item.get("owner")
        mint = item.get("mint")

        if not owner or not mint:
            continue

        amount = int(
            item.get(
                "uiTokenAmount",
                {},
            ).get(
                "amount",
                "0",
            )
        )

        pre_map[(owner, mint)] = amount

    for item in post_balances:

        owner = item.get("owner")
        mint = item.get("mint")

        if not owner or not mint:
            continue

        amount = int(
            item.get(
                "uiTokenAmount",
                {},
            ).get(
                "amount",
                "0",
            )
        )

        post_map[(owner, mint)] = amount

    all_keys = (
        set(pre_map.keys())
        | set(post_map.keys())
    )

    deltas: dict[tuple[str, str], int] = {}

    for key in all_keys:

        difference = (
            post_map.get(key, 0)
            - pre_map.get(key, 0)
        )

        if difference != 0:

            deltas[key] = difference

    return deltas


def extract_counterparties_from_transaction(
    investigated_address: str,
    signature: str,
    transaction: dict[str, Any],
) -> list[dict[str, Any]]:

    if not transaction:
        return []

    meta = transaction.get("meta") or {}

    if meta.get("err") is not None:
        return []

    candidates: dict[
        str,
        dict[str, Any]
    ] = {}

    # --------------------------------------------------------
    # NATIVE SOL BALANCE CHANGES
    # --------------------------------------------------------

    native_deltas = get_balance_deltas(
        transaction
    )

    account_keys = get_transaction_account_keys(
        transaction
    )

    for address, delta in native_deltas.items():

        if address == investigated_address:
            continue

        if address not in account_keys:
            continue

        if delta == 0:
            continue

        if address not in candidates:

            candidates[address] = {
                "address": address,
                "native_delta_lamports": delta,
                "token_deltas": [],
                "signature": signature,
                "slot": transaction.get(
                    "slot"
                ),
                "block_time": transaction.get(
                    "blockTime"
                ),
                "explorer": (
                    f"{SOLANA_EXPLORER}/tx/"
                    f"{signature}"
                ),
            }

    # --------------------------------------------------------
    # SPL / TOKEN-2022 OWNER BALANCE CHANGES
    # --------------------------------------------------------

    token_deltas = get_token_owner_deltas(
        transaction
    )

    for (
        owner,
        mint,
    ), delta in token_deltas.items():

        if owner == investigated_address:
            continue

        if delta == 0:
            continue

        if owner not in candidates:

            candidates[owner] = {
                "address": owner,
                "native_delta_lamports": 0,
                "token_deltas": [],
                "signature": signature,
                "slot": transaction.get(
                    "slot"
                ),
                "block_time": transaction.get(
                    "blockTime"
                ),
                "explorer": (
                    f"{SOLANA_EXPLORER}/tx/"
                    f"{signature}"
                ),
            }

        candidates[
            owner
        ][
            "token_deltas"
        ].append(
            {
                "mint": mint,
                "amount_raw": abs(delta),
                "direction": (
                    "RECEIVED"
                    if delta > 0
                    else "SENT"
                ),
            }
        )

    return list(
        candidates.values()
    )


async def fetch_recent_transactions_for_address(
    address: str,
    limit: int = MAX_TRANSACTIONS_PER_WALLET,
) -> list[dict[str, Any]]:

    signatures = await rpc_call(
        "getSignaturesForAddress",
        [
            address,
            {
                "limit": min(
                    limit,
                    100
                )
            },
        ],
    )

    records = signatures or []

    records = [
        item
        for item in records
        if item.get("err") is None
        and item.get("signature")
    ]

    async def fetch_one(
        record: dict[str, Any]
    ):

        signature = record.get(
            "signature"
        )

        try:

            result = await rpc_call(
                "getTransaction",
                [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "finalized",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            )

            if result is None:
                return None

            return {
                "signature": signature,
                "transaction": result,
            }

        except Exception:

            return None

    results = await asyncio.gather(
        *[
            fetch_one(record)
            for record in records
        ]
    )

    return [
        result
        for result in results
        if result is not None
    ]


# ============================================================
# COUNTERPARTIES
# ============================================================

@router.get("/counterparties/{address}")
async def counterparties(
    address: str,
    limit: int = Query(
        default=10,
        ge=1,
        le=25,
    ),
):

    if not address:

        raise HTTPException(
            status_code=400,
            detail="Solana address is required",
        )

    try:

        transactions_data = (
            await fetch_recent_transactions_for_address(
                address=address,
                limit=limit,
            )
        )

        counterparty_map: dict[
            str,
            dict[str, Any]
        ] = {}

        transactions_checked = 0

        for item in transactions_data:

            signature = item.get(
                "signature"
            )

            tx = item.get(
                "transaction"
            )

            if not tx:
                continue

            transactions_checked += 1

            extracted = (
                extract_counterparties_from_transaction(
                    investigated_address=address,
                    signature=signature,
                    transaction=tx,
                )
            )

            for counterparty in extracted:

                cp_address = counterparty.get(
                    "address"
                )

                if not cp_address:
                    continue

                if cp_address not in counterparty_map:

                    counterparty_map[
                        cp_address
                    ] = {
                        "address": cp_address,
                        "interaction_count": 0,
                        "signatures": [],
                        "native_delta_lamports": 0,
                        "token_deltas": [],
                        "last_slot": None,
                        "last_block_time": None,
                    }

                item_data = counterparty_map[
                    cp_address
                ]

                item_data[
                    "interaction_count"
                ] += 1

                item_data[
                    "native_delta_lamports"
                ] += counterparty.get(
                    "native_delta_lamports",
                    0
                )

                signature_value = (
                    counterparty.get(
                        "signature"
                    )
                )

                if (
                    signature_value
                    and signature_value
                    not in item_data[
                        "signatures"
                    ]
                ):

                    item_data[
                        "signatures"
                    ].append(
                        signature_value
                    )

                token_deltas = (
                    counterparty.get(
                        "token_deltas"
                    )
                    or []
                )

                item_data[
                    "token_deltas"
                ].extend(
                    token_deltas
                )

                slot = counterparty.get(
                    "slot"
                )

                block_time = counterparty.get(
                    "block_time"
                )

                if (
                    item_data["last_slot"]
                    is None
                    or (
                        slot is not None
                        and slot
                        > item_data["last_slot"]
                    )
                ):

                    item_data[
                        "last_slot"
                    ] = slot

                if (
                    item_data["last_block_time"]
                    is None
                    or (
                        block_time is not None
                        and block_time
                        > item_data[
                            "last_block_time"
                        ]
                    )
                ):

                    item_data[
                        "last_block_time"
                    ] = block_time

        counterparties_list = list(
            counterparty_map.values()
        )

        counterparties_list.sort(
            key=lambda item: (
                item.get(
                    "interaction_count",
                    0
                ),
                item.get(
                    "last_slot"
                )
                or 0,
            ),
            reverse=True,
        )

        for item in counterparties_list:

            item["explorer"] = (
                f"{SOLANA_EXPLORER}/account/"
                f"{item['address']}"
            )

        return {
            "network": "Solana",
            "status": "LIVE",
            "root_wallet": address,
            "transactions_checked": (
                transactions_checked
            ),
            "counterparty_count": len(
                counterparties_list
            ),
            "counterparties": (
                counterparties_list
            ),
            "investigation_limits": {
                "transactions_per_wallet": limit,
                "source": SOLANA_RPC,
                "commitment": "finalized",
            },
            "source": SOLANA_RPC,
            "explorer": (
                f"{SOLANA_EXPLORER}/account/{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Solana counterparty lookup "
                f"failed: {exc}"
            ),
        )


# ============================================================
# FUND FLOW
# 1-HOP / 2-HOP
# ============================================================

@router.get("/fundflow/{address}")
async def fundflow(
    address: str,
    hops: int = Query(
        default=1,
        ge=1,
        le=2,
    ),
):

    if not address:

        raise HTTPException(
            status_code=400,
            detail="Solana address is required",
        )

    try:

        # ----------------------------------------------------
        # GRAPH STATE
        # ----------------------------------------------------

        wallet_nodes: dict[
            str,
            dict[str, Any]
        ] = {}

        edges: list[
            dict[str, Any]
        ] = []

        processed_wallets: set[str] = set()

        transaction_cache: dict[
            str,
            list[dict[str, Any]]
        ] = {}

        total_transactions = 0

        # Tracks the deepest hop that was actually processed.
        deepest_processed_hop = 0

        # ----------------------------------------------------
        # ROOT WALLET
        # ----------------------------------------------------

        wallet_nodes[address] = {
            "address": address,
            "hop": 0,
            "type": "root",
            "explorer": (
                f"{SOLANA_EXPLORER}/account/"
                f"{address}"
            ),
        }

        current_wallets = [
            address
        ]

        # ----------------------------------------------------
        # HOP LOOP
        # ----------------------------------------------------

        for current_hop in range(
            1,
            hops + 1
        ):

            if not current_wallets:
                break

            # This hop is actually being processed.
            deepest_processed_hop = current_hop

            # Keep investigation controlled.
            wallets_to_process = (
                current_wallets[
                    :MAX_WALLETS_PER_HOP
                ]
            )

            if not wallets_to_process:
                break

            next_wallets: list[str] = []

            # ------------------------------------------------
            # PROCESS WALLETS CONCURRENTLY
            # ------------------------------------------------

            async def process_wallet(
                wallet: str
            ):

                if wallet in processed_wallets:

                    return (
                        wallet,
                        [],
                        0,
                    )

                processed_wallets.add(
                    wallet
                )

                try:

                    if (
                        wallet
                        not in transaction_cache
                    ):

                        remaining_budget = (
                            MAX_TOTAL_TRANSACTIONS
                            - total_transactions
                        )

                        if remaining_budget <= 0:

                            return (
                                wallet,
                                [],
                                0,
                            )

                        fetch_limit = min(
                            MAX_TRANSACTIONS_PER_WALLET,
                            remaining_budget,
                        )

                        transaction_cache[
                            wallet
                        ] = (
                            await fetch_recent_transactions_for_address(
                                address=wallet,
                                limit=fetch_limit,
                            )
                        )

                    txs = transaction_cache[
                        wallet
                    ]

                    return (
                        wallet,
                        txs,
                        len(txs),
                    )

                except Exception:

                    return (
                        wallet,
                        [],
                        0,
                    )

            results = await asyncio.gather(
                *[
                    process_wallet(wallet)
                    for wallet
                    in wallets_to_process
                ]
            )

            # ------------------------------------------------
            # EXTRACT GRAPH RELATIONSHIPS
            # ------------------------------------------------

            for (
                wallet,
                txs,
                transaction_count,
            ) in results:

                if (
                    total_transactions
                    >= MAX_TOTAL_TRANSACTIONS
                ):
                    break

                total_transactions += (
                    transaction_count
                )

                for item in txs:

                    if (
                        len(edges)
                        >= MAX_EDGES
                    ):
                        break

                    signature = item.get(
                        "signature"
                    )

                    tx = item.get(
                        "transaction"
                    )

                    if not tx:
                        continue

                    counterparties_found = (
                        extract_counterparties_from_transaction(
                            investigated_address=wallet,
                            signature=signature,
                            transaction=tx,
                        )
                    )

                    # Deduplicate counterparties
                    # inside the same transaction.
                    seen_in_transaction: set[
                        str
                    ] = set()

                    for counterparty in (
                        counterparties_found
                    ):

                        cp_address = (
                            counterparty.get(
                                "address"
                            )
                        )

                        if not cp_address:
                            continue

                        if (
                            cp_address
                            == wallet
                        ):
                            continue

                        if (
                            cp_address
                            in seen_in_transaction
                        ):
                            continue

                        seen_in_transaction.add(
                            cp_address
                        )

                        # ------------------------------------------------
                        # NODE CREATION
                        #
                        # Important:
                        # Existing nodes keep their original shortest hop.
                        # ------------------------------------------------

                        if (
                            cp_address
                            not in wallet_nodes
                        ):

                            wallet_nodes[
                                cp_address
                            ] = {
                                "address": (
                                    cp_address
                                ),
                                "hop": (
                                    current_hop
                                ),
                                "type": (
                                    "counterparty"
                                ),
                                "explorer": (
                                    f"{SOLANA_EXPLORER}"
                                    f"/account/"
                                    f"{cp_address}"
                                ),
                            }

                        # ------------------------------------------------
                        # EDGE
                        # ------------------------------------------------

                        edges.append(
                            {
                                "from": wallet,
                                "to": cp_address,
                                "hop": current_hop,
                                "signature": (
                                    signature
                                ),
                                "slot": tx.get(
                                    "slot"
                                ),
                                "block_time": (
                                    tx.get(
                                        "blockTime"
                                    )
                                ),
                                "native_delta_lamports": (
                                    counterparty.get(
                                        "native_delta_lamports",
                                        0,
                                    )
                                ),
                                "token_deltas": (
                                    counterparty.get(
                                        "token_deltas",
                                        [],
                                    )
                                ),
                                "status": (
                                    "SUCCESS"
                                ),
                                "explorer": (
                                    f"{SOLANA_EXPLORER}"
                                    f"/tx/"
                                    f"{signature}"
                                ),
                            }
                        )

                        # ------------------------------------------------
                        # PREPARE NEXT HOP
                        # ------------------------------------------------

                        if (
                            current_hop
                            < hops
                        ):

                            if (
                                cp_address
                                not in processed_wallets
                                and cp_address
                                not in next_wallets
                            ):

                                next_wallets.append(
                                    cp_address
                                )

                        if (
                            len(edges)
                            >= MAX_EDGES
                        ):
                            break

                    if (
                        len(edges)
                        >= MAX_EDGES
                    ):
                        break

            # ------------------------------------------------
            # MOVE TO NEXT HOP
            # ------------------------------------------------

            current_wallets = (
                next_wallets[
                    :MAX_WALLETS_PER_HOP
                ]
            )

            if (
                len(edges)
                >= MAX_EDGES
            ):
                break

        # ----------------------------------------------------
        # NORMALIZE HOP COUNTS
        # ----------------------------------------------------

        wallets_by_hop: dict[
            str,
            int
        ] = {}

        for node in wallet_nodes.values():

            hop_value = node.get(
                "hop",
                0
            )

            key = f"hop_{hop_value}"

            wallets_by_hop[key] = (
                wallets_by_hop.get(
                    key,
                    0
                )
                + 1
            )

        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        return {
            "network": "Solana",
            "status": "LIVE",
            "root_wallet": address,
            "hops_requested": hops,

            # IMPORTANT:
            # This now reports actual processing depth,
            # not just the largest node hop.
            "hops_traced": (
                deepest_processed_hop
            ),

            "wallets": len(
                wallet_nodes
            ),

            "edges": len(
                edges
            ),

            "transactions": (
                total_transactions
            ),

            "wallets_by_hop": (
                wallets_by_hop
            ),

            "wallet_nodes": list(
                wallet_nodes.values()
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
                "commitment": "finalized",
                "source": SOLANA_RPC,
            },

            "source": SOLANA_RPC,

            "explorer": (
                f"{SOLANA_EXPLORER}/account/"
                f"{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail={
                "network": "Solana",
                "status": "UNAVAILABLE",
                "error": (
                    "Solana fund-flow lookup "
                    f"failed: {exc}"
                ),
            },
        )