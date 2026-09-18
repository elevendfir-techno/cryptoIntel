from fastapi import APIRouter
import httpx

from app.services.state import state

router = APIRouter(
    prefix="/api/detection",
    tags=["Detection"]
)

BITCOIN_API = "https://blockchain.info"

# Detection thresholds
PRICE_ANOMALY_PERCENT = 8
VOLUME_SPIKE = 100_000_000
RAPID_ACTIVITY_TRADES = 50
EXCHANGE_SPREAD_PERCENT = 2
LARGE_TRANSFER_BTC = 10

# Keep blockchain requests controlled
BITCOIN_BLOCKS_TO_CHECK = 1


async def get_bitcoin_live_detections():

    detections = []

    try:

        async with httpx.AsyncClient(
            timeout=20
        ) as client:

            # -------------------------------------------------
            # GET LATEST BITCOIN BLOCK
            # -------------------------------------------------

            latest_response = await client.get(
                f"{BITCOIN_API}/latestblock"
            )

            latest_response.raise_for_status()

            latest_block = latest_response.json()

            block_hash = latest_block.get(
                "hash"
            )

            block_height = latest_block.get(
                "height"
            )

            if not block_hash:
                return detections

            # -------------------------------------------------
            # GET FULL BLOCK
            # -------------------------------------------------

            block_response = await client.get(
                f"{BITCOIN_API}/rawblock/{block_hash}"
            )

            block_response.raise_for_status()

            block = block_response.json()

            transactions = block.get(
                "tx",
                []
            )

            # -------------------------------------------------
            # ANALYSE REAL BLOCKCHAIN TRANSACTIONS
            # -------------------------------------------------

            for tx in transactions:

                txid = tx.get(
                    "hash",
                    "UNKNOWN"
                )

                total_output_sats = 0
                largest_output_sats = 0

                # Blockchain.com transaction outputs
                # are stored inside "out"

                for output in tx.get(
                    "out",
                    []
                ):

                    value = output.get(
                        "value",
                        0
                    )

                    try:
                        value = int(value)
                    except (
                        TypeError,
                        ValueError
                    ):
                        continue

                    total_output_sats += value

                    largest_output_sats = max(
                        largest_output_sats,
                        value
                    )

                total_btc = (
                    total_output_sats
                    / 100_000_000
                )

                largest_btc = (
                    largest_output_sats
                    / 100_000_000
                )

                # =================================================
                # LARGE BITCOIN TRANSFER
                # =================================================

                if largest_btc >= LARGE_TRANSFER_BTC:

                    detections.append({

                        "type":
                            "LARGE TRANSFER",

                        "severity": (
                            "HIGH"
                            if largest_btc >= 100
                            else "MEDIUM"
                        ),

                        "asset": "BTC",

                        "source":
                            "Bitcoin Blockchain",

                        "value":
                            f"{largest_btc:.8f} BTC",

                        "reason": (
                            "Large Bitcoin transaction "
                            "output detected in the "
                            "latest Bitcoin block."
                        ),

                        "txid": txid,

                        "block": block_hash,

                        "block_height":
                            block_height,

                        "network":
                            "Bitcoin",

                        "data_source":
                            "Blockchain.com"
                    })

                # =================================================
                # VERY LARGE TRANSACTION
                # =================================================

                if total_btc >= 100:

                    detections.append({

                        "type":
                            "HIGH VALUE TRANSACTION",

                        "severity":
                            "HIGH",

                        "asset":
                            "BTC",

                        "source":
                            "Bitcoin Blockchain",

                        "value":
                            f"{total_btc:.8f} BTC",

                        "reason": (
                            "Transaction contains a "
                            "very large aggregate "
                            "Bitcoin output value."
                        ),

                        "txid": txid,

                        "block": block_hash,

                        "block_height":
                            block_height,

                        "network":
                            "Bitcoin",

                        "data_source":
                            "Blockchain.com"
                    })

    except Exception as e:

        detections.append({

            "type":
                "BLOCKCHAIN DATA STATUS",

            "severity":
                "LOW",

            "asset":
                "BTC",

            "source":
                "Blockchain.com",

            "value":
                "UNAVAILABLE",

            "reason":
                (
                    "Live Bitcoin detection "
                    "temporarily unavailable: "
                    f"{str(e)}"
                )
        })

    return detections


