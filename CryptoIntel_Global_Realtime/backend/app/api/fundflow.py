from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter(prefix="/api/fundflow", tags=["fund-flow"])

BITCOIN_API = "https://blockstream.info/api"

MAX_HOPS = 3
MAX_WALLETS_PER_HOP = 20
MAX_TXS_PER_WALLET = 20


@router.get("/{address}")
async def fundflow(
    address: str,
    network: str = "bitcoin",
    hops: int = 2
):
    if network.lower() != "bitcoin":
        raise HTTPException(
            status_code=400,
            detail="Currently only Bitcoin fund flow is live."
        )

    # Keep hops between 1 and 3
    hops = max(1, min(hops, MAX_HOPS))

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            nodes = {}
            edges = []

            # Root wallet
            nodes[address] = {
                "id": address,
                "type": "wallet",
                "label": address[:12] + "...",
                "hop": 0
            }

            visited = {address}
            current_wallets = [address]

            total_transactions = 0

            # --------------------------------------------------
            # TRUE RECURSIVE FUND FLOW
            # --------------------------------------------------

            for current_hop in range(1, hops + 1):

                next_wallets = []

                for wallet_address in current_wallets:

                    # Get live transactions for this wallet
                    response = await client.get(
                        f"{BITCOIN_API}/address/{wallet_address}/txs"
                    )

                    if response.status_code == 404:
                        continue

                    response.raise_for_status()

                    transactions = response.json()

                    total_transactions += len(transactions)

                    # Limit transactions per wallet
                    for tx in transactions[:MAX_TXS_PER_WALLET]:

                        txid = tx.get("txid")

                        if not txid:
                            continue

                        # --------------------------------------
                        # INPUTS
                        # Other wallets → current wallet
                        # --------------------------------------

                        for vin in tx.get("vin", []):

                            prevout = vin.get("prevout") or {}

                            source_address = prevout.get(
                                "scriptpubkey_address"
                            )

                            if not source_address:
                                continue

                            if source_address == wallet_address:
                                continue

                            value_sats = prevout.get(
                                "value", 0
                            )

                            # Add source wallet
                            if source_address not in nodes:

                                nodes[source_address] = {
                                    "id": source_address,
                                    "type": "wallet",
                                    "label": (
                                        source_address[:12] + "..."
                                    ),
                                    "hop": current_hop
                                }

                            # Add edge
                            edges.append({
                                "source": source_address,
                                "target": wallet_address,
                                "txid": txid,
                                "value_sats": value_sats,
                                "type": "incoming",
                                "hop": current_hop
                            })

                            # Queue wallet for next hop
                            if (
                                source_address not in visited
                                and source_address not in next_wallets
                                and len(next_wallets)
                                < MAX_WALLETS_PER_HOP
                            ):
                                next_wallets.append(
                                    source_address
                                )

                        # --------------------------------------
                        # OUTPUTS
                        # Current wallet → other wallets
                        # --------------------------------------

                        for vout in tx.get("vout", []):

                            destination_address = vout.get(
                                "scriptpubkey_address"
                            )

                            if not destination_address:
                                continue

                            if destination_address == wallet_address:
                                continue

                            value_sats = vout.get(
                                "value", 0
                            )

                            # Add destination wallet
                            if destination_address not in nodes:

                                nodes[destination_address] = {
                                    "id": destination_address,
                                    "type": "wallet",
                                    "label": (
                                        destination_address[:12]
                                        + "..."
                                    ),
                                    "hop": current_hop
                                }

                            # Add edge
                            edges.append({
                                "source": wallet_address,
                                "target": destination_address,
                                "txid": txid,
                                "value_sats": value_sats,
                                "type": "outgoing",
                                "hop": current_hop
                            })

                            # Queue wallet for next hop
                            if (
                                destination_address not in visited
                                and destination_address
                                not in next_wallets
                                and len(next_wallets)
                                < MAX_WALLETS_PER_HOP
                            ):
                                next_wallets.append(
                                    destination_address
                                )

                # Mark discovered wallets as visited
                for wallet in next_wallets:
                    visited.add(wallet)

                # Continue to next hop
                current_wallets = next_wallets

                # Nothing more to investigate
                if not current_wallets:
                    break

            # --------------------------------------------------
            # REMOVE DUPLICATE EDGES
            # --------------------------------------------------

            unique_edges = {}

            for edge in edges:

                key = (
                    edge["source"],
                    edge["target"],
                    edge["txid"],
                    edge["type"],
                    edge.get("value_sats", 0)
                )

                unique_edges[key] = edge

            final_edges = list(unique_edges.values())

            return {
                "root": address,
                "network": "Bitcoin",
                "status": "LIVE",

                "hops_requested": hops,
                "hops_traced": hops,

                "nodes": list(nodes.values()),
                "edges": final_edges,

                "wallet_count": len(nodes),
                "edge_count": len(final_edges),

                "transactions_scanned": total_transactions,

                "limits": {
                    "max_hops": MAX_HOPS,
                    "max_wallets_per_hop":
                        MAX_WALLETS_PER_HOP,
                    "max_transactions_per_wallet":
                        MAX_TXS_PER_WALLET
                },

                "source": "Blockstream Esplora API"
            }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Fund flow lookup failed: {str(e)}"
        )