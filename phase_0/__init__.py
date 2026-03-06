"""
Phase 0 — Foundation & Data Contract.

Provides: canonical schema (FundRecord), source registry, and update timestamp rules.
"""

from phase_0.schema import FIELD_DISPLAY_NAMES, FundRecord
from phase_0.source_registry import (  # noqa: I001
    BASE_URL,
    PHASE_1_SOURCES,
    SourceRegistry,
    RegisteredSource,
    get_default_registry,
    get_all_urls,
    get_source_by_fund_id,
    load_registry,
    save_registry,
)
from phase_0.update_timestamp import (
    DEFAULT_TZ,
    LAST_UPDATE_DATETIME_FMT,
    format_last_update,
    parse_last_update,
)

__all__ = [
    "FundRecord",
    "FIELD_DISPLAY_NAMES",
    "BASE_URL",
    "PHASE_1_SOURCES",
    "SourceRegistry",
    "RegisteredSource",
    "get_default_registry",
    "get_all_urls",
    "get_source_by_fund_id",
    "load_registry",
    "save_registry",
    "DEFAULT_TZ",
    "LAST_UPDATE_DATETIME_FMT",
    "format_last_update",
    "parse_last_update",
]
