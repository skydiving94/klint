"""Imports the product catalogue a merchant uploads as CSV."""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Protocol

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 5_000_000
MAX_ROWS = 20_000
REQUIRED_COLUMNS = ("sku", "title", "price", "currency", "stock", "category")
OPTIONAL_COLUMNS = ("description", "barcode", "weight_grams", "tags", "is_active")
SKU_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{2,31}$")
BARCODE_PATTERN = re.compile(r"^\d{8}(\d{4,6})?$")
CURRENCIES = {"EUR", "USD", "GBP", "CHF", "SEK"}
MAX_TITLE_LENGTH = 140
MAX_DESCRIPTION_LENGTH = 5_000
MAX_TAGS = 12


class CatalogueStore(Protocol):
    """The product tables, behind the database the app wires in."""

    async def list_categories(self, merchant_id: int) -> dict[str, int]: ...

    async def find_products(
        self, merchant_id: int, skus: Sequence[str]
    ) -> dict[str, dict]: ...

    async def insert_products(self, merchant_id: int, rows: Sequence[dict]) -> int: ...

    async def update_products(self, merchant_id: int, rows: Sequence[dict]) -> int: ...

    async def find_barcodes(self, barcodes: Sequence[str]) -> dict[str, str]: ...


class ImportError_(Exception):
    """The upload could not be imported at all; the message is safe to show."""


@dataclass
class RowProblem:
    line: int
    column: str
    message: str


@dataclass
class ImportReport:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    problems: list[RowProblem] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not self.problems


