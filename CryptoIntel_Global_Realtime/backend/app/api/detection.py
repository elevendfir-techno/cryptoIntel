from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter

from app.services.state import state
from app.services.event_bus import event_bus
from app.services.risk_engine import analyze_detection
from app.services.alert_engine import process_risk_result


router = APIRouter(
    prefix="/api/detection",
    tags=["Detection"]
)


# ============================================================
# EXTERNAL DATA SOURCES
# ============================================================

BITCOIN_API = "https://blockchain.info"


# ============================================================
# MARKET DETECTION THRESHOLDS
# ============================================================

PRICE_ANOMALY_PERCENT = 8
VOLUME_SPIKE = 100_000_000
RAPID_ACTIVITY_TRADES = 50
EXCHANGE_SPREAD_PERCENT = 2


# ============================================================
# BITCOIN DETECTION THRESHOLDS
# ============================================================

LARGE_TRANSFER_BTC = 10
BITCOIN_HIGH_VALUE_BTC = 100


# ============================================================
# ETHEREUM REAL-TIME DETECTION THRESHOLDS
# ============================================================

LARGE_TRANSFER_ETH = 10
HIGH_VALUE_TRANSACTION_ETH = 100

RAPID_ETH_TX_COUNT = 10
RAPID_ETH_TX_WINDOW_SECONDS = 60


# ============================================================
# BITCOIN REQUEST CONTROL
# ============================================================

BITCOIN_BLOCKS_TO_CHECK = 1


# ============================================================
# REAL-TIME DETECTION STORAGE
# ============================================================

REALTIME_DETECTIONS = deque(
    maxlen=500
)

REALTIME_EVENTS_ANALYZED = 0
REALTIME_DETECTIONS_FOUND = 0

# Track recent Ethereum transactions per sender.
ETHEREUM_ADDRESS_ACTIVITY = {}

# Track currently active rapid-activity detection
# per Ethereum address.
ETHEREUM_RAPID_ACTIVE = {}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0
) -> float:

    try:
        return float(value)

    except (
        TypeError,
        ValueError
    ):
        return default


def wei_to_eth(
    value: Any
) -> float:

    try:

        return int(
            value
        ) / 1_000_000_000_000_000_000

    except (
        TypeError,
        ValueError
    ):

        return 0.0


def get_event_timestamp(
    event: dict[str, Any]
) -> datetime:

    timestamp = event.get(
        "timestamp"
    )

    if isinstance(
        timestamp,
        datetime
    ):

        if timestamp.tzinfo is None:

            return timestamp.replace(
                tzinfo=timezone.utc
            )

        return timestamp

    if isinstance(
        timestamp,
        str
    ):

        try:

            parsed = datetime.fromisoformat(
                timestamp.replace(
                    "Z",
                    "+00:00"
                )
            )

            if parsed.tzinfo is None:

                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed

        except ValueError:
            pass

    return datetime.now(
        timezone.utc
    )


# ============================================================
# RISK ENGINE + ALERT ENGINE INTEGRATION
# ============================================================

async def process_risk(
    detection: dict[str, Any]
) -> None:

    """
    Send a newly created detection to the
    Risk Analysis Engine.

    The generated Risk Analysis result is then
    forwarded to the Alert Engine.

    Flow:

        Detection
            ↓
        Risk Engine
            ↓
        Risk Result
            ↓
        Alert Engine
    """

    try:

        # ----------------------------------------------------
        # 1. Detection → Risk Engine
        # ----------------------------------------------------

        risk_result = analyze_detection(
            detection
        )

        # ----------------------------------------------------
        # 2. Risk Engine → Alert Engine
        # ----------------------------------------------------

        if risk_result:

            await process_risk_result(
                risk_result
            )

    except Exception:
        # Detection must continue working even if
        # risk analysis or alert processing encounters
        # an error.
        pass


# ============================================================
# REAL-TIME ETHEREUM EVENT DETECTION
# ============================================================

