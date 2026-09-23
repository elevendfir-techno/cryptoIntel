from __future__ import annotations

from typing import Any

import asyncio
import httpx

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/multichain",
    tags=["multichain"],
)


# ============================================================
# EVM NETWORK CONFIGURATION
# ============================================================

CHAINS: dict[str, dict[str, Any]] = {
    "bnb": {
        "name": "BNB Smart Chain",
        "symbol": "BNB",
        "chain_id": 56,
        "rpc": "https://bsc-dataseed.bnbchain.org",
        "explorer": "https://bscscan.com",
    },
    "arbitrum": {
        "name": "Arbitrum One",
        "symbol": "ETH",
        "chain_id": 42161,
        "rpc": "https://arb1.arbitrum.io/rpc",
        "explorer": "https://arbiscan.io",
    },
    "optimism": {
        "name": "Optimism",
        "symbol": "ETH",
        "chain_id": 10,
        "rpc": "https://mainnet.optimism.io",
        "explorer": "https://optimistic.etherscan.io",
    },
    "base": {
        "name": "Base",
        "symbol": "ETH",
        "chain_id": 8453,
        "rpc": "https://mainnet.base.org",
        "explorer": "https://basescan.org",
    },
    "avalanche": {
        "name": "Avalanche C-Chain",
        "symbol": "AVAX",
        "chain_id": 43114,
        "rpc": "https://api.avax.network/ext/bc/C/rpc",
        "explorer": "https://snowtrace.io",
    },
}


# ============================================================
# EXISTING NETWORK FUND-FLOW ROUTES
# ============================================================

NETWORK_HISTORY_ROUTES = {
    "bitcoin": "/api/fundflow/{address}",
    "ethereum": "/api/fundflow/{address}",
    "solana": "/api/solana/fundflow/{address}",
    "tron": "/api/tron/fundflow/{address}",
    "xrpl": "/api/xrpl/fundflow/{address}",
    "cardano": "/api/cardano/fundflow/{address}",
}


# ============================================================
# UNIFIED INVESTIGATION MODELS
# ============================================================

class InvestigationTarget(BaseModel):
    network: str = Field(
        ...,
        description=(
            "Network key such as bitcoin, ethereum, "
            "solana, tron, xrpl, cardano, bnb, "
            "arbitrum, optimism, base or avalanche"
        ),
    )

    address: str = Field(
        ...,
        description="Wallet or contract address",
    )


class MultichainInvestigationRequest(BaseModel):
    targets: list[InvestigationTarget] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Explicit network/address targets",
    )


# ============================================================
# RPC HELPER
# ============================================================

