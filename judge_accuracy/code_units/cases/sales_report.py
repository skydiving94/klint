"""Builds the monthly sales report the finance team downloads as CSV."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
REPORT_FOLDER = Path("reports")
REGIONS = ("north", "south", "east", "west")


class SalesStore(Protocol):
    """The sales tables, behind the database the app wires in."""

    async def sum_sales_by_day(
        self, start: date, end: date, regions: Sequence[str]
    ) -> list[dict]: ...

    async def sum_refunds_by_day(
        self, start: date, end: date, regions: Sequence[str]
    ) -> list[dict]: ...

    async def list_targets(self, month: date, regions: Sequence[str]) -> list[dict]: ...


class ReportError(Exception):
    """The report could not be built; the message is safe to show."""


@dataclass(frozen=True)
class ReportRequest:
    month: date
    regions: tuple[str, ...]
    is_refunds_included: bool = True


def parse_report_request(query: dict) -> ReportRequest:
    """Return the request a download link's query asks for.

    Raises ReportError when the month is not YYYY-MM or a region is unknown.
    """
    month_text = query.get("month")
    if not isinstance(month_text, str) or len(month_text) != 7:
        raise ReportError("Give the month as YYYY-MM")
    try:
        month = date(int(month_text[:4]), int(month_text[5:7]), 1)
    except ValueError:
        raise ReportError("Give the month as YYYY-MM") from None
    region_text = query.get("regions", ",".join(REGIONS))
    if not isinstance(region_text, str):
        raise ReportError("Give the regions as a comma-separated list")
    regions = tuple(sorted({region.strip() for region in region_text.split(",")}))
    unknown = [region for region in regions if region not in REGIONS]
    if unknown:
        raise ReportError(f"Unknown regions: {', '.join(unknown)}")
    return ReportRequest(
        month=month,
        regions=regions,
        is_refunds_included=query.get("refunds", "yes") != "no",
    )


def find_month_end(month: date) -> date:
    """Return the first day of the month after ``month``."""
    if month.month == 12:
        return date(month.year + 1, 1, 1)
    return date(month.year, month.month + 1, 1)


def to_money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, ROUND_HALF_UP)


def write_report_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


async def build_sales_report(store: SalesStore, request: ReportRequest) -> Path:
    """Write the month's sales report as CSV and return its path.

    The report has a row per day and region with sales, refunds and net
    sales, a total per region against its target, and a grand total. The
    sales, the refunds and the targets of every region are read in one query
    each, and the file is written off the event loop.
    """
    start = request.month
    end = find_month_end(start)
    if end > date.today().replace(day=1) and start > date.today():
        raise ReportError("The month has not started yet")
    regions = request.regions
    if not regions:
        raise ReportError("Choose at least one region")

    sales_rows = await store.sum_sales_by_day(start, end, regions)
    refund_rows = (
        await store.sum_refunds_by_day(start, end, regions)
        if request.is_refunds_included
        else []
    )
    target_rows = await store.list_targets(start, regions)

    day_region_to_sales: dict[tuple[date, str], Decimal] = {}
    for row in sales_rows:
        key = (row["day"], row["region"])
        day_region_to_sales[key] = day_region_to_sales.get(key, Decimal(0)) + to_money(
            row["amount"]
        )

    day_region_to_refunds: dict[tuple[date, str], Decimal] = {}
    for row in refund_rows:
        key = (row["day"], row["region"])
        day_region_to_refunds[key] = day_region_to_refunds.get(
            key, Decimal(0)
        ) + to_money(row["amount"])

    region_to_target = {
        row["region"]: to_money(row["target"]) for row in target_rows
    }
    missing_targets = [region for region in regions if region not in region_to_target]
    if missing_targets:
        logger.warning("No sales target for %s", ", ".join(missing_targets))

    days = sorted({day for day, _ in day_region_to_sales} | {
        day for day, _ in day_region_to_refunds
    })
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Day", "Region", "Sales", "Refunds", "Net sales"])

    region_to_sales: dict[str, Decimal] = {region: Decimal(0) for region in regions}
    region_to_refunds: dict[str, Decimal] = {region: Decimal(0) for region in regions}
    for day in days:
        for region in regions:
            sales = day_region_to_sales.get((day, region), Decimal(0))
            refunds = day_region_to_refunds.get((day, region), Decimal(0))
            if sales == 0 and refunds == 0:
                continue
            region_to_sales[region] += sales
            region_to_refunds[region] += refunds
            writer.writerow(
                [day.isoformat(), region, f"{sales}", f"{refunds}", f"{sales - refunds}"]
            )

    writer.writerow([])
    writer.writerow(["Region", "Sales", "Refunds", "Net sales", "Target", "Of target"])
    for region in regions:
        net = region_to_sales[region] - region_to_refunds[region]
        target = region_to_target.get(region)
        if target is None or target == 0:
            share = "no target"
        else:
            share = f"{(net / target * 100).quantize(Decimal('0.1'))}%"
        writer.writerow(
            [
                region,
                f"{region_to_sales[region]}",
                f"{region_to_refunds[region]}",
                f"{net}",
                "" if target is None else f"{target}",
                share,
            ]
        )

    total_sales = sum(region_to_sales.values(), Decimal(0))
    total_refunds = sum(region_to_refunds.values(), Decimal(0))
    total_target = sum(region_to_target.values(), Decimal(0))
    writer.writerow([])
    writer.writerow(
        [
            "All regions",
            f"{total_sales}",
            f"{total_refunds}",
            f"{total_sales - total_refunds}",
            f"{total_target}",
            (
                f"{((total_sales - total_refunds) / total_target * 100).quantize(Decimal('0.1'))}%"
                if total_target
                else "no target"
            ),
        ]
    )

    refund_share = (
        (total_refunds / total_sales * 100).quantize(Decimal("0.1"))
        if total_sales
        else Decimal(0)
    )
    if refund_share > 10:
        logger.warning(
            "Refunds are %s%% of sales in %s", refund_share, start.strftime("%B %Y")
        )
    best_region = max(
        regions,
        key=lambda region: region_to_sales[region] - region_to_refunds[region],
    )
    writer.writerow([])
    writer.writerow(["Best region", best_region])
    writer.writerow(["Refunds as a share of sales", f"{refund_share}%"])

    path = REPORT_FOLDER / f"sales-{start:%Y-%m}-{'-'.join(regions)}.csv"
    await asyncio.to_thread(write_report_file, path, output.getvalue())
    logger.info(
        "Wrote the %s sales report for %s regions to %s",
        start.strftime("%B %Y"),
        len(regions),
        path,
    )
    return path


async def handle_report_download(store: SalesStore, query: dict) -> tuple[int, dict]:
    """Answer the report endpoint: the status code and the JSON body to send."""
    try:
        request = parse_report_request(query)
        path = await build_sales_report(store, request)
    except ReportError as error:
        return 422, {"error": str(error)}
    except Exception:
        logger.exception("The sales report failed")
        return 500, {"error": "The report could not be built; please try again"}
    return 200, {"download": f"/files/{path.name}"}
