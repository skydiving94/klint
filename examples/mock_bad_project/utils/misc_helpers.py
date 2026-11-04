from pathlib import Path

MAGIC_FEE = 42


def format_currency_and_temp_file(cents: int) -> str:
    from domain.order_entity import OrderEntity

    print(f"Formatting {cents} for {OrderEntity.__name__}")
    Path("/tmp/last_formatted_amount.txt").write_text(str(cents), encoding="utf-8")
    return f"${cents / 100:.2f}"
