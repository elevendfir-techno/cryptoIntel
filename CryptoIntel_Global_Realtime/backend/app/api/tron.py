from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query


router = APIRouter(
    prefix="/api/tron",
    tags=["tron"],
)


TRON_API = "https://api.trongrid.io"
TRON_EXPLORER = "https://tronscan.org"

# ============================================================
# SAFETY / PERFORMANCE LIMITS
# ============================================================

MAX_HOPS = 2

# Total records returned by the fund-flow response
MAX_TRANSACTIONS = 50
MAX_TRC20_TRANSFERS = 50

# Maximum wallets expanded at each hop
MAX_WALLETS_PER_HOP = 10

# Give every hop its own budget.
# This prevents Hop 1 from consuming the entire global budget.
MAX_TRANSACTIONS_PER_HOP = 25
MAX_TRC20_PER_HOP = 25


# ============================================================
# TRON BASE58 CHECK ENCODING
# ============================================================

BASE58_ALPHABET = (
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)


def base58_encode(data: bytes) -> str:
    """
    Encode bytes using Bitcoin-style Base58 alphabet.
    TRON uses Base58Check encoding for normal T... addresses.
    """

    number = int.from_bytes(data, "big")

    encoded = ""

    while number > 0:
        number, remainder = divmod(
            number,
            58,
        )

        encoded = (
            BASE58_ALPHABET[remainder]
            + encoded
        )

    # Preserve leading zero bytes.
    leading_zeroes = 0

    for byte in data:

        if byte == 0:

            leading_zeroes += 1

        else:

            break

    return (
        "1" * leading_zeroes
        + encoded
    )


def tron_hex_to_base58(
    value: str,
) -> str | None:
    """
    Convert a TRON hexadecimal address into
    a normal Base58Check T... address.

    Example hex form:

        41xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

    Normal TRON address:

        Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    """

    if not isinstance(value, str):

        return None

    value = value.strip()

    if value.startswith("0x"):

        value = value[2:]

    # TRON mainnet addresses are 21 bytes:
    # 41 + 20-byte account address.
    if len(value) != 42:

        return None

    if not value.lower().startswith("41"):

        return None

    try:

        payload = bytes.fromhex(value)

    except ValueError:

        return None

    # Base58Check:
    # payload + first 4 bytes of double SHA-256.
    import hashlib

    checksum = hashlib.sha256(
        hashlib.sha256(payload).digest()
    ).digest()[:4]

    return base58_encode(
        payload + checksum
    )


def normalize_tron_address(
    value: Any,
) -> str | None:
    """
    Normalize either:
      - Base58 TRON address (T...)
      - TRON hex address (41...)
    into Base58 T... format.
    """

    if not isinstance(value, str):

        return None

    value = value.strip()

    if (
        len(value) == 34
        and value.startswith("T")
    ):

        return value

    if len(value) == 42:

        return tron_hex_to_base58(
            value
        )

    return None


# ============================================================
# API GET
# ============================================================

