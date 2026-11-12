"""Turns a customer's cart into a placed order: prices, stock, payment and receipt."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
MAX_CART_LINES = 50
MAX_QUANTITY = 99
FREE_SHIPPING_FROM = Decimal(os.environ.get("FREE_SHIPPING_FROM", "60"))
COUNTRY_TO_VAT = {
    "DE": Decimal("0.19"),
    "FR": Decimal("0.20"),
    "NL": Decimal("0.21"),
    "SE": Decimal("0.25"),
}
COUNTRY_TO_SHIPPING = {
    "DE": Decimal("4.90"),
    "FR": Decimal("6.90"),
    "NL": Decimal("5.90"),
    "SE": Decimal("9.90"),
}


class CheckoutStep(Enum):
    VALIDATED = "validated"
    PRICED = "priced"
    RESERVED = "reserved"
    PAID = "paid"
    PLACED = "placed"


class CheckoutStore(Protocol):
    """The tables checkout reads and writes, behind the app's database."""

    async def find_products(self, skus: Sequence[str]) -> dict[str, dict]: ...

    async def reserve_stock(self, sku_to_quantity: dict[str, int]) -> list[str]: ...

    async def release_stock(self, sku_to_quantity: dict[str, int]) -> None: ...

    async def find_coupon(self, code: str) -> dict | None: ...

    async def insert_order(self, order: dict, lines: Sequence[dict]) -> int: ...


class PaymentService(Protocol):
    async def authorize(self, payment_token: str, amount: Decimal, currency: str) -> str: ...

    async def capture(self, authorization_id: str) -> None: ...

    async def void(self, authorization_id: str) -> None: ...


class ReceiptSender(Protocol):
    async def send_receipt(self, email: str, order_id: int, text: str) -> None: ...


class CheckoutError(Exception):
    """The order could not be placed; the message is safe to show."""


@dataclass(frozen=True)
class CartLine:
    sku: str
    quantity: int


@dataclass(frozen=True)
class CheckoutRequest:
    customer_id: int
    email: str
    country: str
    lines: tuple[CartLine, ...]
    payment_token: str
    coupon_code: str | None = None


@dataclass(frozen=True)
class PlacedOrder:
    order_id: int
    total: Decimal
    currency: str


def to_cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, ROUND_HALF_UP)


