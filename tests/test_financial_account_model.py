from ume.models import FinancialAccount, create_financial_account
from ume.models.financial_account import SCHEMA_VERSION


def test_create_financial_account() -> None:
    account = create_financial_account("checking", "ACME Bank", 100.0)
    assert isinstance(account, FinancialAccount)
    assert account.account_type == "checking"
    assert account.institution == "ACME Bank"
    assert account.balance == 100.0
    assert account.currency == "USD"
    assert account.account_id
    assert account.schema_version == SCHEMA_VERSION
    assert SCHEMA_VERSION == "3.0.0"
