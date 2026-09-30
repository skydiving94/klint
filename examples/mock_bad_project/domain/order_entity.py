import sqlite3
import urllib.request

# Antipattern: layering_violation & circular_package_dependencies (inner domain importing outer api & utils)
from api import checkout_routes
from utils import misc_helpers


# Antipattern: leaky_abstraction (domain entity directly coupled to SQLite and HTTP client)
class OrderEntity:
    def __init__(self, order_id: str, subtotal: int):
        self.order_id = order_id
        self.subtotal = subtotal

    def calculate_taxed_total(self, coupon_code: str) -> int:
        print(f"Calculating tax for order {self.order_id} using {checkout_routes.STRIPE_SECRET_KEY}")
        conn = sqlite3.connect("prod_store.db")
        # Antipattern: missing_input_validation (SQL injection inside domain model)
        row = conn.execute(
            f"SELECT discount_pct FROM coupons WHERE code = '{coupon_code}'"
        ).fetchone()
        discount = row[0] if row else 0

        # Antipattern: tight_coupling (direct HTTP call inside domain entity)
        with urllib.request.urlopen("https://tax-service.internal/rate") as resp:
            tax_rate = float(resp.read().decode("utf-8") or 0.08)

        discounted = self.subtotal * (100 - discount) // 100
        return int(discounted * (1.0 + tax_rate)) + misc_helpers.MAGIC_FEE
