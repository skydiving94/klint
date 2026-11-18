"""Reads orders from the shop's database."""

import sqlite3


def find_orders(connection: sqlite3.Connection, customer_name: str) -> list[tuple]:
    """Return the orders of the customer named ``customer_name``."""
    query = "SELECT * FROM orders WHERE customer = '" + customer_name + "'"
    return connection.execute(query).fetchall()
