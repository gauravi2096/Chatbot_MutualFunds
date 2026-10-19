"""
Phase 1 — Document preparation: convert FundRecord into text chunks for embedding and retrieval.
"""

from typing import List, Tuple

from phase_0.schema import FundRecord, FIELD_DISPLAY_NAMES


# NAV of 0 is the old placeholder for "not available". A daily change of 0.0 is a real value
# (the NAV did not move) and is only N/A when it is missing (None).
_ZERO_MEANS_MISSING = ("nav",)


def record_to_text(record: FundRecord) -> str:
    """
    Convert one fund record to a single text chunk.
    Format: "Field Name: value" lines for RAG retrieval. A missing value is written as "N/A"
    (never blank, and never a placeholder 0.0 the model could quote as a real figure).
    """
    lines: List[str] = []
    for key, value in record.model_dump().items():
        if key == "scraped_at":
            continue
        missing = (
            value is None
            or (isinstance(value, str) and not value.strip())
            or (key in _ZERO_MEANS_MISSING and value == 0)
        )
        label = FIELD_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
        if missing:
            shown = "N/A"
        elif key == "daily_pct_change":
            shown = f"{value:.2f}%"  # 0.0 -> "0.00%", -0.2 -> "-0.20%"
        else:
            shown = value
        lines.append(f"{label}: {shown}")
    return "\n".join(lines)


def records_to_documents(records: List[FundRecord]) -> List[Tuple[str, dict]]:
    """
    Convert fund records to (text, metadata) for the vector store.
    metadata must include fund_id and source_url for the retriever.
    """
    out: List[Tuple[str, dict]] = []
    for r in records:
        text = record_to_text(r)
        if not text.strip():
            continue
        metadata = {
            "fund_id": r.fund_id,
            "source_url": str(r.source_url),
            "fund_name": r.fund_name,
        }
        out.append((text, metadata))
    return out
