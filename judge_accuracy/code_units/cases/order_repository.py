"""Reads and writes customer orders in the shop's SQL database."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

logger = logging.getLogger(__name__)

ORDER_COLUMNS = "id, customer_id, status, total, created_at"
LINE_COLUMNS = "order_id, product_id, quantity, unit_price"
MAX_PAGE_SIZE = 200


class Database(Protocol):
    """The queries the repository needs from an async SQL connection."""

    async def fetch_all(self, sql: str, params: Sequence[object]) -> list[dict]: ...

    async def fetch_one(self, sql: str, params: Sequence[object]) -> dict | None: ...

    async def execute(self, sql: str, params: Sequence[object]) -> int: ...


class OrderNotFoundError(LookupError):
    """No order has the ID asked for."""


@dataclass(frozen=True)
class OrderLine:
    product_id: int
    quantity: int
    unit_price: Decimal

    def find_subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass(frozen=True)
class Order:
    order_id: int
    customer_id: int
    status: str
    total: Decimal
    created_at: datetime
    lines: tuple[OrderLine, ...] = ()


def _build_order(row: dict, lines: Sequence[OrderLine] = ()) -> Order:
    return Order(
        order_id=row["id"],
        customer_id=row["customer_id"],
        status=row["status"],
        total=Decimal(row["total"]),
        created_at=row["created_at"],
        lines=tuple(lines),
    )


def _build_line(row: dict) -> OrderLine:
    return OrderLine(
        product_id=row["product_id"],
        quantity=row["quantity"],
        unit_price=Decimal(row["unit_price"]),
    )


def _check_page_size(page_size: int) -> int:
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be from 1 to {MAX_PAGE_SIZE}")
    return page_size


async def find_order(database: Database, order_id: int) -> Order:
    """Return the order ``order_id`` with its lines.

    Raises OrderNotFoundError when there is none.
    """
    row = await database.fetch_one(
        f"SELECT {ORDER_COLUMNS} FROM orders WHERE id = ?", (order_id,)
    )
    if row is None:
        raise OrderNotFoundError(order_id)
    line_rows = await database.fetch_all(
        f"SELECT {LINE_COLUMNS} FROM order_lines WHERE order_id = ?", (order_id,)
    )
    return _build_order(row, [_build_line(line) for line in line_rows])


async def list_customer_orders(
    database: Database, customer_id: int, page_size: int = 50, after_id: int = 0
) -> list[Order]:
    """Return a page of the customer's orders, oldest first, with their lines.

    The lines of the whole page are read in one query.
    """
    rows = await database.fetch_all(
        f"SELECT {ORDER_COLUMNS} FROM orders "
        "WHERE customer_id = ? AND id > ? ORDER BY id LIMIT ?",
        (customer_id, after_id, _check_page_size(page_size)),
    )
    return await _attach_lines(database, rows)


async def _attach_lines(database: Database, rows: Sequence[dict]) -> list[Order]:
    """Return an order for each row, with the lines of all of them read at once."""
    if not rows:
        return []
    order_ids = [row["id"] for row in rows]
    placeholders = ", ".join("?" for _ in order_ids)
    line_rows = await database.fetch_all(
        f"SELECT {LINE_COLUMNS} FROM order_lines WHERE order_id IN ({placeholders})",
        order_ids,
    )
    order_id_to_lines: dict[int, list[OrderLine]] = {
        order_id: [] for order_id in order_ids
    }
    for line_row in line_rows:
        order_id_to_lines[line_row["order_id"]].append(_build_line(line_row))
    return [_build_order(row, order_id_to_lines[row["id"]]) for row in rows]


async def list_orders_by_status(
    database: Database, status: str, page_size: int = 50
) -> list[Order]:
    """Return the oldest orders in ``status``, with their lines."""
    if status not in {"pending", "paid", "shipped", "cancelled"}:
        raise ValueError(f"Unknown order status: {status!r}")
    rows = await database.fetch_all(
        f"SELECT {ORDER_COLUMNS} FROM orders WHERE status = ? ORDER BY id LIMIT ?",
        (status, _check_page_size(page_size)),
    )
    return await _attach_lines(database, rows)


async def create_order(
    database: Database, customer_id: int, lines: Sequence[OrderLine]
) -> int:
    """Store a new pending order and its lines; return its ID.

    Raises ValueError when there is no line, or a line's quantity is not
    positive.
    """
    if not lines:
        raise ValueError("An order needs at least one line")
    if any(line.quantity < 1 for line in lines):
        raise ValueError("Each line needs a quantity of at least 1")
    total = sum((line.find_subtotal() for line in lines), Decimal(0))
    order_id = await database.execute(
        "INSERT INTO orders (customer_id, status, total) VALUES (?, 'pending', ?)",
        (customer_id, str(total)),
    )
    values = ", ".join("(?, ?, ?, ?)" for _ in lines)
    params: list[object] = []
    for line in lines:
        params.extend((order_id, line.product_id, line.quantity, str(line.unit_price)))
    await database.execute(
        f"INSERT INTO order_lines ({LINE_COLUMNS}) VALUES {values}", params
    )
    logger.info("Created order %s for customer %s", order_id, customer_id)
    return order_id


async def update_order_status(database: Database, order_id: int, status: str) -> None:
    """Move the order ``order_id`` to ``status``.

    Raises OrderNotFoundError when there is no such order, and ValueError
    for a status the shop does not use.
    """
    if status not in {"pending", "paid", "shipped", "cancelled"}:
        raise ValueError(f"Unknown order status: {status!r}")
    changed = await database.execute(
        "UPDATE orders SET status = ? WHERE id = ?", (status, order_id)
    )
    if changed == 0:
        raise OrderNotFoundError(order_id)
    logger.info("Order %s is now %s", order_id, status)


async def cancel_orders(database: Database, order_ids: Sequence[int]) -> int:
    """Cancel every pending order of ``order_ids``; return how many were cancelled."""
    if not order_ids:
        return 0
    placeholders = ", ".join("?" for _ in order_ids)
    cancelled = await database.execute(
        f"UPDATE orders SET status = 'cancelled' "
        f"WHERE status = 'pending' AND id IN ({placeholders})",
        list(order_ids),
    )
    logger.info("Cancelled %s of %s orders", cancelled, len(order_ids))
    return cancelled


async def sum_customer_spending(
    database: Database, customer_ids: Sequence[int]
) -> dict[int, Decimal]:
    """Return what each customer of ``customer_ids`` spent on paid orders."""
    if not customer_ids:
        return {}
    placeholders = ", ".join("?" for _ in customer_ids)
    rows = await database.fetch_all(
        "SELECT customer_id, SUM(total) AS spent FROM orders "
        f"WHERE status IN ('paid', 'shipped') AND customer_id IN ({placeholders}) "
        "GROUP BY customer_id",
        list(customer_ids),
    )
    customer_id_to_spent = {customer_id: Decimal(0) for customer_id in customer_ids}
    for row in rows:
        customer_id_to_spent[row["customer_id"]] = Decimal(row["spent"])
    return customer_id_to_spent


async def count_orders_by_status(database: Database) -> dict[str, int]:
    """Return how many orders are in each status."""
    rows = await database.fetch_all(
        "SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status", ()
    )
    return {row["status"]: row["order_count"] for row in rows}


async def find_best_selling_products(
    database: Database, since: datetime, limit: int = 10
) -> list[tuple[int, int]]:
    """Return the products sold most since ``since``, with the quantity sold."""
    rows = await database.fetch_all(
        "SELECT order_lines.product_id, SUM(order_lines.quantity) AS sold "
        "FROM order_lines JOIN orders ON orders.id = order_lines.order_id "
        "WHERE orders.status IN ('paid', 'shipped') AND orders.created_at >= ? "
        "GROUP BY order_lines.product_id ORDER BY sold DESC LIMIT ?",
        (since, _check_page_size(limit)),
    )
    return [(row["product_id"], row["sold"]) for row in rows]


async def delete_cancelled_orders(database: Database, before: datetime) -> int:
    """Delete the orders cancelled before ``before`` and their lines.

    Returns how many orders were deleted.
    """
    await database.execute(
        "DELETE FROM order_lines WHERE order_id IN "
        "(SELECT id FROM orders WHERE status = 'cancelled' AND created_at < ?)",
        (before,),
    )
    deleted = await database.execute(
        "DELETE FROM orders WHERE status = 'cancelled' AND created_at < ?", (before,)
    )
    logger.info("Deleted %s cancelled orders from before %s", deleted, before)
    return deleted