async def rpc_call(
    rpc_url: str,
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
        timeout=20
    ) as client:

        response = await client.post(
            rpc_url,
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
# HEX → INTEGER
# ============================================================

def hex_to_int(
    value: str | None,
) -> int:

    if not value:
        return 0

    try:
        return int(
            value,
            16,
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


# ============================================================
# ADDRESS VALIDATION
# ============================================================

def validate_evm_address(
    address: str,
) -> bool:

    if not isinstance(
        address,
        str,
    ):
        return False

    if not address.startswith(
        "0x"
    ):
        return False

    if len(address) != 42:
        return False

    try:
        int(
            address[2:],
            16,
        )
        return True

    except ValueError:
        return False


# ============================================================
# CHAIN STATUS
# ============================================================

async def get_chain_status(
    key: str,
    config: dict[str, Any],
) -> dict[str, Any]:

    try:

        chain_id_hex = await rpc_call(
            config["rpc"],
            "eth_chainId",
        )

        block_hex = await rpc_call(
            config["rpc"],
            "eth_blockNumber",
        )

        actual_chain_id = hex_to_int(
            chain_id_hex
        )

        latest_block = hex_to_int(
            block_hex
        )

        if (
            actual_chain_id
            != config["chain_id"]
        ):

            return {
                "network": config["name"],
                "network_key": key,
                "symbol": config["symbol"],
                "chain_id": config["chain_id"],
                "status": "DEGRADED",
                "reason": (
                    "RPC returned unexpected "
                    "chain ID"
                ),
                "rpc_chain_id": actual_chain_id,
                "latest_block": latest_block,
                "source": config["rpc"],
            }

        return {
            "network": config["name"],
            "network_key": key,
            "symbol": config["symbol"],
            "chain_id": config["chain_id"],
            "status": "LIVE",
            "latest_block": latest_block,
            "source": config["rpc"],
            "explorer": config["explorer"],
        }

    except Exception as exc:

        return {
            "network": config["name"],
            "network_key": key,
            "symbol": config["symbol"],
            "chain_id": config["chain_id"],
            "status": "UNAVAILABLE",
            "latest_block": None,
            "source": config["rpc"],
            "error": str(exc),
        }


# ============================================================
# NETWORK LIST
# ============================================================

@router.get("/networks")
async def networks():

    results = []

    for key, config in CHAINS.items():

        results.append(
            await get_chain_status(
                key,
                config,
            )
        )

    live_count = sum(
        1
        for result in results
        if result.get("status") == "LIVE"
    )

    return {
        "status": "LIVE",
        "networks": results,
        "total": len(results),
        "live": live_count,
        "unavailable": (
            len(results)
            - live_count
        ),
    }


# ============================================================
# LATEST BLOCK
# ============================================================

@router.get("/{network}/latest-block")
async def latest_block(
    network: str,
):

    key = network.lower().strip()

    if key not in CHAINS:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unsupported network: "
                f"{network}"
            ),
        )

    config = CHAINS[key]

    try:

        block_number_hex = await rpc_call(
            config["rpc"],
            "eth_blockNumber",
        )

        block_number = hex_to_int(
            block_number_hex
        )

        block = await rpc_call(
            config["rpc"],
            "eth_getBlockByNumber",
            [
                hex(block_number),
                True,
            ],
        )

        if not block:

            raise RuntimeError(
                "Latest block was not returned "
                "by RPC"
            )

        return {
            "network": config["name"],
            "status": "LIVE",
            "block_number": block_number,
            "block_hash": block.get("hash"),
            "parent_hash": block.get("parentHash"),
            "timestamp": hex_to_int(
                block.get("timestamp")
            ),
            "transaction_count": len(
                block.get(
                    "transactions",
                    [],
                )
            ),
            "miner": block.get("miner"),
            "gas_used": hex_to_int(
                block.get("gasUsed")
            ),
            "gas_limit": hex_to_int(
                block.get("gasLimit")
            ),
            "source": config["rpc"],
            "explorer": config["explorer"],
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail={
                "network": config["name"],
                "status": "UNAVAILABLE",
                "error": str(exc),
            },
        )


# ============================================================
# BLOCK DETAILS
# ============================================================

@router.get("/{network}/block/{block_number}")
async def block(
    network: str,
    block_number: int,
):

    key = network.lower().strip()

    if key not in CHAINS:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unsupported network: "
                f"{network}"
            ),
        )

    if block_number < 0:

        raise HTTPException(
            status_code=400,
            detail="Block number must be >= 0",
        )

    config = CHAINS[key]

    try:

        block_data = await rpc_call(
            config["rpc"],
            "eth_getBlockByNumber",
            [
                hex(block_number),
                True,
            ],
        )

        if not block_data:

            raise HTTPException(
                status_code=404,
                detail="Block not found",
            )

        return {
            "network": config["name"],
            "status": "LIVE",
            "block_number": block_number,
            "block": block_data,
            "source": config["rpc"],
            "explorer": config["explorer"],
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Block lookup failed: "
                f"{exc}"
            ),
        )


# ============================================================
# TRANSACTION
# ============================================================

@router.get("/{network}/transaction/{tx_hash}")
async def transaction(
    network: str,
    tx_hash: str,
):

    key = network.lower().strip()

    if key not in CHAINS:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unsupported network: "
                f"{network}"
            ),
        )

    if not tx_hash.startswith("0x"):

        raise HTTPException(
            status_code=400,
            detail=(
                "Transaction hash "
                "must start with 0x"
            ),
        )

    config = CHAINS[key]

    try:

        tx = await rpc_call(
            config["rpc"],
            "eth_getTransactionByHash",
            [tx_hash],
        )

        if not tx:

            raise HTTPException(
                status_code=404,
                detail="Transaction not found",
            )

        receipt = await rpc_call(
            config["rpc"],
            "eth_getTransactionReceipt",
            [tx_hash],
        )

        return {
            "network": config["name"],
            "status": "LIVE",
            "transaction": tx,
            "receipt": receipt,
            "source": config["rpc"],
            "explorer": (
                f"{config['explorer']}"
                f"/tx/{tx_hash}"
            ),
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Transaction lookup "
                f"failed: {exc}"
            ),
        )


