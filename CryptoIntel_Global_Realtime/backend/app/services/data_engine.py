"""
CryptoIntel Global Real-Time Data Engine

Flow:

Live Sources
    ↓
Data Engine
    ↓
Normalization
    ↓
Shared EventBus
    ↓
Detection / Risk / Alert Consumers

Current continuous blockchain ingestion:
    - Ethereum mainnet
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx

from .event_bus import event_bus
from .normalization import normalize_event


logger = logging.getLogger("cryptointel.data_engine")


EventHandler = Callable[
    [dict[str, Any]],
    Awaitable[None] | None
]


# =========================================================
# ETHEREUM
# =========================================================

ETHEREUM_RPC = (
    "https://ethereum-rpc.publicnode.com"
)

ETHEREUM_POLL_INTERVAL = 12


# =========================================================
# DATA ENGINE
# =========================================================

class DataEngine:

    def __init__(self) -> None:

        # IMPORTANT:
        # Use the single shared EventBus.
        self.event_bus = event_bus

        self._running = False

        self._tasks: set[
            asyncio.Task[Any]
        ] = set()

        # -------------------------------------------------
        # GENERAL EVENT METRICS
        # -------------------------------------------------

        self.events_received = 0

        self.events_published = 0

        self.events_failed = 0

        # -------------------------------------------------
        # ENGINE TIMING
        # -------------------------------------------------

        self.started_at: str | None = None

        self.last_event_at: str | None = None

        # -------------------------------------------------
        # ETHEREUM STATE
        # -------------------------------------------------

        self.ethereum_running = False

        self.ethereum_latest_block: int | None = None

        self.ethereum_blocks_processed = 0

        self.ethereum_transactions_processed = 0

        self.ethereum_last_block_at: str | None = None

        self.ethereum_last_error: str | None = None


    # =====================================================
    # START
    # =====================================================

    async def start(self) -> None:

        if self._running:
            return

        self._running = True

        self.started_at = self._utc_now()

        logger.info(
            "CryptoIntel Global Data Engine started."
        )

        # -------------------------------------------------
        # START ETHEREUM CONTINUOUS INGESTION
        # -------------------------------------------------

        ethereum_task = asyncio.create_task(
            self._ethereum_ingestion_loop()
        )

        self._tasks.add(
            ethereum_task
        )

        ethereum_task.add_done_callback(
            self._tasks.discard
        )


    # =====================================================
    # STOP
    # =====================================================

    async def stop(self) -> None:

        if not self._running:
            return

        self._running = False

        self.ethereum_running = False

        if self._tasks:

            for task in self._tasks:

                task.cancel()

            await asyncio.gather(
                *self._tasks,
                return_exceptions=True
            )

            self._tasks.clear()

        logger.info(
            "CryptoIntel Global Data Engine stopped."
        )


    # =====================================================
    # INGEST
    # =====================================================

    async def ingest(
        self,
        event: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:

        if not self._running:

            raise RuntimeError(
                "Data engine is not running."
            )

        self.events_received += 1

        try:

            normalized = normalize_event(
                event,
                source=source,
            )

            self.last_event_at = (
                normalized["timestamp"]
            )

            await self.event_bus.publish(
                normalized
            )

            self.events_published += 1

            return normalized

        except Exception:

            self.events_failed += 1

            logger.exception(
                "Failed to ingest event."
            )

            raise


    # =====================================================
    # SUBMIT
    # =====================================================

    def submit(
        self,
        event: dict[str, Any],
        source: str | None = None,
    ) -> asyncio.Task[Any]:

        task = asyncio.create_task(
            self.ingest(
                event,
                source=source,
            )
        )

        self._tasks.add(
            task
        )

        task.add_done_callback(
            self._tasks.discard
        )

        return task


    # =====================================================
    # SUBSCRIBE
    # =====================================================

    def subscribe(
        self,
        handler: EventHandler,
    ) -> None:

        self.event_bus.subscribe(
            handler
        )


    # =====================================================
    # UNSUBSCRIBE
    # =====================================================

    def unsubscribe(
        self,
        handler: EventHandler,
    ) -> None:

        self.event_bus.unsubscribe(
            handler
        )


    # =====================================================
    # ETHEREUM RPC
    # =====================================================

    async def _ethereum_rpc(
        self,
        client: httpx.AsyncClient,
        method: str,
        params: list[Any],
    ) -> Any:

        response = await client.post(
            ETHEREUM_RPC,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1,
            },
        )

        response.raise_for_status()

        data = response.json()

        if "error" in data:

            raise RuntimeError(
                data["error"].get(
                    "message",
                    "Ethereum RPC error"
                )
            )

        return data.get(
            "result"
        )


    # =====================================================
    # ETHEREUM GET LATEST BLOCK
    # =====================================================

    async def _ethereum_latest_block(
        self,
        client: httpx.AsyncClient,
    ) -> int:

        block_hex = await self._ethereum_rpc(
            client,
            "eth_blockNumber",
            [],
        )

        if not block_hex:

            raise RuntimeError(
                "Ethereum latest block was empty."
            )

        return int(
            block_hex,
            16
        )


    # =====================================================
    # ETHEREUM FETCH FULL BLOCK
    # =====================================================

    async def _ethereum_get_block(
        self,
        client: httpx.AsyncClient,
        block_number: int,
    ) -> dict[str, Any] | None:

        block = await self._ethereum_rpc(
            client,
            "eth_getBlockByNumber",
            [
                hex(block_number),
                True,
            ],
        )

        return block


    # =====================================================
    # ETHEREUM TRANSACTION EVENT
    # =====================================================

    async def _ingest_ethereum_transaction(
        self,
        tx: dict[str, Any],
        block_number: int,
        block_timestamp: int,
    ) -> None:

        if not tx:

            return

        tx_hash = tx.get(
            "hash"
        )

        if not tx_hash:

            return

        value_hex = (
            tx.get("value")
            or "0x0"
        )

        gas_hex = (
            tx.get("gas")
            or "0x0"
        )

        gas_price_hex = (
            tx.get("gasPrice")
            or "0x0"
        )

        nonce_hex = (
            tx.get("nonce")
            or "0x0"
        )

        try:

            value_wei = int(
                value_hex,
                16
            )

        except Exception:

            value_wei = 0

        try:

            gas = int(
                gas_hex,
                16
            )

        except Exception:

            gas = 0

        try:

            gas_price = int(
                gas_price_hex,
                16
            )

        except Exception:

            gas_price = 0

        try:

            nonce = int(
                nonce_hex,
                16
            )

        except Exception:

            nonce = 0

        event = {

            "event_type":
                "BLOCKCHAIN_TRANSACTION",

            "source":
                "PublicNode Ethereum JSON-RPC",

            "network":
                "Ethereum",

            "timestamp":
                block_timestamp,

            "tx_hash":
                tx_hash,

            "block":
                block_number,

            "from":
                tx.get("from"),

            "to":
                tx.get("to"),

            "value":
                value_wei,

            "token":
                "ETH",

            "gas":
                gas,

            "gas_price":
                gas_price,

            "nonce":
                nonce,

            "status":
                "LIVE",

            # Preserve the complete
            # original transaction.
            "raw":
                tx,
        }

        await self.ingest(
            event,
            source=(
                "PublicNode Ethereum JSON-RPC"
            ),
        )

        self.ethereum_transactions_processed += 1


    # =====================================================
    # ETHEREUM PROCESS BLOCK
    # =====================================================

    async def _process_ethereum_block(
        self,
        client: httpx.AsyncClient,
        block_number: int,
    ) -> None:

        block = await self._ethereum_get_block(
            client,
            block_number,
        )

        if not block:

            return

        timestamp_hex = (
            block.get("timestamp")
            or "0x0"
        )

        try:

            block_timestamp = int(
                timestamp_hex,
                16
            )

        except Exception:

            block_timestamp = int(
                datetime.now(
                    timezone.utc
                ).timestamp()
            )

        transactions = (
            block.get(
                "transactions",
                []
            )
        )

        # -------------------------------------------------
        # PROCESS EVERY TRANSACTION
        # -------------------------------------------------

        for tx in transactions:

            try:

                await self._ingest_ethereum_transaction(
                    tx,
                    block_number,
                    block_timestamp,
                )

            except Exception as e:

                self.events_failed += 1

                logger.error(
                    "Ethereum transaction ingestion "
                    "failed: %s",
                    e,
                )

        self.ethereum_blocks_processed += 1

        self.ethereum_latest_block = (
            block_number
        )

        self.ethereum_last_block_at = (
            self._utc_now()
        )


    # =====================================================
    # ETHEREUM CONTINUOUS INGESTION
    # =====================================================

    async def _ethereum_ingestion_loop(
        self,
    ) -> None:

        self.ethereum_running = True

        logger.info(
            "Ethereum continuous blockchain "
            "ingestion started."
        )

        previous_block: int | None = None

        while self._running:

            try:

                async with httpx.AsyncClient(
                    timeout=30,
                    headers={
                        "User-Agent":
                            "CryptoIntel/1.0"
                    },
                ) as client:

                    latest_block = (
                        await self._ethereum_latest_block(
                            client
                        )
                    )

                    # -------------------------------------
                    # INITIAL SYNC
                    # -------------------------------------

                    if previous_block is None:

                        previous_block = (
                            latest_block
                        )

                        logger.info(
                            "Ethereum ingestion "
                            "initialized at block %s",
                            latest_block,
                        )

                        await self._process_ethereum_block(
                            client,
                            latest_block,
                        )

                    # -------------------------------------
                    # NEW BLOCKS
                    # -------------------------------------

                    elif latest_block > previous_block:

                        # Process every newly observed
                        # block in sequence.
                        for block_number in range(
                            previous_block + 1,
                            latest_block + 1,
                        ):

                            if not self._running:

                                break

                            await self._process_ethereum_block(
                                client,
                                block_number,
                            )

                        previous_block = (
                            latest_block
                        )

                    self.ethereum_last_error = None

            except asyncio.CancelledError:

                raise

            except Exception as e:

                self.ethereum_last_error = (
                    str(e)
                )

                logger.error(
                    "Ethereum continuous ingestion "
                    "error: %s",
                    e,
                )

            await asyncio.sleep(
                ETHEREUM_POLL_INTERVAL
            )

        self.ethereum_running = False

        logger.info(
            "Ethereum continuous blockchain "
            "ingestion stopped."
        )


    # =====================================================
    # HEALTH
    # =====================================================

    def health(self) -> dict[str, Any]:

        return {

            "status": (
                "RUNNING"
                if self._running
                else "STOPPED"
            ),

            "started_at":
                self.started_at,

            "last_event_at":
                self.last_event_at,

            "events_received":
                self.events_received,

            "events_published":
                self.events_published,

            "events_failed":
                self.events_failed,

            "subscribers":
                self.event_bus.subscriber_count(),

            "ethereum": {

                "status": (
                    "RUNNING"
                    if self.ethereum_running
                    else "STOPPED"
                ),

                "latest_block":
                    self.ethereum_latest_block,

                "blocks_processed":
                    self.ethereum_blocks_processed,

                "transactions_processed":
                    self.ethereum_transactions_processed,

                "last_block_at":
                    self.ethereum_last_block_at,

                "last_error":
                    self.ethereum_last_error,
            },
        }


    # =====================================================
    # UTC TIME
    # =====================================================

    @staticmethod
    def _utc_now() -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()


# =========================================================
# SINGLE SHARED DATA ENGINE
# =========================================================

data_engine = DataEngine()