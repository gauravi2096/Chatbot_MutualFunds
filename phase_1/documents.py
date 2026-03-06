"""
Phase 1 — Document preparation: convert FundRecord into text chunks for embedding and retrieval.
"""

from typing import List, Tuple

from phase_0.schema import FundRecord, FIELD_DISPLAY_NAMES


def record_to_text(record: FundRecord) -> str:
    """
    Convert one fund record to a single text chunk (all non-empty fields).
    Format: "Field Name: value" lines for RAG retrieval.
    """
    lines: List[str] = []
    d = record.model_dump()
    for key, value in d.items():
        if key in ("scraped_at",) or value is None or value == "":
            continue
        label = FIELD_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
        if isinstance(value, float):
            lines.append(f"{label}: {value}")
        else:
            lines.append(f"{label}: {value}")
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
