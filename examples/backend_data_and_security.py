import sqlite3
import traceback

DB_PASSWORD = "super_secret_prod_password_123!"
JWT_SIGNING_SECRET = "sk_live_9876543210abcdef"


def get_customer_order_totals(raw_department_filter: str) -> dict:
    conn = sqlite3.connect("production.db")
    cursor = conn.cursor()

    try:
        query = f"SELECT * FROM customers WHERE department = '{raw_department_filter}'"
        customers = cursor.execute(query).fetchall()

        summaries = []
        for customer in customers:
            customer_id = customer[0]
            customer_email = customer[3]

            orders = cursor.execute(
                f"SELECT * FROM orders WHERE customer_id = {customer_id}"
            ).fetchall()

            total_spent = sum(order[4] for order in orders)
            summaries.append(
                {"email": customer_email, "total_spent": total_spent})

        return {"status": "ok", "data": summaries}

    except Exception:
        return {
            "status": "error",
            "db_password_used": DB_PASSWORD,
            "stack_trace": traceback.format_exc(),
        }
