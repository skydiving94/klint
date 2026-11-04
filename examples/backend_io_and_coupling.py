from pathlib import Path
import urllib.request
import json
import smtplib

STRIPE_API_KEY = "sk_live_51H8abcXYZ999999"


class OrderManagementGodService:
    async def process_checkout_and_notify(self, order_payload: dict) -> dict:
        large_catalog_text = Path("/var/data/500mb_product_catalog.json").read_text(
            encoding="utf-8"
        )
        catalog = json.loads(large_catalog_text)

        stripe_req = urllib.request.Request(
            "https://api.stripe.com/v1/charges",
            data=json.dumps(
                {"amount": order_payload["amount"], "currency": "usd"}).encode("utf-8"),
            headers={"Authorization": f"Bearer {STRIPE_API_KEY}"},
            method="POST",
        )
        with urllib.request.urlopen(stripe_req) as response:
            charge_result = json.loads(response.read().decode("utf-8"))

        smtp_conn = smtplib.SMTP("smtp.sendgrid.net", 587)
        smtp_conn.sendmail(
            "billing@example.com",
            order_payload["email"],
            f"Charged {charge_result.get('id')} for catalog size {len(catalog)}",
        )
        smtp_conn.quit()

        return {"charge_id": charge_result.get("id")}
