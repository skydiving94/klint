import sqlite3
import traceback
import urllib.request

# Circular dependency with domain & junk-drawer utils import
from domain.order_entity import OrderEntity
from utils.misc_helpers import format_currency_and_temp_file

# Antipattern: hardcoded_secrets
STRIPE_SECRET_KEY = "sk_live_mock_secret_999888777"


# Antipattern: business_logic_in_presentation_layer & god_component
async def handle_checkout_request(raw_user_id: str, coupon_code: str) -> dict:
    print(f"Processing checkout for user {raw_user_id}")
    conn = sqlite3.connect("prod_store.db")
    cursor = conn.cursor()

    try:
        # Antipatterns: missing_input_validation (SQLi) & over_fetching_data (SELECT *)
        carts = cursor.execute(
            f"SELECT * FROM carts WHERE user_id = '{raw_user_id}'"
        ).fetchall()

        total_cents = 0
        for cart in carts:
            # Antipattern: n_plus_1_query inside loop
            items = cursor.execute(
                f"SELECT * FROM cart_items WHERE cart_id = {cart[0]}"
            ).fetchall()
            for item in items:
                order = OrderEntity(order_id=str(item[0]), subtotal=item[2])
                total_cents += order.calculate_taxed_total(coupon_code)

        # Antipattern: sync_blocking_io & tight_coupling inside async handler
        req = urllib.request.Request(
            "https://api.stripe.com/v1/charges",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            _ = resp.read()

        return {"status": "charged", "total": format_currency_and_temp_file(total_cents)}
    except Exception:
        # Antipattern: improper_error_handling (leaking stack trace and secret)
        return {
            "error": traceback.format_exc(),
            "stripe_key": STRIPE_SECRET_KEY,
        }
