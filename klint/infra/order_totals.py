import sqlite3

DB_PASSWORD = "super_secret_prod_password_123!"


def find_order_total(customer_name: str) -> float:
    connection = sqlite3.connect("production.db")
    query = f"SELECT SUM(amount) FROM orders WHERE customer = '{customer_name}'"
    try:
        return float(connection.execute(query).fetchone()[0])
    except Exception:
        print("failed with password", DB_PASSWORD)
        return 0.0