async def api_get(
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:

    async with httpx.AsyncClient(
        timeout=30
    ) as client:

        response = await client.get(
            f"{TRON_API}{path}",
            params=params,
            headers={
                "Accept": "application/json",
            },
        )

    response.raise_for_status()

    return response.json()


# ============================================================
# ADDRESS VALIDATION
# ============================================================

def validate_tron_address(
    address: str,
) -> str:

    address = address.strip()

    if not address:

        raise HTTPException(
            status_code=400,
            detail="TRON address is required",
        )

    if (
        len(address) != 34
        or not address.startswith("T")
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid TRON address.",
        )

    return address


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
async def health():

    try:

        data = await api_get(
            "/wallet/getnowblock"
        )

        block_header = data.get(
            "block_header",
            {},
        )

        raw_data = block_header.get(
            "raw_data",
            {},
        )

        return {
            "network": "TRON",
            "status": "LIVE",
            "block_number": raw_data.get(
                "number"
            ),
            "block_hash": data.get(
                "blockID"
            ),
            "source": TRON_API,
            "explorer": TRON_EXPLORER,
        }

    except Exception as exc:

        return {
            "network": "TRON",
            "status": "UNAVAILABLE",
            "source": TRON_API,
            "error": str(exc),
        }


# ============================================================
# LATEST BLOCK
# ============================================================

@router.get("/latest-block")
async def latest_block():

    try:

        data = await api_get(
            "/wallet/getnowblock"
        )

        header = data.get(
            "block_header",
            {},
        )

        raw_data = header.get(
            "raw_data",
            {},
        )

        return {
            "network": "TRON",
            "status": "LIVE",
            "block_number": raw_data.get(
                "number"
            ),
            "block_hash": data.get(
                "blockID"
            ),
            "timestamp": raw_data.get(
                "timestamp"
            ),
            "parent_hash": raw_data.get(
                "parentHash"
            ),
            "transaction_count": len(
                data.get(
                    "transactions",
                    [],
                )
            ),
            "source": TRON_API,
            "explorer": TRON_EXPLORER,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail={
                "network": "TRON",
                "status": "UNAVAILABLE",
                "error": str(exc),
            },
        )


# ============================================================
# ACCOUNT / WALLET
# ============================================================

@router.get("/account/{address}")
async def account(
    address: str,
):

    address = validate_tron_address(
        address
    )

    try:

        data = await api_get(
            "/v1/accounts/" + address
        )

        accounts = data.get(
            "data",
            [],
        )

        if not accounts:

            raise HTTPException(
                status_code=404,
                detail="TRON account not found",
            )

        account_data = accounts[0]

        balance_sun = int(
            account_data.get(
                "balance",
                0,
            )
        )

        return {
            "address": address,
            "network": "TRON",
            "status": "LIVE",
            "native_asset": "TRX",
            "balance_sun": balance_sun,
            "balance_trx": (
                balance_sun / 1_000_000
            ),
            "account": account_data,
            "source": TRON_API,
            "explorer": (
                f"{TRON_EXPLORER}"
                f"/#/address/{address}"
            ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "TRON account lookup failed: "
                f"{exc}"
            ),
        )


# ============================================================
# SINGLE TRANSACTION
# ============================================================

@router.get("/transaction/{txid}")
async def transaction(
    txid: str,
):

    if not txid:

        raise HTTPException(
            status_code=400,
            detail=(
                "TRON transaction ID is required"
            ),
        )

    try:

        data = await api_get(
            "/wallet/gettransactionbyid",
            params={
                "value": txid,
            },
        )

        if not data:

            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        return {
            "network": "TRON",
            "status": "LIVE",
            "transaction": data,
            "source": TRON_API,
            "explorer": (
                f"{TRON_EXPLORER}"
                f"/#/transaction/{txid}"
            ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "TRON transaction lookup failed: "
                f"{exc}"
            ),
        )


# ============================================================
# TRANSACTION HISTORY
# ============================================================

@router.get("/transactions/{address}")
async def transactions(
    address: str,
    limit: int = Query(
        20,
        ge=1,
        le=50,
    ),
    fingerprint: str | None = None,
):

    address = validate_tron_address(
        address
    )

    try:

        params: dict[str, Any] = {
            "limit": limit,
        }

        if fingerprint:

            params["fingerprint"] = fingerprint

        data = await api_get(
            f"/v1/accounts/{address}/transactions",
            params=params,
        )

        records = data.get(
            "data",
            [],
        )

        meta = data.get(
            "meta",
            {},
        )

        return {
            "network": "TRON",
            "status": "LIVE",
            "address": address,
            "limit": limit,
            "count": len(records),
            "transactions": records,
            "next_cursor": meta.get(
                "fingerprint"
            ),
            "source": TRON_API,
            "explorer": (
                f"{TRON_EXPLORER}"
                f"/#/address/{address}"
            ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "TRON transaction history "
                f"lookup failed: {exc}"
            ),
        )


# ============================================================
# TRC-20 TOKEN TRANSFERS
# ============================================================

@router.get("/trc20-transfers/{address}")
async def trc20_transfers(
    address: str,
    limit: int = Query(
        20,
        ge=1,
        le=50,
    ),
    fingerprint: str | None = None,
):

    address = validate_tron_address(
        address
    )

    try:

        params: dict[str, Any] = {
            "limit": limit,
        }

        if fingerprint:

            params["fingerprint"] = fingerprint

        data = await api_get(
            f"/v1/accounts/{address}"
            "/transactions/trc20",
            params=params,
        )

        records = data.get(
            "data",
            [],
        )

        meta = data.get(
            "meta",
            {},
        )

        return {
            "network": "TRON",
            "status": "LIVE",
            "address": address,
            "asset_type": "TRC-20",
            "limit": limit,
            "count": len(records),
            "transfers": records,
            "next_cursor": meta.get(
                "fingerprint"
            ),
            "source": TRON_API,
            "explorer": (
                f"{TRON_EXPLORER}"
                f"/#/address/{address}"
            ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "TRON TRC-20 transfer "
                f"lookup failed: {exc}"
            ),
        )


# ============================================================
# TRANSACTION ADDRESS EXTRACTION
# ============================================================

def extract_transaction_addresses(
    transaction_data: dict[str, Any],
) -> set[str]:

    found: set[str] = set()

    raw_data = transaction_data.get(
        "raw_data",
        {},
    )

    contracts = raw_data.get(
        "contract",
        [],
    )

    if not isinstance(
        contracts,
        list,
    ):

        return found

    for contract in contracts:

        if not isinstance(
            contract,
            dict,
        ):

            continue

        parameter = contract.get(
            "parameter",
            {},
        )

        if not isinstance(
            parameter,
            dict,
        ):

            continue

        value = parameter.get(
            "value",
            {},
        )

        if not isinstance(
            value,
            dict,
        ):

            continue

        # Common TRON transaction fields.
        address_keys = (
            "owner_address",
            "to_address",
            "from_address",
            "receiver_address",
            "contract_address",
            "origin_address",
            "caller_address",
        )

        for key in address_keys:

            candidate = value.get(
                key
            )

            normalized = (
                normalize_tron_address(
                    candidate
                )
            )

            if normalized:

                found.add(normalized)

        # Some TRON contract payloads can contain
        # nested dictionaries.
        for nested_value in value.values():

            if isinstance(
                nested_value,
                dict,
            ):

                for nested_key in address_keys:

                    candidate = nested_value.get(
                        nested_key
                    )

                    normalized = (
                        normalize_tron_address(
                            candidate
                        )
                    )

                    if normalized:

                        found.add(normalized)

    return found


def extract_transaction_counterparties(
    transaction_data: dict[str, Any],
    wallet: str,
) -> list[str]:

    found = (
        extract_transaction_addresses(
            transaction_data
        )
    )

    found.discard(wallet)

    return sorted(found)


# ============================================================
# WALLET TRANSACTION DATA
# ============================================================

async def get_wallet_transactions(
    address: str,
    limit: int = MAX_TRANSACTIONS_PER_HOP,
) -> list[dict[str, Any]]:

    data = await api_get(
        f"/v1/accounts/{address}/transactions",
        params={
            "limit": limit,
        },
    )

    return data.get(
        "data",
        [],
    )


async def get_wallet_trc20_transfers(
    address: str,
    limit: int = MAX_TRC20_PER_HOP,
) -> list[dict[str, Any]]:

    data = await api_get(
        f"/v1/accounts/{address}"
        "/transactions/trc20",
        params={
            "limit": limit,
        },
    )

    return data.get(
        "data",
        [],
    )


# ============================================================
# FUND FLOW
# ============================================================

@router.get("/fundflow/{address}")
async def fundflow(
    address: str,
    hops: int = Query(
        1,
        ge=1,
        le=MAX_HOPS,
    ),
):

    address = validate_tron_address(
        address
    )

    current_level: list[str] = [
        address
    ]

    visited: set[str] = {
        address
    }

    nodes: list[dict[str, Any]] = [
        {
            "id": address,
            "address": address,
            "network": "TRON",
            "hop": 0,
            "type": "wallet",
        }
    ]

    edges: list[dict[str, Any]] = []

    all_transactions: list[
        dict[str, Any]
    ] = []

    all_trc20: list[
        dict[str, Any]
    ] = []

    traced_hops = 0

    try:

        # ====================================================
        # HOP LOOP
        # ====================================================

        for hop_number in range(
            1,
            hops + 1,
        ):

            if not current_level:

                break

            next_level: list[str] = []

            hop_transaction_count = 0
            hop_trc20_count = 0

            # =================================================
            # PROCESS WALLETS AT CURRENT HOP
            # =================================================

            for wallet in current_level:

                # Stop expanding more wallets
                # if the next level is already full.
                if (
                    len(next_level)
                    >= MAX_WALLETS_PER_HOP
                ):

                    break

                # =============================================
                # NATIVE TRON TRANSACTIONS
                # =============================================

                try:

                    transactions_data = (
                        await get_wallet_transactions(
                            wallet,
                            MAX_TRANSACTIONS_PER_HOP,
                        )
                    )

                except Exception:

                    transactions_data = []

                for tx in transactions_data:

                    if (
                        hop_transaction_count
                        >= MAX_TRANSACTIONS_PER_HOP
                    ):

                        break

                    if (
                        len(all_transactions)
                        >= MAX_TRANSACTIONS
                    ):

                        break

                    txid = tx.get(
                        "txID"
                    )

                    all_transactions.append(
                        {
                            "wallet": wallet,
                            "txID": txid,
                            "hop": hop_number,
                            "transaction": tx,
                        }
                    )

                    hop_transaction_count += 1

                    if not txid:

                        continue

                    # Get complete transaction.
                    try:

                        full_tx = await api_get(
                            "/wallet/gettransactionbyid",
                            params={
                                "value": txid,
                            },
                        )

                    except Exception:

                        continue

                    counterparties = (
                        extract_transaction_counterparties(
                            full_tx,
                            wallet,
                        )
                    )

                    for counterparty in counterparties:

                        # Do not create self edges.
                        if (
                            counterparty
                            == wallet
                        ):

                            continue

                        edges.append(
                            {
                                "from": wallet,
                                "to": counterparty,
                                "hop": hop_number,
                                "type": "TRX/transaction",
                                "txid": txid,
                            }
                        )

                        # Add a new wallet for next hop.
                        if (
                            counterparty
                            not in visited
                        ):

                            visited.add(
                                counterparty
                            )

                            nodes.append(
                                {
                                    "id": counterparty,
                                    "address": counterparty,
                                    "network": "TRON",
                                    "hop": hop_number,
                                    "type": "wallet",
                                }
                            )

                            if (
                                len(next_level)
                                < MAX_WALLETS_PER_HOP
                            ):

                                next_level.append(
                                    counterparty
                                )

                # =============================================
                # TRC-20 TRANSFERS
                # =============================================

                try:

                    token_transfers = (
                        await get_wallet_trc20_transfers(
                            wallet,
                            MAX_TRC20_PER_HOP,
                        )
                    )

                except Exception:

                    token_transfers = []

                for transfer in token_transfers:

                    if (
                        hop_trc20_count
                        >= MAX_TRC20_PER_HOP
                    ):

                        break

                    if (
                        len(all_trc20)
                        >= MAX_TRC20_TRANSFERS
                    ):

                        break

                    all_trc20.append(
                        {
                            "wallet": wallet,
                            "hop": hop_number,
                            "transfer": transfer,
                        }
                    )

                    hop_trc20_count += 1

                    from_address = normalize_tron_address(
                        transfer.get(
                            "from"
                        )
                    )

                    to_address = normalize_tron_address(
                        transfer.get(
                            "to"
                        )
                    )

                    if not from_address:

                        continue

                    if not to_address:

                        continue

                    if (
                        from_address
                        == to_address
                    ):

                        continue

                    edges.append(
                        {
                            "from": from_address,
                            "to": to_address,
                            "hop": hop_number,
                            "type": "TRC-20",
                            "token": transfer.get(
                                "token_info"
                            ),
                            "transaction_id": (
                                transfer.get(
                                    "transaction_id"
                                )
                            ),
                        }
                    )

                    # Determine the opposite wallet
                    # relative to the wallet currently
                    # being investigated.
                    if (
                        from_address
                        == wallet
                    ):

                        candidate = (
                            to_address
                        )

                    elif (
                        to_address
                        == wallet
                    ):

                        candidate = (
                            from_address
                        )

                    else:

                        # The indexed transfer can be related
                        # to the account without being the exact
                        # sender/receiver in unusual cases.
                        candidate = None

                    if (
                        candidate
                        and candidate != wallet
                        and candidate not in visited
                    ):

                        visited.add(
                            candidate
                        )

                        nodes.append(
                            {
                                "id": candidate,
                                "address": candidate,
                                "network": "TRON",
                                "hop": hop_number,
                                "type": "wallet",
                            }
                        )

                        if (
                            len(next_level)
                            < MAX_WALLETS_PER_HOP
                        ):

                            next_level.append(
                                candidate
                            )

            # =================================================
            # HOP COMPLETED
            # =================================================

            if next_level:

                traced_hops = hop_number

            current_level = next_level

            # If no new wallets were discovered,
            # there is nowhere to expand.
            if not current_level:

                break

        # ====================================================
        # RESPONSE
        # ====================================================

        return {
            "network": "TRON",
            "status": "LIVE",
            "root_wallet": address,
            "hops_requested": hops,
            "hops_traced": traced_hops,
            "wallets": len(nodes),
            "edges": len(edges),
            "transactions": len(
                all_transactions
            ),
            "trc20_transfers": len(
                all_trc20
            ),
            "nodes": nodes,
            "edges_data": edges,
            "transaction_data": all_transactions,
            "trc20_data": all_trc20,
            "source": TRON_API,
            "explorer": (
                f"{TRON_EXPLORER}"
                f"/#/address/{address}"
            ),
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail={
                "network": "TRON",
                "status": "ERROR",
                "error": str(exc),
            },
        )