from pathlib import Path
import urllib.request
import json
import smtplib

# Antipattern: hardcoded_secrets
STRIPE_API_KEY = "sk_live_51H8abcXYZ999999"


# Antipattern: god_component (handles HTTP routing, disk I/O, billing, email, and reporting)
class OrderManagementGodService:
    async def process_checkout_and_notify(self, order_payload: dict) -> dict:
        # Antipattern: sync_blocking_io (heavy synchronous file read inside an async method on the main event loop)
        large_catalog_text = Path("/var/data/500mb_product_catalog.json").read_text(
            encoding="utf-8"
        )
        catalog = json.loads(large_catalog_text)

        # Antipatterns:
        # 1. tight_coupling (directly calling external Stripe HTTP endpoint without an adapter/interface)
        # 2. sync_blocking_io (blocking network request on the main async event loop thread)
        stripe_req = urllib.request.Request(
            "https://api.stripe.com/v1/charges",
            data=json.dumps(
                {"amount": order_payload["amount"], "currency": "usd"}).encode("utf-8"),
            headers={"Authorization": f"Bearer {STRIPE_API_KEY}"},
            method="POST",
        )
        with urllib.request.urlopen(stripe_req) as response:
            charge_result = json.loads(response.read().decode("utf-8"))

        # Antipattern: tight_coupling & sync_blocking_io (direct synchronous SMTP client inside checkout logic)
        smtp_conn = smtplib.SMTP("smtp.sendgrid.net", 587)
        smtp_conn.sendmail(
            "billing@example.com",
            order_payload["email"],
            f"Charged {charge_result.get('id')} for catalog size {len(catalog)}",
        )
        smtp_conn.quit()

        return {"charge_id": charge_result.get("id")}
