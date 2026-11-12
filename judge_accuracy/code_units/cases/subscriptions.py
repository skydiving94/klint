"""Customer subscriptions: starting, changing, pausing, renewing and cancelling them."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14
GRACE_DAYS = 7
MAX_PAUSE_DAYS = 90


class SubscriptionState(Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAUSED = "paused"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class BillingInterval(Enum):
    MONTH = "month"
    YEAR = "year"


@dataclass(frozen=True)
class Plan:
    plan_id: str
    name: str
    interval: BillingInterval
    price: Decimal
    seat_limit: int
    is_public: bool = True


@dataclass(frozen=True)
class Subscription:
    subscription_id: int
    customer_id: int
    plan_id: str
    state: SubscriptionState
    seats: int
    current_period_end: date
    paused_until: date | None = None
    cancel_at_period_end: bool = False


class SubscriptionStore(Protocol):
    """The subscription table, behind the database the app wires in."""

    async def find(self, subscription_id: int) -> Subscription | None: ...

    async def find_for_customer(self, customer_id: int) -> Subscription | None: ...

    async def insert(self, subscription: Subscription) -> int: ...

    async def save(self, subscription: Subscription) -> None: ...

    async def list_due(self, on: date, limit: int) -> list[Subscription]: ...


class RenewalCharger(Protocol):
    """Charges a renewal through whichever payment provider the app wires in."""

    async def charge_renewal(
        self, customer_id: int, amount: Decimal, description: str
    ) -> bool: ...


class SubscriptionError(Exception):
    """A change to a subscription was refused; the message is safe to show."""


class PlanCatalogue:
    """The plans customers can subscribe to, looked up by ID.

    Plans are given when the catalogue is built, as read from configuration;
    the catalogue never changes after that.
    """

    def __init__(self, plans: Sequence[Plan]) -> None:
        self._plan_id_to_plan = {plan.plan_id: plan for plan in plans}
        if len(self._plan_id_to_plan) != len(plans):
            raise ValueError("Two plans share an ID")

    def find_plan(self, plan_id: str) -> Plan:
        """Return the plan ``plan_id``; SubscriptionError when there is none."""
        plan = self._plan_id_to_plan.get(plan_id)
        if plan is None:
            raise SubscriptionError("This plan does not exist")
        return plan

    def list_public_plans(self) -> list[Plan]:
        """Return the plans shown on the pricing page, cheapest first."""
        return sorted(
            (plan for plan in self._plan_id_to_plan.values() if plan.is_public),
            key=lambda plan: plan.price,
        )

    def find_upgrade(self, plan_id: str) -> Plan | None:
        """Return the next dearer public plan of the same interval; None if none."""
        plan = self.find_plan(plan_id)
        dearer = [
            other
            for other in self.list_public_plans()
            if other.interval is plan.interval and other.price > plan.price
        ]
        return dearer[0] if dearer else None


def find_period_end(start: date, interval: BillingInterval) -> date:
    """Return the day a period of ``interval`` that starts on ``start`` ends."""
    if interval is BillingInterval.YEAR:
        try:
            return start.replace(year=start.year + 1)
        except ValueError:
            return start.replace(year=start.year + 1, day=28)
    month = start.month % 12 + 1
    year = start.year + (start.month == 12)
    day = min(start.day, 28)
    return date(year, month, day)


def find_prorated_charge(
    old_plan: Plan, new_plan: Plan, seats: int, days_left: int, days_in_period: int
) -> Decimal:
    """Return what moving to ``new_plan`` costs for the rest of the period."""
    if days_in_period <= 0:
        raise ValueError("A period lasts at least a day")
    difference = (new_plan.price - old_plan.price) * seats
    return max(difference * days_left / days_in_period, Decimal(0)).quantize(
        Decimal("0.01")
    )


class SubscriptionService:
    """Changes customers' subscriptions, keeping each change to the plan's rules.

    Every SubscriptionError message is safe to show to the customer. The
    service reads and writes subscriptions through the store, and charges
    renewals and upgrades through the charger.
    """

    def __init__(
        self,
        store: SubscriptionStore,
        catalogue: PlanCatalogue,
        charger: RenewalCharger,
    ) -> None:
        self._store = store
        self._catalogue = catalogue
        self._charger = charger

    async def start_trial(self, customer_id: int, plan_id: str, today: date) -> int:
        """Start a trial of the plan for a customer with no subscription."""
        if await self._store.find_for_customer(customer_id) is not None:
            raise SubscriptionError("You already have a subscription")
        plan = self._catalogue.find_plan(plan_id)
        if not plan.is_public:
            raise SubscriptionError("This plan does not exist")
        return await self._store.insert(
            Subscription(
                subscription_id=0,
                customer_id=customer_id,
                plan_id=plan.plan_id,
                state=SubscriptionState.TRIAL,
                seats=1,
                current_period_end=today + timedelta(days=TRIAL_DAYS),
            )
        )

    async def change_seats(self, subscription_id: int, seats: int) -> Subscription:
        """Set the number of seats, within the plan's limit."""
        subscription = await self._find_changeable(subscription_id)
        plan = self._catalogue.find_plan(subscription.plan_id)
        if not 1 <= seats <= plan.seat_limit:
            raise SubscriptionError(f"Choose 1 to {plan.seat_limit} seats")
        changed = replace(subscription, seats=seats)
        await self._store.save(changed)
        return changed

    async def change_plan(
        self, subscription_id: int, plan_id: str, today: date
    ) -> Subscription:
        """Move to another plan of the same interval, charging the difference now."""
        subscription = await self._find_changeable(subscription_id)
        old_plan = self._catalogue.find_plan(subscription.plan_id)
        new_plan = self._catalogue.find_plan(plan_id)
        if new_plan.interval is not old_plan.interval:
            raise SubscriptionError("Change the billing interval at renewal")
        if subscription.seats > new_plan.seat_limit:
            raise SubscriptionError("Remove seats before moving to this plan")
        period_start = subscription.current_period_end - timedelta(
            days=365 if old_plan.interval is BillingInterval.YEAR else 30
        )
        charge = find_prorated_charge(
            old_plan,
            new_plan,
            subscription.seats,
            (subscription.current_period_end - today).days,
            (subscription.current_period_end - period_start).days,
        )
        if charge > 0 and not await self._charger.charge_renewal(
            subscription.customer_id, charge, f"Upgrade to {new_plan.name}"
        ):
            raise SubscriptionError("The upgrade could not be charged")
        changed = replace(subscription, plan_id=new_plan.plan_id)
        await self._store.save(changed)
        return changed

    async def pause(
        self, subscription_id: int, until: date, today: date
    ) -> Subscription:
        """Pause an active subscription until a day at most MAX_PAUSE_DAYS away."""
        subscription = await self._find_changeable(subscription_id)
        if subscription.state is not SubscriptionState.ACTIVE:
            raise SubscriptionError("Only an active subscription can be paused")
        if not today < until <= today + timedelta(days=MAX_PAUSE_DAYS):
            raise SubscriptionError(f"Pause for 1 to {MAX_PAUSE_DAYS} days")
        changed = replace(
            subscription, state=SubscriptionState.PAUSED, paused_until=until
        )
        await self._store.save(changed)
        return changed

    async def resume(self, subscription_id: int) -> Subscription:
        """Resume a paused subscription now."""
        subscription = await self._find_changeable(subscription_id)
        if subscription.state is not SubscriptionState.PAUSED:
            raise SubscriptionError("The subscription is not paused")
        changed = replace(
            subscription, state=SubscriptionState.ACTIVE, paused_until=None
        )
        await self._store.save(changed)
        return changed

    async def cancel(self, subscription_id: int) -> Subscription:
        """Cancel at the end of the current period; it stays usable until then."""
        subscription = await self._find_changeable(subscription_id)
        changed = replace(subscription, cancel_at_period_end=True)
        await self._store.save(changed)
        logger.info("Subscription %s will end on %s", subscription_id, changed.current_period_end)
        return changed

    async def renew_due(self, today: date, batch_size: int = 200) -> int:
        """Renew, end or mark past due each subscription due today; return how many.

        A subscription past due for GRACE_DAYS is cancelled.
        """
        handled = 0
        for subscription in await self._store.list_due(today, batch_size):
            await self._renew_one(subscription, today)
            handled += 1
        return handled

    async def _renew_one(self, subscription: Subscription, today: date) -> None:
        if subscription.cancel_at_period_end:
            await self._store.save(replace(subscription, state=SubscriptionState.CANCELLED))
            return
        if subscription.state is SubscriptionState.PAUSED:
            if subscription.paused_until and subscription.paused_until > today:
                return
            subscription = replace(subscription, state=SubscriptionState.ACTIVE)
        plan = self._catalogue.find_plan(subscription.plan_id)
        is_charged = await self._charger.charge_renewal(
            subscription.customer_id,
            plan.price * subscription.seats,
            f"{plan.name}, {subscription.seats} seats",
        )
        if is_charged:
            await self._store.save(
                replace(
                    subscription,
                    state=SubscriptionState.ACTIVE,
                    current_period_end=find_period_end(today, plan.interval),
                )
            )
        elif (today - subscription.current_period_end).days >= GRACE_DAYS:
            await self._store.save(replace(subscription, state=SubscriptionState.CANCELLED))
            logger.info("Cancelled subscription %s after the grace period", subscription.subscription_id)
        else:
            await self._store.save(replace(subscription, state=SubscriptionState.PAST_DUE))

    async def _find_changeable(self, subscription_id: int) -> Subscription:
        subscription = await self._store.find(subscription_id)
        if subscription is None:
            raise SubscriptionError("The subscription was not found")
        if subscription.state is SubscriptionState.CANCELLED:
            raise SubscriptionError("The subscription has ended")
        return subscription
