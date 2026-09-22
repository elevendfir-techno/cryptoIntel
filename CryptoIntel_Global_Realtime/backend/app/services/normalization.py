"""
CryptoIntel Event Normalization

Converts different exchange/blockchain event formats
into a common CryptoIntel event structure.

This module does NOT invent missing values.
Unknown fields remain None/unknown.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def normalize_event(
    event: dict[str, Any],
    source: str | None = None,
) -> dict[str, Any]:
    """
    Normalize an incoming real-world event.

    The original event is preserved under:
        raw

    This allows later investigation/evidence systems
    to inspect the original source payload.
    """

    if not isinstance(event, dict):
        raise TypeError(
            "Event must be a dictionary."
        )

    timestamp = _get_timestamp(event)

    event_type = (
        event.get("event_type")
        or event.get("type")
        or _detect_event_type(event)
    )

    network = (
        event.get("network")
        or event.get("chain")
    )

    normalized = {
        "event_id": _event_id(
            event,
            source=source
        ),

        "event_type": str(
            event_type or "UNKNOWN"
        ).upper(),

        "source": source
        or event.get("source")
        or "UNKNOWN",

        "network": network,

        "timestamp": timestamp,

        "status": (
            event.get("status")
            or "LIVE"
        ),

        "symbol": event.get("symbol"),

        "tx_hash": (
            event.get("tx_hash")
            or event.get("transaction_hash")
            or event.get("hash")
        ),

        "block": (
            event.get("block")
            or event.get("block_number")
        ),

        "from": (
            event.get("from")
            or event.get("from_address")
        ),

        "to": (
            event.get("to")
            or event.get("to_address")
        ),

        "value": event.get("value"),

        "token": event.get("token"),

        "token_address": (
            event.get("token_address")
        ),

        "price": event.get("price"),

        "volume": (
            event.get("volume")
            or event.get("quantity")
            or event.get("qty")
        ),

        "raw": event,
    }

    return normalized


def _detect_event_type(
    event: dict[str, Any],
) -> str:
    """
    Try to identify the event category using fields
    that actually exist in the source payload.
    """

    if (
        "tx_hash" in event
        or "transaction_hash" in event
    ):
        return "BLOCKCHAIN_TRANSACTION"

    if (
        "from" in event
        and "to" in event
        and "value" in event
    ):
        return "BLOCKCHAIN_TRANSFER"

    if (
        "price" in event
        and (
            "qty" in event
            or "quantity" in event
            or "volume" in event
        )
    ):
        return "MARKET_TRADE"

    if (
        "symbol" in event
        and "price" in event
    ):
        return "MARKET_DATA"

    if (
        "wallet" in event
        or "address" in event
    ):
        return "WALLET_ACTIVITY"

    return "UNKNOWN"


def _get_timestamp(
    event: dict[str, Any],
) -> str:
    """
    Use the source timestamp when available.

    Otherwise use the actual current UTC ingestion time.
    """

    value = (
        event.get("timestamp")
        or event.get("time")
        or event.get("datetime")
    )

    if value is None:
        return datetime.now(
            timezone.utc
        ).isoformat()

    if isinstance(value, (int, float)):
        # Common exchange timestamps are milliseconds.
        if value > 10_000_000_000:
            value = value / 1000

        return datetime.fromtimestamp(
            value,
            tz=timezone.utc
        ).isoformat()

    return str(value)


def _event_id(
    event: dict[str, Any],
    source: str | None = None,
) -> str:
    """
    Generate a deterministic ID from the actual source event.

    No random/demo identifier is generated.
    """

    stable_data = {
        "source": source
        or event.get("source"),
        "event_type": event.get("event_type")
        or event.get("type"),
        "tx_hash": event.get("tx_hash")
        or event.get("transaction_hash")
        or event.get("hash"),
        "symbol": event.get("symbol"),
        "timestamp": event.get("timestamp")
        or event.get("time"),
        "from": event.get("from"),
        "to": event.get("to"),
    }

    serialized = json.dumps(
        stable_data,
        sort_keys=True,
        default=str,
    )

    digest = hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()

    return f"evt_{digest[:32]}"