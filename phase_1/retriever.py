"""
Phase 1 — Retriever: given a user query, return top-k chunks with source URL
and last data update timestamp.
"""

from typing import List, Optional

from phase_1.config import REGISTRY_PATH, TOP_K
from phase_1.vector_store import VectorStore
from phase_0.source_registry import load_registry
from phase_0.update_timestamp import format_last_update


class Retriever:
    """RAG retriever: vector search + registry for source URL and last update."""

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        registry_path=None,
        top_k: int = TOP_K,
    ):
        from pathlib import Path
        self._store = vector_store or VectorStore()
        self._registry_path = Path(registry_path or REGISTRY_PATH)
        self._top_k = top_k

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        fund_id: Optional[str] = None,
    ) -> dict:
        """
        Run retrieval for the query. Returns dict with:
          - chunks: list of { "text", "source_url", "fund_id", "fund_name" }
          - source_url: primary source URL (first result's URL for the one link in response)
          - last_data_update: timestamp string (date + 12h am/pm)
        If fund_id is set, only chunks for that fund are returned (scoped conversation).
        """
        k = top_k or self._top_k
        where = {"fund_id": fund_id} if (fund_id and fund_id.strip()) else None
        # When filtering by fund, one document per fund so request enough for that one fund
        n_results = k if not where else max(k, 1)
        result = self._store.query(query_text=query, n_results=n_results, where=where)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        registry = load_registry(self._registry_path)
        last_data_update = registry.last_data_update or format_last_update()

        chunks: List[dict] = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            if not meta:
                meta = {}
            chunks.append({
                "text": doc or "",
                "source_url": meta.get("source_url", ""),
                "fund_id": meta.get("fund_id", ""),
                "fund_name": meta.get("fund_name", ""),
                "distance": distances[i] if i < len(distances) else None,
            })

        # Primary source link: first chunk's URL (per architecture: one clickable source link)
        source_url = chunks[0]["source_url"] if chunks else ""

        return {
            "chunks": chunks,
            "source_url": source_url,
            "last_data_update": last_data_update,
        }