# ============================================================
# ADDRESS
# ============================================================

@router.get("/{network}/address/{address}")
async def address(
    network: str,
    address: str,
):

    key = network.lower().strip()

    if key not in CHAINS:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unsupported network: "
                f"{network}"
            ),
        )

    if not validate_evm_address(address):

        raise HTTPException(
            status_code=400,
            detail="Invalid EVM address",
        )

    config = CHAINS[key]

    try:

        balance_hex = await rpc_call(
            config["rpc"],
            "eth_getBalance",
            [
                address,
                "latest",
            ],
        )

        nonce_hex = await rpc_call(
            config["rpc"],
            "eth_getTransactionCount",
            [
                address,
                "latest",
            ],
        )

        code = await rpc_call(
            config["rpc"],
            "eth_getCode",
            [
                address,
                "latest",
            ],
        )

        balance_wei = hex_to_int(
            balance_hex
        )

        return {
            "address": address,
            "network": config["name"],
            "network_key": key,
            "status": "LIVE",
            "native_asset": config["symbol"],
            "balance_raw": balance_wei,
            "balance_wei": balance_wei,
            "nonce": hex_to_int(nonce_hex),
            "address_type": (
                "SMART_CONTRACT"
                if code and code != "0x"
                else "EOA"
            ),
            "source": config["rpc"],
            "explorer": (
                f"{config['explorer']}"
                f"/address/{address}"
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Address lookup failed: "
                f"{exc}"
            ),
        )


# ============================================================
# EXISTING SINGLE-NETWORK INVESTIGATION
# ============================================================

@router.get("/investigate/{network}/{address}")
async def investigate_address(
    network: str,
    address: str,
):

    key = network.lower().strip()

    if key not in CHAINS:

        raise HTTPException(
            status_code=404,
            detail=(
                "Unsupported multichain "
                f"network: {network}"
            ),
        )

    if not validate_evm_address(address):

        raise HTTPException(
            status_code=400,
            detail="Invalid EVM address",
        )

    config = CHAINS[key]

    try:

        balance_hex = await rpc_call(
            config["rpc"],
            "eth_getBalance",
            [
                address,
                "latest",
            ],
        )

        nonce_hex = await rpc_call(
            config["rpc"],
            "eth_getTransactionCount",
            [
                address,
                "latest",
            ],
        )

        code = await rpc_call(
            config["rpc"],
            "eth_getCode",
            [
                address,
                "latest",
            ],
        )

        block_hex = await rpc_call(
            config["rpc"],
            "eth_blockNumber",
        )

        balance_wei = hex_to_int(
            balance_hex
        )

        nonce = hex_to_int(
            nonce_hex
        )

        latest_block = hex_to_int(
            block_hex
        )

        address_type = (
            "SMART_CONTRACT"
            if code and code != "0x"
            else "EOA"
        )

        return {
            "status": "LIVE",
            "investigation": {
                "root_address": address,
                "network": config["name"],
                "network_key": key,
                "chain_id": config["chain_id"],
                "native_asset": config["symbol"],
                "address_type": address_type,
                "balance": {
                    "raw": balance_wei,
                    "wei": balance_wei,
                },
                "nonce": nonce,
                "latest_block": latest_block,
                "activity": {
                    "available": True,
                    "transaction_history": (
                        "Use the network-specific "
                        "transaction endpoint"
                    ),
                },
                "fund_flow": {
                    "available": True,
                    "status": "READY_FOR_CORRELATION",
                },
                "indicators": [],
                "cross_chain": {
                    "status": "PENDING",
                    "note": (
                        "Cross-chain relationships "
                        "require evidence from "
                        "multiple networks. "
                        "Address similarity alone "
                        "is not treated as a "
                        "relationship."
                    ),
                },
                "source": config["rpc"],
                "explorer": (
                    f"{config['explorer']}"
                    f"/address/{address}"
                ),
            },
        }

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail={
                "network": config["name"],
                "status": "UNAVAILABLE",
                "error": str(exc),
            },
        )


