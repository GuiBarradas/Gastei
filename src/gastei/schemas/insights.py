"""DTOs for insight aggregations."""

from pydantic import BaseModel, Field


class CategorySpending(BaseModel):
    category: str
    label: str | None = None
    amount: float = Field(description="Absolute amount spent in the period (always positive)")
    transaction_count: int


class MonthlySummary(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    income: float = Field(description="Total income in the month (positive)")
    expense: float = Field(description="Total expense in the month (positive)")
    net: float = Field(description="income - expense")


class MerchantSpending(BaseModel):
    merchant: str
    amount: float = Field(description="Absolute amount spent (always positive)")
    transaction_count: int


class AccountBalance(BaseModel):
    account_id: str
    name: str
    type: str
    balance: float
    currency_code: str = "BRL"


class BankBalance(BaseModel):
    """Aggregated balance per bank (all accounts and credit cards combined)."""

    bank_name: str
    institution_id: str
    account_count: int
    total_balance: float
    currency_code: str = "BRL"


class DashboardSummary(BaseModel):
    total_balance: float
    accounts: list[AccountBalance]
    spending_by_category: list[CategorySpending]
    top_merchants: list[MerchantSpending]
    monthly: list[MonthlySummary]
