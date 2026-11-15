"""Builds customer invoices for a billing period and charges them."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
DEFAULT_TAX_RATE = Decimal("0.20")
PAYMENT_TIMEOUT_SECONDS = float(os.environ.get("PAYMENT_TIMEOUT_SECONDS", "10"))


class BillingStore(Protocol):
    """The reads and writes invoicing needs from the billing database."""

    async def list_usage(
        self, account_ids: Sequence[int], start: date, end: date
    ) -> list[dict]: ...

    async def list_accounts(self, account_ids: Sequence[int]) -> list[dict]: ...

    async def save_invoices(self, invoices: Sequence[Invoice]) -> None: ...

    async def mark_paid(self, invoice_id: str, payment_reference: str) -> None: ...


class PaymentGateway(Protocol):
    """Charges a customer's saved payment method."""

    async def charge(
        self, customer_reference: str, amount: Decimal, currency: str, timeout: float
    ) -> str: ...


class InvoiceError(Exception):
    """An invoice could not be built or charged; the message is safe to show."""


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    quantity: Decimal
    unit_price: Decimal

    def find_amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(CENT, ROUND_HALF_UP)


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    account_id: int
    currency: str
    period_start: date
    period_end: date
    lines: tuple[InvoiceLine, ...] = field(default_factory=tuple)
    tax_rate: Decimal = DEFAULT_TAX_RATE

    def find_subtotal(self) -> Decimal:
        return sum((line.find_amount() for line in self.lines), Decimal(0))

    def find_tax(self) -> Decimal:
        return (self.find_subtotal() * self.tax_rate).quantize(CENT, ROUND_HALF_UP)

    def find_total(self) -> Decimal:
        return self.find_subtotal() + self.find_tax()


def format_invoice_id(account_id: int, period_end: date) -> str:
    return f"INV-{period_end:%Y%m}-{account_id:06d}"


def _check_period(start: date, end: date) -> None:
    if end <= start:
        raise InvoiceError("The billing period must end after it starts")
    if (end - start).days > 92:
        raise InvoiceError("A billing period is at most a quarter long")


def _find_tax_rate(account: dict) -> Decimal:
    """Return the account's tax rate: none for a tax-exempt account."""
    if account.get("is_tax_exempt"):
        return Decimal(0)
    rate = account.get("tax_rate")
    return DEFAULT_TAX_RATE if rate is None else Decimal(str(rate))


def build_account_invoice(
    account: dict, usage_rows: Sequence[dict], start: date, end: date
) -> Invoice | None:
    """Return the account's invoice for its usage in the period; None when it owes nothing.

    The usage of each meter is summed into a line, topped up to the
    account's minimum fee, and the account's discount taken off. Raises
    InvoiceError for a discount over 100%.
    """
    account_id = account["id"]
    meter_to_quantity: dict[str, Decimal] = {}
    meter_to_price: dict[str, Decimal] = {}
    for row in usage_rows:
        meter = row["meter"]
        meter_to_quantity[meter] = meter_to_quantity.get(
            meter, Decimal(0)
        ) + Decimal(str(row["quantity"]))
        meter_to_price[meter] = Decimal(str(row["unit_price"]))

    lines = []
    for meter in sorted(meter_to_quantity):
        quantity = meter_to_quantity[meter]
        if quantity <= 0:
            continue
        lines.append(
            InvoiceLine(
                description=f"{meter} usage, {start:%d %b} to {end:%d %b %Y}",
                quantity=quantity,
                unit_price=meter_to_price[meter],
            )
        )

    minimum_fee = Decimal(str(account.get("minimum_monthly_fee") or 0))
    subtotal = sum((line.find_amount() for line in lines), Decimal(0))
    if minimum_fee > subtotal:
        lines.append(
            InvoiceLine(
                description="Minimum monthly fee top-up",
                quantity=Decimal(1),
                unit_price=(minimum_fee - subtotal).quantize(CENT, ROUND_HALF_UP),
            )
        )

    discount_percent = Decimal(str(account.get("discount_percent") or 0))
    if discount_percent > 0:
        if discount_percent > 100:
            raise InvoiceError(f"Account {account_id} has a discount over 100%")
        discount = (
            sum((line.find_amount() for line in lines), Decimal(0))
            * discount_percent
            / 100
        ).quantize(CENT, ROUND_HALF_UP)
        lines.append(
            InvoiceLine(
                description=f"Discount, {discount_percent}%",
                quantity=Decimal(1),
                unit_price=-discount,
            )
        )

    if not lines:
        return None
    return Invoice(
        invoice_id=format_invoice_id(account_id, end),
        account_id=account_id,
        currency=account.get("currency", "EUR"),
        period_start=start,
        period_end=end,
        lines=tuple(lines),
        tax_rate=_find_tax_rate(account),
    )


