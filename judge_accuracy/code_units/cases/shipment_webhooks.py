"""Takes in carriers' tracking webhooks and moves shipments through their states."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256_000
MAX_EVENTS_PER_CALL = 100
CARRIER_TO_SECRET_VARIABLE = {
    "parcelfast": "PARCELFAST_WEBHOOK_SECRET",
    "northpost": "NORTHPOST_WEBHOOK_SECRET",
}


class ShipmentState(Enum):
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    LOST = "lost"


# The states a shipment may move to from each state.
STATE_TO_NEXT_STATES = {
    ShipmentState.LABEL_CREATED: {ShipmentState.IN_TRANSIT, ShipmentState.LOST},
    ShipmentState.IN_TRANSIT: {
        ShipmentState.IN_TRANSIT,
        ShipmentState.OUT_FOR_DELIVERY,
        ShipmentState.RETURNED,
        ShipmentState.LOST,
    },
    ShipmentState.OUT_FOR_DELIVERY: {
        ShipmentState.DELIVERED,
        ShipmentState.IN_TRANSIT,
        ShipmentState.RETURNED,
    },
    ShipmentState.DELIVERED: set(),
    ShipmentState.RETURNED: set(),
    ShipmentState.LOST: {ShipmentState.IN_TRANSIT},
}


class ShipmentStore(Protocol):
    """The shipment tables, behind the database the app wires in."""

    async def find_shipments(
        self, carrier: str, tracking_numbers: Sequence[str]
    ) -> list[dict]: ...

    async def save_transitions(self, transitions: Sequence[Transition]) -> None: ...

    async def has_seen_event(self, carrier: str, event_ids: Sequence[str]) -> set[str]: ...


class CustomerNotifier(Protocol):
    async def notify_delivery_change(
        self, order_id: int, state: ShipmentState, at: datetime
    ) -> None: ...


@dataclass(frozen=True)
class TrackingEvent:
    event_id: str
    tracking_number: str
    state: ShipmentState
    happened_at: datetime


@dataclass(frozen=True)
class Transition:
    shipment_id: int
    order_id: int
    old_state: ShipmentState
    new_state: ShipmentState
    happened_at: datetime
    event_id: str


@dataclass(frozen=True)
class WebhookResult:
    status: int
    body: dict


def find_carrier_secret(carrier: str) -> bytes | None:
    """Return the carrier's webhook secret from the environment; None if unknown."""
    variable = CARRIER_TO_SECRET_VARIABLE.get(carrier)
    if variable is None:
        return None
    value = os.environ.get(variable)
    return None if not value else value.encode()


def is_signature_valid(secret: bytes, body: bytes, signature: str) -> bool:
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_event(data: object) -> TrackingEvent | None:
    """Return the event a webhook item describes; None when an item is not valid."""
    if not isinstance(data, dict):
        return None
    event_id = data.get("id")
    tracking_number = data.get("tracking_number")
    state_name = data.get("status")
    happened_at_text = data.get("occurred_at")
    if not (
        isinstance(event_id, str)
        and isinstance(tracking_number, str)
        and isinstance(state_name, str)
        and isinstance(happened_at_text, str)
    ):
        return None
    if not 6 <= len(tracking_number) <= 40 or not tracking_number.isalnum():
        return None
    try:
        state = ShipmentState(state_name)
        happened_at = datetime.fromisoformat(happened_at_text)
    except ValueError:
        return None
    if happened_at.tzinfo is None:
        happened_at = happened_at.replace(tzinfo=timezone.utc)
    return TrackingEvent(event_id, tracking_number, state, happened_at)


