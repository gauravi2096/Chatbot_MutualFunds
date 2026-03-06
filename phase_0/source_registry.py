"""
Phase 0 — Source registry: Phase 1 INDmoney fund pages with fund identifier
and last-successful-update timestamp.

Used by ingestion to know which URLs to scrape and by the chatbot to attach
the correct source link. Last update timestamp is set after a successful
ingestion run (Phase 4 scheduler will automate daily runs).
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

BASE_URL = "https://www.indmoney.com/mutual-funds"

# Phase 1 fund slugs and display names (from ARCHITECTURE.md)
PHASE_1_SOURCES = [
    ("hdfc-infrastructure-fund-direct-plan-growth-option-3315", "HDFC Infrastructure Fund"),
    ("hdfc-mid-cap-fund-direct-plan-growth-option-3097", "HDFC Mid Cap Fund"),
    ("hdfc-small-cap-fund-direct-growth-option-3580", "HDFC Small Cap Fund"),
    ("hdfc-flexi-cap-fund-direct-plan-growth-option-3184", "HDFC Flexi Cap Fund"),
    ("hdfc-value-fund-direct-plan-growth-option-3623", "HDFC Value Fund"),
    ("hdfc-dynamic-debt-plan-direct-plan-growth-option-513", "HDFC Dynamic Debt Fund"),
    ("hdfc-low-duration-direct-plan-growth-option-1481", "HDFC Low Duration"),
    ("hdfc-gold-etf-fund-of-fund-direct-plan-growth-5359", "HDFC Gold ETF FoF"),
    ("hdfc-hybrid-equity-fund-direct-growth-option-4103", "HDFC Hybrid Equity Fund"),
    ("hdfc-equity-savings-fund-direct-plan-growth-option-4569", "HDFC Equity Savings Fund"),
]


class RegisteredSource(BaseModel):
    """One entry in the source registry."""

    fund_id: str = Field(..., description="Unique fund identifier (slug from URL)")
    fund_name: str = Field(..., description="Display name of the fund")
    url: HttpUrl = Field(..., description="Full INDmoney fund page URL")
    last_successful_update: Optional[str] = Field(
        None,
        description="Timestamp of last successful ingestion (12-hour format with am/pm)",
    )


class SourceRegistry(BaseModel):
    """Registry of all Phase 1 sources and optional last-update timestamp."""

    sources: list[RegisteredSource] = Field(default_factory=list)
    last_data_update: Optional[str] = Field(
        None,
        description="Single 'last data update' value (date + 12-hour time, am/pm) for chatbot responses",
    )


def get_default_registry() -> SourceRegistry:
    """Build the default Phase 1 source registry with full URLs."""
    sources = [
        RegisteredSource(
            fund_id=slug,
            fund_name=name,
            url=f"{BASE_URL}/{slug}",
        )
        for slug, name in PHASE_1_SOURCES
    ]
    return SourceRegistry(sources=sources)


def load_registry(path: Path) -> SourceRegistry:
    """Load registry from JSON file. Creates default if file does not exist."""
    if not path.exists():
        return get_default_registry()
    return SourceRegistry.model_validate_json(path.read_text(encoding="utf-8"))


def save_registry(registry: SourceRegistry, path: Path) -> None:
    """Persist registry to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry.model_dump_json(indent=2), encoding="utf-8")


def get_source_by_fund_id(registry: SourceRegistry, fund_id: str) -> Optional[RegisteredSource]:
    """Return the registered source for a fund_id, or None."""
    for s in registry.sources:
        if s.fund_id == fund_id:
            return s
    return None


def get_all_urls(registry: SourceRegistry) -> list[str]:
    """Return all Phase 1 URLs as strings (for scraper)."""
    return [str(s.url) for s in registry.sources]