async def build_invoices(
    store: BillingStore, account_ids: Sequence[int], start: date, end: date
) -> list[Invoice]:
    """Return an invoice for each account of ``account_ids`` for the period.

    The usage and the accounts of every account are read in one query each.
    An account with no usage in the period gets no invoice. Raises
    InvoiceError for a period that is not valid.
    """
    _check_period(start, end)
    if not account_ids:
        return []
    accounts = await store.list_accounts(account_ids)
    account_id_to_account = {account["id"]: account for account in accounts}
    missing = sorted(set(account_ids) - set(account_id_to_account))
    if missing:
        logger.warning("Skipping %s accounts that do not exist", len(missing))

    usage_rows = await store.list_usage(sorted(account_id_to_account), start, end)
    account_id_to_rows: dict[int, list[dict]] = {}
    for row in usage_rows:
        account_id_to_rows.setdefault(row["account_id"], []).append(row)

    invoices = [
        invoice
        for account_id, rows in sorted(account_id_to_rows.items())
        if (
            invoice := build_account_invoice(
                account_id_to_account[account_id], rows, start, end
            )
        )
        is not None
    ]
    logger.info("Built %s invoices for %s accounts", len(invoices), len(account_ids))
    return invoices


async def charge_invoices(
    store: BillingStore,
    gateway: PaymentGateway,
    invoices: Sequence[Invoice],
    account_id_to_customer_reference: dict[int, str],
) -> list[str]:
    """Charge each invoice to its account's saved payment method.

    Returns the IDs of the invoices that could not be charged; each failure
    is logged without the gateway's internal details, and the other
    invoices are still charged.
    """
    failed: list[str] = []
    for invoice in invoices:
        customer_reference = account_id_to_customer_reference.get(invoice.account_id)
        if customer_reference is None:
            logger.warning("Invoice %s has no payment method", invoice.invoice_id)
            failed.append(invoice.invoice_id)
            continue
        total = invoice.find_total()
        if total <= 0:
            await store.mark_paid(invoice.invoice_id, "nothing-to-charge")
            continue
        try:
            payment_reference = await gateway.charge(
                customer_reference, total, invoice.currency, PAYMENT_TIMEOUT_SECONDS
            )
        except (TimeoutError, ConnectionError):
            logger.warning("Could not reach the gateway for %s", invoice.invoice_id)
            failed.append(invoice.invoice_id)
            continue
        await store.mark_paid(invoice.invoice_id, payment_reference)
        logger.info("Charged invoice %s", invoice.invoice_id)
    return failed


async def close_billing_period(
    store: BillingStore,
    gateway: PaymentGateway,
    account_ids: Sequence[int],
    start: date,
    end: date,
    account_id_to_customer_reference: dict[int, str],
) -> list[str]:
    """Build, save and charge the period's invoices; return those not charged.

    Raises InvoiceError when the invoices cannot be built; no invoice is
    saved then.
    """
    invoices = await build_invoices(store, account_ids, start, end)
    if not invoices:
        logger.info("No invoices to close for %s to %s", start, end)
        return []
    await store.save_invoices(invoices)
    failed = await charge_invoices(
        store, gateway, invoices, account_id_to_customer_reference
    )
    if failed:
        logger.warning("%s of %s invoices were not charged", len(failed), len(invoices))
    return failed


def summarize_invoices(invoices: Sequence[Invoice]) -> dict[str, Decimal]:
    """Return the total invoiced in each currency."""
    currency_to_total: dict[str, Decimal] = {}
    for invoice in invoices:
        currency_to_total[invoice.currency] = (
            currency_to_total.get(invoice.currency, Decimal(0)) + invoice.find_total()
        )
    return currency_to_total


def render_invoice_text(invoice: Invoice) -> str:
    """Return the invoice as plain text, one line per invoice line."""
    rows = [
        f"Invoice {invoice.invoice_id}",
        f"Period: {invoice.period_start:%d %b %Y} to {invoice.period_end:%d %b %Y}",
        "",
    ]
    for line in invoice.lines:
        rows.append(
            f"{line.description:<48} {line.quantity:>10} x {line.unit_price:>10} "
            f"= {line.find_amount():>10} {invoice.currency}"
        )
    rows += [
        "",
        f"{'Subtotal':<72} {invoice.find_subtotal():>10} {invoice.currency}",
        f"{'Tax':<72} {invoice.find_tax():>10} {invoice.currency}",
        f"{'Total':<72} {invoice.find_total():>10} {invoice.currency}",
    ]
    return "\n".join(rows)