# ============================================================
# TARGET INVESTIGATION HELPER
# ============================================================

async def investigate_evm_target(
    target: InvestigationTarget,
) -> dict[str, Any]:

    key = target.network.lower().strip()

    address_value = target.address.strip()

    if key not in CHAINS:

        return {
            "network": key,
            "network_key": key,
            "address": address_value,
            "status": "UNSUPPORTED",
            "error": (
                "Network is not configured "
                "in the EVM multichain layer"
            ),
        }

    if not validate_evm_address(address_value):

        return {
            "network": key,
            "network_key": key,
            "address": address_value,
            "status": "INVALID",
            "error": "Invalid EVM address",
        }

    config = CHAINS[key]

    try:

        (
            balance_hex,
            nonce_hex,
            code,
            block_hex,
        ) = await asyncio_gather_rpc(
            config["rpc"],
            [
                (
                    "eth_getBalance",
                    [
                        address_value,
                        "latest",
                    ],
                ),
                (
                    "eth_getTransactionCount",
                    [
                        address_value,
                        "latest",
                    ],
                ),
                (
                    "eth_getCode",
                    [
                        address_value,
                        "latest",
                    ],
                ),
                (
                    "eth_blockNumber",
                    [],
                ),
            ],
        )

        balance_wei = hex_to_int(
            balance_hex
        )

        nonce = hex_to_int(
            nonce_hex
        )

        latest_block = hex_to_int(
            block_hex
        )

        address_type = (
            "SMART_CONTRACT"
            if code and code != "0x"
            else "EOA"
        )

        return {
            "network": config["name"],
            "network_key": key,
            "address": address_value,
            "status": "LIVE",
            "chain_id": config["chain_id"],
            "native_asset": config["symbol"],
            "address_type": address_type,
            "balance": {
                "raw": balance_wei,
                "wei": balance_wei,
            },
            "nonce": nonce,
            "latest_block": latest_block,
            "activity": {
                "available": True,
                "transaction_history": (
                    "Available through "
                    "network-specific "
                    "transaction endpoints"
                ),
            },
            "fund_flow": {
                "available": True,
                "status": "READY_FOR_CORRELATION",
            },
            "indicators": [],
            "source": config["rpc"],
            "explorer": (
                f"{config['explorer']}"
                f"/address/{address_value}"
            ),
        }

    except Exception as exc:

        return {
            "network": config["name"],
            "network_key": key,
            "address": address_value,
            "status": "UNAVAILABLE",
            "error": str(exc),
            "source": config["rpc"],
        }


# ============================================================
# PARALLEL RPC HELPER
# ============================================================

async def asyncio_gather_rpc(
    rpc_url: str,
    calls: list[
        tuple[str, list[Any]]
    ],
) -> list[Any]:

    async def one_call(
        method: str,
        params: list[Any],
    ):

        return await rpc_call(
            rpc_url,
            method,
            params,
        )

    tasks = [
        one_call(
            method,
            params,
        )
        for method, params in calls
    ]

    return await asyncio.gather(
        *tasks
    )


# ============================================================
# EXISTING NETWORK FUND-FLOW HELPER
# ============================================================

