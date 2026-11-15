"""Keeps the shop's stock levels in step with the supplier's catalogue."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)

BATCH_SIZE = 500
STALE_AFTER_HOURS = 24


class SupplierCatalogue(Protocol):
    """The supplier's stock feed, behind whatever client the app wires in."""

    async def list_stock(self, skus: Sequence[str]) -> list[dict]: ...

    async def list_changed_since(self, since: datetime) -> list[dict]: ...


class StockStore(Protocol):
    """The stock table of the shop's database."""

    async def find_levels(self, skus: Sequence[str]) -> dict[str, int]: ...

    async def save_levels(self, sku_to_level: dict[str, int]) -> None: ...

    async def list_tracked_skus(self, after: str, limit: int) -> list[str]: ...

    async def record_sync(self, finished_at: datetime, changed: int) -> None: ...


class StockChange(Enum):
    RESTOCKED = "restocked"
    DEPLETED = "depleted"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class StockUpdate:
    sku: str
    old_level: int
    new_level: int

    def classify(self) -> StockChange:
        if self.new_level > self.old_level:
            return StockChange.RESTOCKED
        if self.new_level < self.old_level:
            return StockChange.DEPLETED
        return StockChange.UNCHANGED


@dataclass(frozen=True)
class SyncReport:
    checked: int
    updates: tuple[StockUpdate, ...]
    rejected_skus: tuple[str, ...]

    def count(self, change: StockChange) -> int:
        return sum(update.classify() is change for update in self.updates)


def split_into_batches(skus: Sequence[str], size: int = BATCH_SIZE) -> list[list[str]]:
    """Return ``skus`` in lists of at most ``size``, in order."""
    if size < 1:
        raise ValueError("A batch holds at least one SKU")
    return [list(skus[index : index + size]) for index in range(0, len(skus), size)]


def is_valid_sku(sku: object) -> bool:
    """Return True for a SKU of 3 to 32 letters, digits and dashes."""
    return (
        isinstance(sku, str)
        and 3 <= len(sku) <= 32
        and all(character.isalnum() or character == "-" for character in sku)
    )


def read_level(row: dict) -> int | None:
    """Return the stock level of a supplier row; None when it is not usable."""
    level = row.get("available")
    if isinstance(level, bool) or not isinstance(level, int):
        return None
    return level if level >= 0 else None


async def list_all_tracked_skus(store: StockStore) -> list[str]:
    """Return every SKU the shop tracks, reading them a page at a time."""
    skus: list[str] = []
    after = ""
    while True:
        page = await store.list_tracked_skus(after, BATCH_SIZE)
        skus.extend(page)
        if len(page) < BATCH_SIZE:
            return skus
        after = page[-1]


async def reconcile_stock(
    catalogue: SupplierCatalogue, store: StockStore, skus: Sequence[str]
) -> SyncReport:
    """Bring the shop's level of each SKU in ``skus`` to the supplier's.

    The SKUs are sent to the supplier a batch at a time, and each batch's
    levels are read and saved in one query each. A row the supplier sends
    for a SKU not asked about, or with a level that is not usable, is
    rejected and logged; the others are still saved.
    """
    valid_skus = [sku for sku in skus if is_valid_sku(sku)]
    rejected: list[str] = [sku for sku in skus if not is_valid_sku(sku)]
    if rejected:
        logger.warning("Skipping %s SKUs that are not valid", len(rejected))
    updates: list[StockUpdate] = []

    for batch in split_into_batches(valid_skus):
        asked = set(batch)
        try:
            supplier_rows = await catalogue.list_stock(batch)
        except (TimeoutError, ConnectionError):
            logger.warning("The supplier did not answer for a batch of %s", len(batch))
            rejected.extend(batch)
            continue

        sku_to_supplier_level: dict[str, int] = {}
        for row in supplier_rows:
            sku = row.get("sku")
            if not isinstance(sku, str) or sku not in asked:
                logger.warning("The supplier sent a SKU not asked about")
                continue
            level = read_level(row)
            if level is None:
                rejected.append(sku)
                continue
            sku_to_supplier_level[sku] = level

        missing = asked - set(sku_to_supplier_level) - set(rejected)
        for sku in sorted(missing):
            logger.info("The supplier no longer lists %s; setting it to 0", sku)
            sku_to_supplier_level[sku] = 0

        sku_to_shop_level = await store.find_levels(sorted(sku_to_supplier_level))
        changed: dict[str, int] = {}
        for sku, new_level in sorted(sku_to_supplier_level.items()):
            old_level = sku_to_shop_level.get(sku, 0)
            update = StockUpdate(sku=sku, old_level=old_level, new_level=new_level)
            updates.append(update)
            if update.classify() is not StockChange.UNCHANGED:
                changed[sku] = new_level

        if changed:
            await store.save_levels(changed)
        logger.info(
            "Batch of %s: %s changed, %s rejected so far",
            len(batch),
            len(changed),
            len(rejected),
        )

    finished_at = datetime.now(timezone.utc)
    changed_count = sum(
        update.classify() is not StockChange.UNCHANGED for update in updates
    )
    await store.record_sync(finished_at, changed_count)
    return SyncReport(
        checked=len(valid_skus),
        updates=tuple(updates),
        rejected_skus=tuple(sorted(set(rejected))),
    )


async def sync_changed_stock(
    catalogue: SupplierCatalogue, store: StockStore, since: datetime
) -> SyncReport:
    """Bring in only the SKUs the supplier changed since ``since``."""
    rows = await catalogue.list_changed_since(since)
    skus = sorted({row["sku"] for row in rows if is_valid_sku(row.get("sku"))})
    return await reconcile_stock(catalogue, store, skus)


async def sync_all_stock(catalogue: SupplierCatalogue, store: StockStore) -> SyncReport:
    """Bring every tracked SKU's level to the supplier's."""
    skus = await list_all_tracked_skus(store)
    return await reconcile_stock(catalogue, store, skus)


async def sync_with_retries(
    catalogue: SupplierCatalogue,
    store: StockStore,
    since: datetime,
    attempts: int = 3,
    pause_seconds: float = 5.0,
) -> SyncReport:
    """Run sync_changed_stock, trying again after a pause when the supplier is down."""
    if attempts < 1:
        raise ValueError("At least one attempt is needed")
    for attempt in range(1, attempts + 1):
        try:
            return await sync_changed_stock(catalogue, store, since)
        except (TimeoutError, ConnectionError):
            if attempt == attempts:
                raise
            logger.warning("Sync attempt %s failed; trying again", attempt)
            await asyncio.sleep(pause_seconds * attempt)
    raise AssertionError("unreachable")


def describe_report(report: SyncReport) -> str:
    """Return a one-line summary of a sync, for the operations channel."""
    return (
        f"Checked {report.checked} SKUs: "
        f"{report.count(StockChange.RESTOCKED)} restocked, "
        f"{report.count(StockChange.DEPLETED)} depleted, "
        f"{len(report.rejected_skus)} rejected"
    )


def list_depleted_skus(updates: Iterable[StockUpdate]) -> list[str]:
    """Return the SKUs that ran out, in order."""
    return sorted(
        update.sku
        for update in updates
        if update.new_level == 0 and update.old_level > 0
    )


def is_sync_stale(last_finished_at: datetime | None, now: datetime) -> bool:
    """Return True when the last sync is older than STALE_AFTER_HOURS, or never ran."""
    if last_finished_at is None:
        return True
    return (now - last_finished_at).total_seconds() > STALE_AFTER_HOURS * 3600