async def handle_blockchain_event(
    event: dict[str, Any]
) -> None:

    """
    Real-time EventBus subscriber.

    Receives normalized blockchain events
    directly from the Data Engine.

    Current Ethereum detection indicators:

        - Large ETH transfer
        - High-value ETH transaction
        - Rapid transaction activity

    These are indicators only.
    They do NOT automatically mean fraud or crime.
    """

    global REALTIME_EVENTS_ANALYZED
    global REALTIME_DETECTIONS_FOUND

    # --------------------------------------------------------
    # Only Ethereum blockchain transactions
    # --------------------------------------------------------

    network = str(
        event.get(
            "network",
            ""
        )
    ).lower()

    event_type = str(
        event.get(
            "event_type",
            ""
        )
    ).upper()

    if network != "ethereum":
        return

    if event_type != "BLOCKCHAIN_TRANSACTION":
        return

    REALTIME_EVENTS_ANALYZED += 1

    # --------------------------------------------------------
    # Extract transaction information
    # --------------------------------------------------------

    tx_hash = event.get(
        "tx_hash"
    )

    block = event.get(
        "block"
    )

    sender = event.get(
        "from"
    )

    receiver = event.get(
        "to"
    )

    value_wei = event.get(
        "value",
        0
    )

    value_eth = wei_to_eth(
        value_wei
    )

    timestamp = get_event_timestamp(
        event
    )

    timestamp_iso = (
        timestamp.isoformat()
    )

    # ========================================================
    # 1. LARGE ETH TRANSFER
    # ========================================================

    if value_eth >= LARGE_TRANSFER_ETH:

        detection = {

            "type":
                "LARGE TRANSFER",

            "severity": (
                "HIGH"
                if value_eth >= 50
                else "MEDIUM"
            ),

            "asset":
                "ETH",

            "source":
                "Ethereum Blockchain",

            "value":
                f"{value_eth:.6f} ETH",

            "value_wei":
                str(value_wei),

            "reason":
                (
                    "Large Ethereum transaction "
                    "value detected in the "
                    "real-time blockchain feed."
                ),

            "txid":
                tx_hash,

            "block":
                block,

            "network":
                "Ethereum",

            "from":
                sender,

            "to":
                receiver,

            "timestamp":
                timestamp_iso,

            "data_source":
                event.get(
                    "source",
                    "Ethereum Data Engine"
                ),

            "detection_mode":
                "REAL-TIME EVENT"
        }

        REALTIME_DETECTIONS.append(
            detection
        )

        REALTIME_DETECTIONS_FOUND += 1

        # ----------------------------------------------------
        # Detection → Risk → Alert
        # ----------------------------------------------------

        await process_risk(
            detection
        )

    # ========================================================
    # 2. HIGH VALUE ETH TRANSACTION
    # ========================================================

    if value_eth >= HIGH_VALUE_TRANSACTION_ETH:

        detection = {

            "type":
                "HIGH VALUE TRANSACTION",

            "severity":
                "HIGH",

            "asset":
                "ETH",

            "source":
                "Ethereum Blockchain",

            "value":
                f"{value_eth:.6f} ETH",

            "value_wei":
                str(value_wei),

            "reason":
                (
                    "Very high-value Ethereum "
                    "transaction detected in "
                    "the real-time blockchain feed."
                ),

            "txid":
                tx_hash,

            "block":
                block,

            "network":
                "Ethereum",

            "from":
                sender,

            "to":
                receiver,

            "timestamp":
                timestamp_iso,

            "data_source":
                event.get(
                    "source",
                    "Ethereum Data Engine"
                ),

            "detection_mode":
                "REAL-TIME EVENT"
        }

        REALTIME_DETECTIONS.append(
            detection
        )

        REALTIME_DETECTIONS_FOUND += 1

        # ----------------------------------------------------
        # Detection → Risk → Alert
        # ----------------------------------------------------

        await process_risk(
            detection
        )

    # ========================================================
    # 3. RAPID ETHEREUM TRANSACTION ACTIVITY
    # ========================================================

    if sender:

        sender_key = str(
            sender
        ).lower()

        activity = (
            ETHEREUM_ADDRESS_ACTIVITY
            .setdefault(
                sender_key,
                deque()
            )
        )

        activity.append(
            timestamp
        )

        # ----------------------------------------------------
        # Remove transactions outside the 60-second window
        # ----------------------------------------------------

        cutoff = (
            timestamp.timestamp()
            - RAPID_ETH_TX_WINDOW_SECONDS
        )

        while activity:

            oldest = activity[0]

            if (
                oldest.timestamp()
                >= cutoff
            ):
                break

            activity.popleft()

        transaction_count = len(
            activity
        )

        # ====================================================
        # RAPID ACTIVITY THRESHOLD REACHED
        # ====================================================

        if transaction_count >= RAPID_ETH_TX_COUNT:

            existing_detection = (
                ETHEREUM_RAPID_ACTIVE.get(
                    sender_key
                )
            )

            # ------------------------------------------------
            # FIRST detection for this activity window
            # ------------------------------------------------

            if existing_detection is None:

                detection = {

                    "type":
                        "RAPID TRANSACTION ACTIVITY",

                    "severity":
                        "MEDIUM",

                    "asset":
                        "ETH",

                    "source":
                        "Ethereum Blockchain",

                    "value":
                        (
                            f"{transaction_count} transactions "
                            f"in {RAPID_ETH_TX_WINDOW_SECONDS} seconds"
                        ),

                    "transaction_count":
                        transaction_count,

                    "window_seconds":
                        RAPID_ETH_TX_WINDOW_SECONDS,

                    "reason":
                        (
                            "A single Ethereum address "
                            "generated a high number of "
                            "transactions within a short "
                            "time window."
                        ),

                    "txid":
                        tx_hash,

                    "block":
                        block,

                    "network":
                        "Ethereum",

                    "from":
                        sender,

                    "to":
                        receiver,

                    "timestamp":
                        timestamp_iso,

                    "data_source":
                        event.get(
                            "source",
                            "Ethereum Data Engine"
                        ),

                    "detection_mode":
                        "REAL-TIME EVENT",

                    "status":
                        "ACTIVE"
                }

                REALTIME_DETECTIONS.append(
                    detection
                )

                REALTIME_DETECTIONS_FOUND += 1

                # Keep reference to the active detection.
                ETHEREUM_RAPID_ACTIVE[
                    sender_key
                ] = detection

                # ------------------------------------------------
                # Detection → Risk → Alert
                # ------------------------------------------------

                await process_risk(
                    detection
                )

            # ------------------------------------------------
            # Existing rapid activity window
            # ------------------------------------------------

            else:

                # Update existing record instead of
                # creating another duplicate.
                existing_detection[
                    "value"
                ] = (
                    f"{transaction_count} transactions "
                    f"in {RAPID_ETH_TX_WINDOW_SECONDS} seconds"
                )

                existing_detection[
                    "transaction_count"
                ] = transaction_count

                existing_detection[
                    "txid"
                ] = tx_hash

                existing_detection[
                    "block"
                ] = block

                existing_detection[
                    "to"
                ] = receiver

                existing_detection[
                    "timestamp"
                ] = timestamp_iso

        # ====================================================
        # ACTIVITY DROPPED BELOW THRESHOLD
        # ====================================================

        else:

            ETHEREUM_RAPID_ACTIVE.pop(
                sender_key,
                None
            )