async def investigate_network_history(
    network: str,
    address: str,
    base_url: str,
) -> dict[str, Any]:

    key = network.lower().strip()

    if key not in NETWORK_HISTORY_ROUTES:

        return {
            "network": key,
            "network_key": key,
            "address": address,
            "status": "UNSUPPORTED",
            "error": (
                "Network history route "
                "is not configured"
            ),
        }

    route = NETWORK_HISTORY_ROUTES[key].format(
        address=address
    )

    params: dict[str, Any] = {}

    # Bitcoin and Ethereum use the shared
    # /api/fundflow/{address} endpoint.
    if key in {
        "bitcoin",
        "ethereum",
    }:
        params["network"] = key
        params["hops"] = 2

    # Remove a trailing slash so that:
    # base_url + route
    # becomes a valid internal API URL.
    target_url = (
        base_url.rstrip("/")
        + route
    )

    try:

        async with httpx.AsyncClient(
            timeout=180
        ) as client:

            response = await client.get(
                target_url,
                params=params,
            )

        if response.status_code >= 400:

            return {
                "network": key,
                "network_key": key,
                "address": address,
                "status": "UNAVAILABLE",
                "error": (
                    f"Network endpoint returned "
                    f"HTTP {response.status_code}"
                ),
                "details": response.text,
            }

        data = response.json()

        source = data.get(
            "source",
            "Existing CryptoIntel network module",
        )

        result_status = data.get(
            "status",
            "LIVE",
        )

        return {
            "network": key,
            "network_key": key,
            "address": address,
            "status": result_status,
            "activity": {
                "available": True,
                "transaction_history": (
                    "Collected through the "
                    "existing network fund-flow module"
                ),
            },
            "fund_flow": {
                "available": True,
                "status": result_status,
            },
            "fund_flow_data": data,
            "source": source,
        }

    except Exception as exc:

        return {
            "network": key,
            "network_key": key,
            "address": address,
            "status": "UNAVAILABLE",
            "error": str(exc),
        }


# ============================================================
# UNIFIED MULTICHAIN INVESTIGATION
# ============================================================