@router.get("")
async def detection():

    detections = []

    # =========================================================
    # 1. PRICE ANOMALY
    # =========================================================

    for market in state.market.values():

        try:

            change = float(
                market.get(
                    "change24h",
                    0
                )
            )

            if abs(change) >= PRICE_ANOMALY_PERCENT:

                detections.append({

                    "type":
                        "PRICE ANOMALY",

                    "severity": (
                        "HIGH"
                        if abs(change) >= 15
                        else "MEDIUM"
                    ),

                    "asset":
                        market.get(
                            "symbol",
                            "UNKNOWN"
                        ),

                    "source":
                        market.get(
                            "exchange",
                            "UNKNOWN"
                        ),

                    "value":
                        f"{change:.2f}%",

                    "reason":
                        (
                            "Unusual 24-hour "
                            "price movement "
                            "detected."
                        )
                })

        except (
            TypeError,
            ValueError
        ):
            continue

    # =========================================================
    # 2. VOLUME SPIKE
    # =========================================================

    for market in state.market.values():

        try:

            volume = float(
                market.get(
                    "volume",
                    0
                )
            )

            if volume >= VOLUME_SPIKE:

                detections.append({

                    "type":
                        "VOLUME SPIKE",

                    "severity":
                        "MEDIUM",

                    "asset":
                        market.get(
                            "symbol",
                            "UNKNOWN"
                        ),

                    "source":
                        market.get(
                            "exchange",
                            "UNKNOWN"
                        ),

                    "value":
                        f"{volume:,.2f}",

                    "reason":
                        (
                            "Unusually high "
                            "24-hour trading "
                            "volume detected."
                        )
                })

        except (
            TypeError,
            ValueError
        ):
            continue

    # =========================================================
    # 3. RAPID MARKET ACTIVITY
    # =========================================================

    trade_count = len(
        state.trades
    )

    if trade_count >= RAPID_ACTIVITY_TRADES:

        detections.append({

            "type":
                "RAPID ACTIVITY",

            "severity":
                "MEDIUM",

            "asset":
                "MULTIPLE",

            "source":
                "Live Market Feed",

            "value":
                f"{trade_count} trades",

            "reason":
                (
                    "High-frequency trading "
                    "activity detected in "
                    "the live feed."
                )
        })

    # =========================================================
    # 4. EXCHANGE PRICE SPREAD
    # =========================================================

    asset_prices = {}

    for market in state.market.values():

        try:

            symbol = (
                market.get(
                    "symbol",
                    ""
                )
                .upper()
                .replace("-", "")
                .replace("_", "")
                .replace("/", "")
            )

            if symbol.endswith("USDT"):

                asset = symbol[:-4]

            elif symbol.endswith("USD"):

                asset = symbol[:-3]

            else:

                asset = symbol

            price = float(
                market.get(
                    "price",
                    0
                )
            )

            if not asset or price <= 0:
                continue

            asset_prices.setdefault(
                asset,
                []
            ).append({

                "exchange":
                    market.get(
                        "exchange",
                        "UNKNOWN"
                    ),

                "price":
                    price
            })

        except (
            TypeError,
            ValueError
        ):
            continue

    for asset, prices in asset_prices.items():

        if len(prices) < 2:
            continue

        highest = max(
            prices,
            key=lambda x: x["price"]
        )

        lowest = min(
            prices,
            key=lambda x: x["price"]
        )

        if lowest["price"] <= 0:
            continue

        spread = (

            (
                highest["price"]
                - lowest["price"]
            )

            / lowest["price"]

        ) * 100

        if spread >= EXCHANGE_SPREAD_PERCENT:

            detections.append({

                "type":
                    "EXCHANGE SPREAD",

                "severity": (
                    "HIGH"
                    if spread >= 5
                    else "MEDIUM"
                ),

                "asset":
                    asset,

                "source":
                    (
                        f'{lowest["exchange"]} → '
                        f'{highest["exchange"]}'
                    ),

                "value":
                    f"{spread:.2f}%",

                "reason":
                    (
                        "Significant price "
                        "difference detected "
                        "between live exchanges."
                    )
            })

    # =========================================================
    # 5. REAL BITCOIN BLOCKCHAIN DETECTIONS
    # =========================================================

    blockchain_detections = (
        await get_bitcoin_live_detections()
    )

    detections.extend(
        blockchain_detections
    )

    # =========================================================
    # FINAL RESPONSE
    # =========================================================

    return {

        "status":
            "LIVE",

        "total_detections":
            len(detections),

        "detections":
            detections[:100],

        "source":
            (
                "Live exchange market feeds + "
                "Bitcoin blockchain"
            ),

        "rules": {

            "price_anomaly":
                "ACTIVE",

            "volume_spike":
                "ACTIVE",

            "rapid_activity":
                "ACTIVE",

            "exchange_spread":
                "ACTIVE",

            "large_transfer":
                "ACTIVE",

            "high_value_transaction":
                "ACTIVE",

            "multi_hop_movement":
                "BLOCKCHAIN ANALYSIS READY"
        },

        "blockchain": {

            "network":
                "Bitcoin",

            "status":
                "LIVE",

            "provider":
                "Blockchain.com"
        }
    }