def read_upload(content: bytes) -> list[dict[str, str]]:
    """Return the rows of an uploaded CSV, its header checked.

    Raises ImportError_ when the upload is too large, is not UTF-8 text, or
    lacks a required column.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImportError_(f"Upload at most {MAX_UPLOAD_BYTES // 1_000_000} MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportError_("The file is not UTF-8 text") from None
    reader = csv.DictReader(io.StringIO(text))
    header = [column.strip().lower() for column in reader.fieldnames or []]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise ImportError_(f"Missing columns: {', '.join(missing)}")
    unknown = [
        column
        for column in header
        if column not in REQUIRED_COLUMNS and column not in OPTIONAL_COLUMNS
    ]
    if unknown:
        raise ImportError_(f"Unknown columns: {', '.join(unknown)}")
    rows = []
    for row in reader:
        rows.append({key.strip().lower(): (value or "").strip() for key, value in row.items()})
        if len(rows) > MAX_ROWS:
            raise ImportError_(f"Upload at most {MAX_ROWS} rows at a time")
    return rows


def check_catalogue_row(
    row: dict[str, str],
    line: int,
    category_name_to_id: dict[str, int],
    seen_skus: dict[str, int],
) -> tuple[list[RowProblem], dict | None]:
    """Check each field of one uploaded row; return its problems and the product.

    The product is None when the row has a problem. ``seen_skus`` gives the
    line of each SKU of the rows before; the row's SKU is added to it.
    """
    problems: list[RowProblem] = []
    sku = row["sku"].upper()
    if not SKU_PATTERN.match(sku):
        problems.append(
            RowProblem(line, "sku", "Use 3 to 32 capital letters, digits and dashes")
        )
    elif sku in seen_skus:
        problems.append(
            RowProblem(line, "sku", f"Also on line {seen_skus[sku]}")
        )
    else:
        seen_skus[sku] = line

    title = " ".join(row["title"].split())
    if not title:
        problems.append(RowProblem(line, "title", "Give a title"))
    elif len(title) > MAX_TITLE_LENGTH:
        problems.append(
            RowProblem(line, "title", f"Use at most {MAX_TITLE_LENGTH} characters")
        )

    try:
        price = Decimal(row["price"].replace(",", "."))
    except InvalidOperation:
        price = None
        problems.append(RowProblem(line, "price", "Give a number"))
    if price is not None:
        if price <= 0:
            problems.append(RowProblem(line, "price", "Give a price above 0"))
        elif price.as_tuple().exponent < -2:
            problems.append(
                RowProblem(line, "price", "Use at most 2 decimal places")
            )

    currency = row["currency"].upper()
    if currency not in CURRENCIES:
        problems.append(
            RowProblem(line, "currency", f"Use one of {', '.join(sorted(CURRENCIES))}")
        )

    stock_text = row["stock"]
    if not stock_text.isdigit():
        problems.append(
            RowProblem(line, "stock", "Give a whole number of 0 or more")
        )
        stock = 0
    else:
        stock = int(stock_text)

    category_id = category_name_to_id.get(row["category"].lower())
    if category_id is None:
        problems.append(
            RowProblem(line, "category", "Use a category your shop has")
        )

    description = row.get("description", "")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        problems.append(
            RowProblem(
                line,
                "description",
                f"Use at most {MAX_DESCRIPTION_LENGTH} characters",
            )
        )

    barcode = row.get("barcode", "")
    if barcode and not BARCODE_PATTERN.match(barcode):
        problems.append(
            RowProblem(line, "barcode", "Give an EAN-8, EAN-13 or GTIN-14")
        )

    weight_text = row.get("weight_grams", "")
    weight_grams = None
    if weight_text:
        if not weight_text.isdigit() or not 1 <= int(weight_text) <= 70_000:
            problems.append(
                RowProblem(line, "weight_grams", "Give 1 to 70000 grams")
            )
        else:
            weight_grams = int(weight_text)

    tags = sorted(
        {tag.strip().lower() for tag in row.get("tags", "").split("|") if tag.strip()}
    )
    if len(tags) > MAX_TAGS:
        problems.append(
            RowProblem(line, "tags", f"Use at most {MAX_TAGS} tags")
        )

    is_active_text = row.get("is_active", "yes").lower()
    if is_active_text not in {"yes", "no", ""}:
        problems.append(RowProblem(line, "is_active", "Use yes or no"))

    if problems:
        return problems, None
    return problems, {
        "sku": sku,
        "title": title,
        "price": str(price),
        "currency": currency,
        "stock": stock,
        "category_id": category_id,
        "description": description,
        "barcode": barcode or None,
        "weight_grams": weight_grams,
        "tags": tags,
        "is_active": is_active_text != "no",
    }


async def import_catalogue(
    store: CatalogueStore, merchant_id: int, content: bytes
) -> ImportReport:
    """Store the valid rows of an uploaded catalogue; report the problems of the others.

    A SKU already in the catalogue is updated when a field changed. The
    categories, the existing products and the barcodes in use are read in
    one query each, and the new and the changed products written in one
    query each.
    """
    rows = await asyncio.to_thread(read_upload, content)
    report = ImportReport()
    category_name_to_id = await store.list_categories(merchant_id)

    checked_rows: list[tuple[int, dict]] = []
    seen_skus: dict[str, int] = {}
    for index, row in enumerate(rows):
        line = index + 2
        problems, product = check_catalogue_row(
            row, line, category_name_to_id, seen_skus
        )
        report.problems.extend(problems)
        if product is not None:
            checked_rows.append((line, product))

    barcodes = [row["barcode"] for _, row in checked_rows if row["barcode"]]
    barcode_to_sku = await store.find_barcodes(barcodes) if barcodes else {}
    kept_rows: list[dict] = []
    for line, row in checked_rows:
        owner = barcode_to_sku.get(row["barcode"]) if row["barcode"] else None
        if owner is not None and owner != row["sku"]:
            report.problems.append(
                RowProblem(line, "barcode", f"Already used by product {owner}")
            )
            continue
        kept_rows.append(row)

    sku_to_existing = await store.find_products(
        merchant_id, [row["sku"] for row in kept_rows]
    )
    new_rows = [row for row in kept_rows if row["sku"] not in sku_to_existing]
    changed_rows = []
    for row in kept_rows:
        existing = sku_to_existing.get(row["sku"])
        if existing is None:
            continue
        if any(existing.get(key) != value for key, value in row.items()):
            changed_rows.append(row)
        else:
            report.unchanged += 1

    if new_rows:
        report.inserted = await store.insert_products(merchant_id, new_rows)
    if changed_rows:
        report.updated = await store.update_products(merchant_id, changed_rows)
    logger.info(
        "Merchant %s imported %s rows: %s new, %s changed, %s problems",
        merchant_id,
        len(rows),
        report.inserted,
        report.updated,
        len(report.problems),
    )
    return report


def format_problems(report: ImportReport, limit: int = 50) -> list[str]:
    """Return the first ``limit`` problems as lines to show the merchant."""
    lines = [
        f"Line {problem.line}, {problem.column}: {problem.message}"
        for problem in sorted(report.problems, key=lambda problem: problem.line)[:limit]
    ]
    hidden = len(report.problems) - limit
    if hidden > 0:
        lines.append(f"... and {hidden} more")
    return lines


async def handle_catalogue_upload(
    store: CatalogueStore, merchant_id: int, content: bytes
) -> tuple[int, dict]:
    """Answer the upload endpoint: the status code and the JSON body to send."""
    try:
        report = await import_catalogue(store, merchant_id, content)
    except ImportError_ as error:
        return 422, {"error": str(error)}
    except Exception:
        logger.exception("Catalogue import failed for merchant %s", merchant_id)
        return 500, {"error": "The upload could not be imported; please try again"}
    return 200, {
        "inserted": report.inserted,
        "updated": report.updated,
        "unchanged": report.unchanged,
        "problems": format_problems(report),
    }
