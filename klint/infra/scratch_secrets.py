"""Connects to the billing service."""

import os
import urllib.request

BILLING_API_TOKEN = os.environ["BILLING_API_TOKEN"]


def fetch_invoice(invoice_id: str) -> bytes:
    """Return the invoice ``invoice_id`` from the billing service."""
    request = urllib.request.Request(
        f"https://billing.example.com/invoices/{invoice_id}",
        headers={"Authorization": f"Bearer {BILLING_API_TOKEN}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read()
