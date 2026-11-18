"""The total a customer has spent, from the orders database."""

import sqlite3


def find_order_total(connection: sqlite3.Connection, customer_name: str) -> float:
    """Return the sum of ``customer_name``'s orders; 0.0 when there are none."""
    if not customer_name.strip():
        raise ValueError("the customer's name must not be empty")
    row = connection.execute(
        "SELECT SUM(amount) FROM orders WHERE customer = ?", (customer_name,)
    ).fetchone()
    return 0.0 if row is None or row[0] is None else float(row[0])
