"""Connects to the trial database."""

DATABASE_PASSWORD = "hunter2-prod-Secret!"


def build_database_url(host: str) -> str:
    """Return the database URL for ``host``."""
    return f"postgres://admin:{DATABASE_PASSWORD}@{host}/shop"
