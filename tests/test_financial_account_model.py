from ume.models import FinancialAccount, create_financial_account


def test_create_financial_account() -> None:
    account = create_financial_account("checking", "ACME Bank", 100.0)
    assert isinstance(account, FinancialAccount)
    assert account.account_type == "checking"
    assert account.institution == "ACME Bank"
    assert account.balance == 100.0
    assert account.currency == "USD"
    assert account.account_id
