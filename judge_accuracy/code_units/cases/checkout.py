"""Turns a customer's cart into a placed order: prices, stock, payment and receipt."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
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


@dataclass(frozen=True)
class PricedCart:
    currency: str
    lines: tuple[dict, ...]
    subtotal: Decimal
    discount: Decimal
    shipping: Decimal
    vat: Decimal
    total: Decimal


def count_cart_quantities(request: CheckoutRequest) -> dict[str, int]:
    """Return how many of each SKU the cart holds; CheckoutError when it cannot be sold."""
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
    return sku_to_quantity


def check_coupon_code(code: str) -> str:
    """Return the coupon code as stored; CheckoutError when it cannot be one."""
    normalized = code.strip().upper()
    if not normalized.isalnum() or len(normalized) > 20:
        raise CheckoutError("This coupon code is not valid")
    return normalized


def price_cart(
    sku_to_product: dict[str, dict],
    sku_to_quantity: dict[str, int],
    coupon: dict | None,
    country: str,
    now: datetime,
) -> PricedCart:
    """Return the cart's lines, discount, shipping, VAT and total.

    Raises CheckoutError, with a message safe to show, when a product is no
    longer sold, the cart mixes currencies, or the coupon does not apply.
    """
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
    if coupon is not None:
        if not coupon["is_active"]:
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
            logger.warning("Coupon %s has an unknown kind", coupon.get("code"))
            raise CheckoutError("This coupon code is not valid")

    discounted = subtotal - discount
    shipping = (
        Decimal(0) if discounted >= FREE_SHIPPING_FROM else COUNTRY_TO_SHIPPING[country]
    )
    vat_rate = COUNTRY_TO_VAT[country]
    vat = to_cents((discounted + shipping) * vat_rate / (1 + vat_rate))
    return PricedCart(
        currency=currency,
        lines=tuple(order_lines),
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        vat=vat,
        total=discounted + shipping,
    )


def render_receipt(order_id: int, cart: PricedCart) -> str:
    """Return the text of the receipt emailed for an order."""
    receipt_lines = [f"Thank you for your order {order_id}.", ""]
    for line in cart.lines:
        receipt_lines.append(
            f"{line['quantity']} x {line['title']}: {line['line_total']} {cart.currency}"
        )
    receipt_lines += [
        "",
        f"Subtotal: {cart.subtotal} {cart.currency}",
        f"Discount: -{cart.discount} {cart.currency}" if cart.discount else "",
        f"Shipping: {cart.shipping} {cart.currency}",
        f"Total: {cart.total} {cart.currency}, of which VAT {cart.vat}",
    ]
    return "\n".join(line for line in receipt_lines if line)


async def place_order(
    store: CheckoutStore,
    payments: PaymentService,
    receipts: ReceiptSender,
    request: CheckoutRequest,
) -> PlacedOrder:
    """Place the order a checkout request describes, undoing each step that fails.

    Reserved stock is released and an authorized payment voided when a later
    step fails. Raises CheckoutError, with a message safe to show, when the
    order cannot be placed.
    """
    sku_to_quantity = count_cart_quantities(request)
    sku_to_product = await store.find_products(sorted(sku_to_quantity))
    coupon = None
    if request.coupon_code:
        coupon = await store.find_coupon(check_coupon_code(request.coupon_code))
        if coupon is None:
            raise CheckoutError("This coupon code is not valid")
    cart = price_cart(
        sku_to_product,
        sku_to_quantity,
        coupon,
        request.country,
        datetime.now(timezone.utc),
    )

    short_skus = await store.reserve_stock(sku_to_quantity)
    if short_skus:
        raise CheckoutError("Some products in your cart just sold out")
    try:
        authorization_id = await payments.authorize(
            request.payment_token, cart.total, cart.currency
        )
    except (TimeoutError, ConnectionError):
        await store.release_stock(sku_to_quantity)
        logger.warning("The payment service did not answer for customer %s", request.customer_id)
        raise CheckoutError("We could not reach the payment service; try again") from None
    except ValueError:
        await store.release_stock(sku_to_quantity)
        raise CheckoutError("Your payment was declined") from None

    try:
        order_id = await store.insert_order(
            {
                "customer_id": request.customer_id,
                "email": request.email,
                "country": request.country,
                "currency": cart.currency,
                "subtotal": str(cart.subtotal),
                "discount": str(cart.discount),
                "shipping": str(cart.shipping),
                "vat": str(cart.vat),
                "total": str(cart.total),
                "coupon_code": request.coupon_code,
                "payment_authorization": authorization_id,
            },
            cart.lines,
        )
        await payments.capture(authorization_id)
    except Exception:
        logger.exception("Storing the order failed after payment; undoing it")
        await payments.void(authorization_id)
        await store.release_stock(sku_to_quantity)
        raise CheckoutError("Your order could not be placed; you were not charged") from None

    try:
        await receipts.send_receipt(request.email, order_id, render_receipt(order_id, cart))
    except (TimeoutError, ConnectionError):
        logger.warning("Could not send the receipt of order %s", order_id)
    logger.info("Order %s placed for %s %s", order_id, cart.total, cart.currency)
    return PlacedOrder(order_id=order_id, total=cart.total, currency=cart.currency)


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
