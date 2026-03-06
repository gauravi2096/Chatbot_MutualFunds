"""
Phase 0 — Canonical data schema for INDmoney mutual fund records.

All supported factual data points for the RAG chatbot. Used by ingestion (Phase 1)
for validation and storage. Fields are optional to support partial scrapes;
validation rules can require specific fields per fund type.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class FundRecord(BaseModel):
    """
    Canonical schema for one mutual fund. All fields align with Phase 1 data points.
    Optional fields allow partial updates; required: fund_id, fund_name, source_url.
    """

    # Identity (required for retrieval and source link)
    fund_id: str = Field(..., description="Unique fund identifier, e.g. slug or numeric id from URL")
    fund_name: str = Field(..., description="Fund Name")
    source_url: HttpUrl = Field(..., description="INDmoney fund page URL (used as source link in responses)")

    # Valuation
    nav: Optional[float] = Field(None, description="NAV")
    nav_date: Optional[date] = Field(None, description="NAV Date")
    daily_pct_change: Optional[float] = Field(None, description="Daily % Change")

    # Size & cost
    aum: Optional[str] = Field(None, description="AUM (string to preserve formatting e.g. '₹1,234 Cr')")
    expense_ratio: Optional[str] = Field(None, description="Expense Ratio (e.g. '0.65%')")

    # Investment terms
    min_investment_lumpsum: Optional[str] = Field(None, description="Min Investment (Lumpsum)")
    min_investment_sip: Optional[str] = Field(None, description="Min Investment (SIP)")
    exit_load: Optional[str] = Field(None, description="Exit Load")
    elss_lock_in: Optional[str] = Field(None, description="ELSS Lock-in (e.g. '3 years' or N/A)")

    # Returns
    cagr_1y: Optional[str] = Field(None, description="1Y CAGR")
    cagr_3y: Optional[str] = Field(None, description="3Y CAGR")
    cagr_5y: Optional[str] = Field(None, description="5Y CAGR")
    since_inception: Optional[str] = Field(None, description="Since Inception")

    # Allocation
    equity_pct: Optional[str] = Field(None, description="Equity %")
    debt_cash_pct: Optional[str] = Field(None, description="Debt + Cash %")
    market_cap_split: Optional[str] = Field(None, description="Market Cap Split")

    # Holdings & risk
    top_holdings: Optional[str] = Field(None, description="Top Holdings (summary or list)")
    risk_level: Optional[str] = Field(None, description="Risk Level")

    # Reference
    benchmark: Optional[str] = Field(None, description="Benchmark")

    # Metadata (set by ingestion, not scraped)
    scraped_at: Optional[str] = Field(None, description="ISO timestamp when record was scraped")

    model_config = {"str_strip_whitespace": True, "extra": "forbid"}


# Display names for each field (for RAG chunks / UI labels)
FIELD_DISPLAY_NAMES = {
    "fund_id": "Fund ID",
    "fund_name": "Fund Name",
    "source_url": "Source URL",
    "nav": "NAV",
    "nav_date": "NAV Date",
    "daily_pct_change": "Daily % Change",
    "aum": "AUM",
    "expense_ratio": "Expense Ratio",
    "min_investment_lumpsum": "Min Investment (Lumpsum)",
    "min_investment_sip": "Min Investment (SIP)",
    "exit_load": "Exit Load",
    "elss_lock_in": "ELSS Lock-in",
    "cagr_1y": "1Y CAGR",
    "cagr_3y": "3Y CAGR",
    "cagr_5y": "5Y CAGR",
    "since_inception": "Since Inception",
    "equity_pct": "Equity %",
    "debt_cash_pct": "Debt + Cash %",
    "market_cap_split": "Market Cap Split",
    "top_holdings": "Top Holdings",
    "risk_level": "Risk Level",
    "benchmark": "Benchmark",
}