@router.post("/investigate")
async def unified_investigation(
    request: Request,
    investigation: MultichainInvestigationRequest,
):

    if not investigation.targets:

        raise HTTPException(
            status_code=400,
            detail=(
                "At least one investigation "
                "target is required."
            ),
        )

    # --------------------------------------------------------
    # Build current API base URL
    # --------------------------------------------------------

    base_url = str(
        request.base_url
    )

    # --------------------------------------------------------
    # Investigate all targets
    # --------------------------------------------------------

    async def process_target(
        target: InvestigationTarget,
    ) -> dict[str, Any]:

        network_key = (
            target.network
            .lower()
            .strip()
        )

        address_value = (
            target.address.strip()
        )

        # Existing EVM multichain layer
        if network_key in CHAINS:

            return await investigate_evm_target(
                target
            )

        # Existing Bitcoin / Ethereum /
        # Solana / TRON / XRPL / Cardano
        # fund-flow modules
        if network_key in NETWORK_HISTORY_ROUTES:

            return await investigate_network_history(
                network_key,
                address_value,
                base_url,
            )

        return {
            "network": network_key,
            "network_key": network_key,
            "address": address_value,
            "status": "UNSUPPORTED",
            "error": (
                "Network is not supported "
                "by the unified investigation layer"
            ),
        }

    # Run requested targets concurrently.
    results = await asyncio.gather(
        *[
            process_target(target)
            for target in investigation.targets
        ]
    )

    results = list(results)

    # --------------------------------------------------------
    # Status groups
    # --------------------------------------------------------

    live_results = [
        result
        for result in results
        if result.get("status") == "LIVE"
    ]

    partial_results = [
        result
        for result in results
        if result.get("status") == "PARTIAL"
    ]

    unavailable_results = [
        result
        for result in results
        if result.get("status") == "UNAVAILABLE"
    ]

    invalid_results = [
        result
        for result in results
        if result.get("status")
        in {
            "INVALID",
            "UNSUPPORTED",
        }
    ]

    successful_results = [
        result
        for result in results
        if result.get("status")
        in {
            "LIVE",
            "PARTIAL",
        }
    ]

    # --------------------------------------------------------
    # Networks checked
    # --------------------------------------------------------

    networks_checked = list(
        dict.fromkeys(
            result.get("network_key")
            for result in results
            if result.get("network_key")
        )
    )

    # --------------------------------------------------------
    # Relationship logic
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # Address equality/similarity alone is NOT treated
    # as proof of ownership or entity relationship.
    #

    relationships: list[
        dict[str, Any]
    ] = []

    unique_addresses: dict[
        str,
        list[str],
    ] = {}

    for result in successful_results:

        address_value = result.get(
            "address"
        )

        network_key = result.get(
            "network_key"
        )

        if not address_value:
            continue

        # EVM addresses can be compared case-insensitively.
        # Other network address formats are kept as supplied.
        if network_key in CHAINS:
            normalized_address = (
                address_value.lower()
            )
        else:
            normalized_address = address_value

        unique_addresses.setdefault(
            normalized_address,
            [],
        ).append(
            network_key
        )

    for (
        normalized_address,
        networks_for_address,
    ) in unique_addresses.items():

        unique_networks = list(
            dict.fromkeys(
                networks_for_address
            )
        )

        if len(unique_networks) > 1:

            relationships.append(
                {
                    "type": (
                        "ADDRESS_REUSE_OBSERVED"
                    ),
                    "address": normalized_address,
                    "networks": unique_networks,
                    "evidence_level": (
                        "OBSERVATION_ONLY"
                    ),
                    "note": (
                        "The same address string "
                        "appears on multiple "
                        "networks. This alone "
                        "does not establish common "
                        "ownership or control."
                    ),
                }
            )

    # --------------------------------------------------------
    # Indicators
    # --------------------------------------------------------

    indicators: list[
        dict[str, Any]
    ] = []

    for result in successful_results:

        if result.get(
            "address_type"
        ) == "SMART_CONTRACT":

            indicators.append(
                {
                    "type": (
                        "SMART_CONTRACT_ADDRESS"
                    ),
                    "network": result.get(
                        "network_key"
                    ),
                    "address": result.get(
                        "address"
                    ),
                    "severity": "INFO",
                    "status": "OBSERVED",
                    "note": (
                        "The investigated EVM "
                        "address contains deployed "
                        "contract code."
                    ),
                }
            )

    # --------------------------------------------------------
    # Overall status
    # --------------------------------------------------------

    if (
        successful_results
        and not unavailable_results
        and not invalid_results
    ):

        overall_status = "LIVE"

    elif successful_results:

        overall_status = "PARTIAL"

    else:

        overall_status = "UNAVAILABLE"

    # --------------------------------------------------------
    # Unified activity
    # --------------------------------------------------------

    unified_activity_available = any(
        result.get("activity", {}).get(
            "available"
        )
        for result in successful_results
    )

    # --------------------------------------------------------
    # Source list
    # --------------------------------------------------------

    sources = list(
        dict.fromkeys(
            result.get("source")
            for result in results
            if result.get("source")
        )
    )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {
        "status": overall_status,

        "investigation": {
            "target_count": len(
                investigation.targets
            ),

            "successful_targets": len(
                successful_results
            ),

            "live_targets": len(
                live_results
            ),

            "partial_targets": len(
                partial_results
            ),

            "unavailable_targets": len(
                unavailable_results
            ),

            "invalid_or_unsupported_targets": len(
                invalid_results
            ),

            "networks_checked": (
                networks_checked
            ),

            "results": results,

            "unified_activity": {
                "available": (
                    unified_activity_available
                ),
                "status": (
                    "COLLECTED"
                    if unified_activity_available
                    else "NO_ACTIVITY_DATA"
                ),
                "note": (
                    "Activity is collected from "
                    "the existing network-specific "
                    "fund-flow modules and EVM "
                    "multichain RPC layer."
                ),
            },

            "relationships": relationships,

            "fund_flow": {
                "available": any(
                    result.get(
                        "fund_flow",
                        {},
                    ).get(
                        "available"
                    )
                    for result in successful_results
                ),
                "status": (
                    "COLLECTED"
                    if any(
                        result.get(
                            "fund_flow_data"
                        )
                        for result in successful_results
                    )
                    else "READY_FOR_CORRELATION"
                ),
                "note": (
                    "Fund-flow data is collected "
                    "through the existing network "
                    "specific modules."
                ),
            },

            "indicators": indicators,

            "risk": {
                "status": "NOT_EVALUATED",
                "note": (
                    "Detection and risk scoring "
                    "are handled by the Detection "
                    "Engine and Risk Analysis stages."
                ),
            },
        },

        "source": (
            "CryptoIntel unified multichain "
            "investigation layer"
        ),

        "sources": sources,
}