async def place_order(
    store: CheckoutStore,
    payments: PaymentService,
    receipts: ReceiptSender,
    request: CheckoutRequest,
) -> PlacedOrder:
    """Check the cart, price it, reserve stock, take payment and store the order.

    Each step undoes the ones before it when it fails: reserved stock is
    released and an authorized payment voided. The products are read in one
    query and the stock of every line reserved in one write. Raises
    CheckoutError, with a message safe to show, when the order cannot be
    placed.
    """
    if not request.lines:
        raise CheckoutError("Your cart is empty")
    if len(request.lines) > MAX_CART_LINES:
        raise CheckoutError(f"A cart holds at most {MAX_CART_LINES} lines")
    if request.country not in COUNTRY_TO_VAT:
        raise CheckoutError("We do not deliver to this country yet")
    sku_to_quantity: dict[str, int] = {}
    for line in request.lines:
        if not 1 <= line.quantity <= MAX_QUANTITY:
            raise CheckoutError(f"Order 1 to {MAX_QUANTITY} of each product")
        sku_to_quantity[line.sku] = sku_to_quantity.get(line.sku, 0) + line.quantity
    if any(quantity > MAX_QUANTITY for quantity in sku_to_quantity.values()):
        raise CheckoutError(f"Order 1 to {MAX_QUANTITY} of each product")
    step = CheckoutStep.VALIDATED

    sku_to_product = await store.find_products(sorted(sku_to_quantity))
    unknown = sorted(set(sku_to_quantity) - set(sku_to_product))
    if unknown:
        raise CheckoutError("Some products in your cart are no longer sold")
    inactive = sorted(
        sku for sku, product in sku_to_product.items() if not product["is_active"]
    )
    if inactive:
        raise CheckoutError("Some products in your cart are no longer sold")
    currencies = {product["currency"] for product in sku_to_product.values()}
    if len(currencies) != 1:
        raise CheckoutError("Your cart mixes currencies; check out each separately")
    currency = currencies.pop()

    order_lines: list[dict] = []
    subtotal = Decimal(0)
    for sku, quantity in sorted(sku_to_quantity.items()):
        product = sku_to_product[sku]
        unit_price = Decimal(str(product["price"]))
        line_total = to_cents(unit_price * quantity)
        subtotal += line_total
        order_lines.append(
            {
                "sku": sku,
                "title": product["title"],
                "quantity": quantity,
                "unit_price": str(unit_price),
                "line_total": str(line_total),
            }
        )

    discount = Decimal(0)
    if request.coupon_code:
        code = request.coupon_code.strip().upper()
        if not code.isalnum() or len(code) > 20:
            raise CheckoutError("This coupon code is not valid")
        coupon = await store.find_coupon(code)
        now = datetime.now(timezone.utc)
        if coupon is None or not coupon["is_active"]:
            raise CheckoutError("This coupon code is not valid")
        if coupon["expires_at"] is not None and coupon["expires_at"] < now:
            raise CheckoutError("This coupon has expired")
        minimum = Decimal(str(coupon.get("minimum_subtotal") or 0))
        if subtotal < minimum:
            raise CheckoutError(f"This coupon needs a cart of at least {minimum}")
        if coupon["kind"] == "percent":
            percent = Decimal(str(coupon["value"]))
            discount = to_cents(subtotal * percent / 100)
        elif coupon["kind"] == "fixed":
            discount = min(Decimal(str(coupon["value"])), subtotal)
        else:
            logger.warning("Coupon %s has an unknown kind", code)
            raise CheckoutError("This coupon code is not valid")

    discounted = subtotal - discount
    shipping = (
        Decimal(0)
        if discounted >= FREE_SHIPPING_FROM
        else COUNTRY_TO_SHIPPING[request.country]
    )
    vat_rate = COUNTRY_TO_VAT[request.country]
    vat = to_cents((discounted + shipping) * vat_rate / (1 + vat_rate))
    total = discounted + shipping
    step = CheckoutStep.PRICED

    short_skus = await store.reserve_stock(sku_to_quantity)
    if short_skus:
        raise CheckoutError("Some products in your cart just sold out")
    step = CheckoutStep.RESERVED

    try:
        authorization_id = await payments.authorize(
            request.payment_token, total, currency
        )
    except (TimeoutError, ConnectionError):
        await store.release_stock(sku_to_quantity)
        logger.warning("The payment service did not answer for customer %s", request.customer_id)
        raise CheckoutError("We could not reach the payment service; try again") from None
    except ValueError:
        await store.release_stock(sku_to_quantity)
        raise CheckoutError("Your payment was declined") from None
    step = CheckoutStep.PAID

    try:
        order_id = await store.insert_order(
            {
                "customer_id": request.customer_id,
                "email": request.email,
                "country": request.country,
                "currency": currency,
                "subtotal": str(subtotal),
                "discount": str(discount),
                "shipping": str(shipping),
                "vat": str(vat),
                "total": str(total),
                "coupon_code": request.coupon_code,
                "payment_authorization": authorization_id,
            },
            order_lines,
        )
        await payments.capture(authorization_id)
    except Exception:
        logger.exception("Storing the order failed after payment; undoing it")
        await payments.void(authorization_id)
        await store.release_stock(sku_to_quantity)
        raise CheckoutError("Your order could not be placed; you were not charged") from None
    step = CheckoutStep.PLACED

    receipt_lines = [f"Thank you for your order {order_id}.", ""]
    for line in order_lines:
        receipt_lines.append(
            f"{line['quantity']} x {line['title']}: {line['line_total']} {currency}"
        )
    receipt_lines += [
        "",
        f"Subtotal: {subtotal} {currency}",
        f"Discount: -{discount} {currency}" if discount else "",
        f"Shipping: {shipping} {currency}",
        f"Total: {total} {currency}, of which VAT {vat}",
    ]
    try:
        await receipts.send_receipt(
            request.email, order_id, "\n".join(line for line in receipt_lines if line)
        )
    except (TimeoutError, ConnectionError):
        logger.warning("Could not send the receipt of order %s", order_id)
    logger.info("Order %s placed at step %s for %s %s", order_id, step.value, total, currency)
    return PlacedOrder(order_id=order_id, total=total, currency=currency)


def parse_checkout_request(customer_id: int, body: dict) -> CheckoutRequest:
    """Return the request a checkout body describes; CheckoutError when it is not valid."""
    email = body.get("email")
    country = body.get("country")
    token = body.get("payment_token")
    items = body.get("lines")
    if not (
        isinstance(email, str)
        and isinstance(country, str)
        and isinstance(token, str)
        and isinstance(items, list)
    ):
        raise CheckoutError("The checkout form is incomplete")
    lines = []
    for item in items:
        if not isinstance(item, dict):
            raise CheckoutError("The checkout form is incomplete")
        sku = item.get("sku")
        quantity = item.get("quantity")
        if not isinstance(sku, str) or isinstance(quantity, bool) or not isinstance(quantity, int):
            raise CheckoutError("The checkout form is incomplete")
        lines.append(CartLine(sku=sku.strip().upper(), quantity=quantity))
    coupon = body.get("coupon_code")
    return CheckoutRequest(
        customer_id=customer_id,
        email=email.strip().lower(),
        country=country.strip().upper(),
        lines=tuple(lines),
        payment_token=token,
        coupon_code=coupon if isinstance(coupon, str) and coupon.strip() else None,
    )


async def handle_checkout(
    store: CheckoutStore,
    payments: PaymentService,
    receipts: ReceiptSender,
    customer_id: int,
    body: dict,
) -> tuple[int, dict]:
    """Answer the checkout endpoint: the status code and the JSON body to send."""
    try:
        order = await place_order(
            store, payments, receipts, parse_checkout_request(customer_id, body)
        )
    except CheckoutError as error:
        return 422, {"error": str(error)}
    except Exception:
        logger.exception("Checkout failed for customer %s", customer_id)
        return 500, {"error": "Something went wrong; you were not charged"}
    return 201, {"order_id": order.order_id, "total": str(order.total), "currency": order.currency}