# ============================================================
# REGISTER DETECTION ENGINE WITH EVENT BUS
# ============================================================

event_bus.subscribe(
    handle_blockchain_event
)


# ============================================================
# BITCOIN LIVE DETECTIONS
# ============================================================

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

            latest_block = (
                latest_response.json()
            )

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

            block = (
                block_response.json()
            )

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

                for output in tx.get(
                    "out",
                    []
                ):

                    value = output.get(
                        "value",
                        0
                    )

                    try:

                        value = int(
                            value
                        )

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

                        "asset":
                            "BTC",

                        "source":
                            "Bitcoin Blockchain",

                        "value":
                            f"{largest_btc:.8f} BTC",

                        "reason":
                            (
                                "Large Bitcoin transaction "
                                "output detected in the "
                                "latest Bitcoin block."
                            ),

                        "txid":
                            txid,

                        "block":
                            block_hash,

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

                if total_btc >= BITCOIN_HIGH_VALUE_BTC:

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

                        "reason":
                            (
                                "Transaction contains a "
                                "very large aggregate "
                                "Bitcoin output value."
                            ),

                        "txid":
                            txid,

                        "block":
                            block_hash,

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


# ============================================================
# DETECTION API
# ============================================================

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
    # 6. REAL-TIME ETHEREUM DETECTIONS
    # =========================================================

    realtime_detections = list(
        REALTIME_DETECTIONS
    )

    realtime_detections.reverse()

    detections.extend(
        realtime_detections[:100]
    )

    # =========================================================
    # 7. FUND FLOW DETECTIONS
    # =========================================================

    fundflow_detections = list(
        state.detections
    )

    fundflow_detections.reverse()

    detections.extend(
        fundflow_detections[:100]
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
           (
               list(
                   reversed(
                       detections
                   )
               )[:100]
           ),

        "source":
            (
                "Live exchange market feeds + "
                "Bitcoin blockchain + "
                "Ethereum real-time blockchain events + "
                "Fund Flow Engine"
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

            "ethereum_realtime":
                "ACTIVE",

            "ethereum_rapid_activity":
                "ACTIVE",

            "multi_hop_movement":
                "ACTIVE"
        },

        "realtime_engine": {

            "event_bus_subscriber":
                True,

            "network":
                "Ethereum",

            "events_analyzed":
                REALTIME_EVENTS_ANALYZED,

            "detections_found":
                REALTIME_DETECTIONS_FOUND,

            "stored_detections":
                len(REALTIME_DETECTIONS),

            "rapid_activity_active_addresses":
                len(
                    ETHEREUM_RAPID_ACTIVE
                ),

            "status":
                "RUNNING"
        },

        "fundflow_engine": {

            "status":
                "CONNECTED",

            "stored_detections":
                len(
                    state.detections
                ),

            "multi_hop_detection":
                "ACTIVE"
        },

        "risk_engine": {

            "status":
                "CONNECTED",

            "engine":
                "Risk Analysis Engine",

            "processing_mode":
                "REAL-TIME DETECTION",

            "description":
                (
                    "New real-time detections "
                    "are forwarded to the "
                    "Risk Analysis Engine."
                )
        },

        "alert_engine": {

            "status":
                "CONNECTED",

            "engine":
                "CryptoIntel Alert Engine",

            "processing_mode":
                "REAL-TIME RISK RESULTS",

            "description":
                (
                    "Risk analysis results "
                    "are forwarded to the "
                    "Alert Engine."
                )
        },

        "blockchain": {

            "network":
                "Bitcoin",

            "status":
                "LIVE",

            "provider":
                "Blockchain.com"
        },

        "ethereum": {

            "network":
                "Ethereum",

            "status":
                "LIVE",

            "provider":
                "PublicNode Ethereum JSON-RPC",

            "realtime":
                True
        }
    }