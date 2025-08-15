"""Financial account node model and factory helpers."""

from __future__ import annotations

from dataclasses import dataclass
import uuid


SCHEMA_VERSION = "1.0"


@dataclass
class FinancialAccount:
    """Represents a financial account in the graph."""

    account_id: str
    account_type: str
    institution: str
    balance: float
    currency: str = "USD"
    schema_version: str = SCHEMA_VERSION


def create_financial_account(
    account_type: str,
    institution: str,
    balance: float,
    *,
    currency: str = "USD",
    account_id: str | None = None,
) -> FinancialAccount:
    """Factory helper to build :class:`FinancialAccount` instances."""

    return FinancialAccount(
        account_id=account_id or str(uuid.uuid4()),
        account_type=account_type,
        institution=institution,
        balance=balance,
        currency=currency,
        schema_version=SCHEMA_VERSION,
    )