async def handle_tracking_webhook(
    store: ShipmentStore,
    notifier: CustomerNotifier,
    carrier: str,
    body: bytes,
    signature: str | None,
) -> WebhookResult:
    """Apply a carrier's batch of tracking events to the shipments it names.

    The call is refused unless it is signed with the carrier's secret. Each
    event moves its shipment to a new state only when the move is allowed
    and the event is newer than the shipment's last change; an event seen
    before is skipped. The shipments and the events seen are read in one
    query each, and every transition is saved in one write. A customer is
    told of a delivery, a return or a loss.
    """
    secret = find_carrier_secret(carrier)
    if secret is None:
        logger.warning("Webhook from an unknown carrier")
        return WebhookResult(404, {"error": "Unknown carrier"})
    if len(body) > MAX_BODY_BYTES:
        return WebhookResult(413, {"error": "The body is too large"})
    if signature is None or not is_signature_valid(secret, body, signature):
        logger.warning("Webhook from %s with a bad signature", carrier)
        return WebhookResult(401, {"error": "The signature is not valid"})

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return WebhookResult(400, {"error": "The body is not JSON"})
    items = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return WebhookResult(400, {"error": "'events' must be a list"})
    if len(items) > MAX_EVENTS_PER_CALL:
        return WebhookResult(
            413, {"error": f"Send at most {MAX_EVENTS_PER_CALL} events per call"}
        )

    events: list[TrackingEvent] = []
    rejected_count = 0
    for item in items:
        event = parse_event(item)
        if event is None:
            rejected_count += 1
            continue
        events.append(event)
    if rejected_count:
        logger.info("Rejected %s events from %s that are not valid", rejected_count, carrier)
    if not events:
        return WebhookResult(200, {"applied": 0, "rejected": rejected_count})

    seen_event_ids = await store.has_seen_event(
        carrier, [event.event_id for event in events]
    )
    new_events = [event for event in events if event.event_id not in seen_event_ids]
    new_events.sort(key=lambda event: event.happened_at)

    tracking_numbers = sorted({event.tracking_number for event in new_events})
    shipment_rows = await store.find_shipments(carrier, tracking_numbers)
    tracking_number_to_shipment = {
        row["tracking_number"]: row for row in shipment_rows
    }
    unknown_numbers = set(tracking_numbers) - set(tracking_number_to_shipment)
    if unknown_numbers:
        logger.info("%s events name shipments we do not have", len(unknown_numbers))

    tracking_number_to_state = {
        number: ShipmentState(row["state"])
        for number, row in tracking_number_to_shipment.items()
    }
    tracking_number_to_changed_at = {
        number: row["state_changed_at"]
        for number, row in tracking_number_to_shipment.items()
    }
    transitions: list[Transition] = []
    refused_moves = 0
    for event in new_events:
        shipment = tracking_number_to_shipment.get(event.tracking_number)
        if shipment is None:
            continue
        old_state = tracking_number_to_state[event.tracking_number]
        if event.happened_at <= tracking_number_to_changed_at[event.tracking_number]:
            continue
        if event.state not in STATE_TO_NEXT_STATES[old_state]:
            refused_moves += 1
            logger.info(
                "Refused move of shipment %s from %s to %s",
                shipment["id"],
                old_state.value,
                event.state.value,
            )
            continue
        transitions.append(
            Transition(
                shipment_id=shipment["id"],
                order_id=shipment["order_id"],
                old_state=old_state,
                new_state=event.state,
                happened_at=event.happened_at,
                event_id=event.event_id,
            )
        )
        tracking_number_to_state[event.tracking_number] = event.state
        tracking_number_to_changed_at[event.tracking_number] = event.happened_at

    if transitions:
        await store.save_transitions(transitions)
    for transition in transitions:
        if transition.new_state in {
            ShipmentState.DELIVERED,
            ShipmentState.RETURNED,
            ShipmentState.LOST,
        }:
            try:
                await notifier.notify_delivery_change(
                    transition.order_id, transition.new_state, transition.happened_at
                )
            except (TimeoutError, ConnectionError):
                logger.warning(
                    "Could not notify the customer of order %s", transition.order_id
                )

    logger.info(
        "Applied %s of %s events from %s; %s refused, %s seen before",
        len(transitions),
        len(events),
        carrier,
        refused_moves,
        len(seen_event_ids),
    )
    return WebhookResult(
        200,
        {
            "applied": len(transitions),
            "refused": refused_moves,
            "duplicates": len(seen_event_ids),
            "rejected": rejected_count,
        },
    )


def list_final_states() -> list[ShipmentState]:
    """Return the states a shipment never leaves."""
    return [state for state, next_states in STATE_TO_NEXT_STATES.items() if not next_states]


def describe_transition(transition: Transition) -> str:
    return (
        f"Shipment {transition.shipment_id} of order {transition.order_id}: "
        f"{transition.old_state.value} -> {transition.new_state.value} "
        f"at {transition.happened_at:%Y-%m-%d %H:%M} UTC"
    )
