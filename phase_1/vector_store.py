"""
Phase 1 — Vector store: store document embeddings in ChromaDB for similarity search.
"""

from typing import List, Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from phase_1.config import CHROMA_COLLECTION, CHROMA_DIR


def get_embedding_function():
    """Default embedding function (sentence-transformers)."""
    return SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")


class VectorStore:
    """ChromaDB-backed vector store for fund documents."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_function=None,
    ):
        self.persist_directory = persist_directory or str(CHROMA_DIR)
        self.collection_name = collection_name or CHROMA_COLLECTION
        self._ef = embedding_function or get_embedding_function()
        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._ef,
            metadata={"description": "INDmoney fund factual data"},
        )

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[dict],
        ids: Optional[List[str]] = None,
    ) -> None:
        """Add document chunks with metadata. IDs default to fund_id + index."""
        if ids is None:
            ids = [m.get("fund_id", str(i)) + f"_{i}" for i, m in enumerate(metadatas)]
        self._collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    def clear(self) -> None:
        """Remove all documents (re-build index)."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._ef,
            metadata={"description": "INDmoney fund factual data"},
        )

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> dict:
        """
        Run similarity search. Returns Chroma result dict with keys:
        ids, distances, metadatas, documents, embeddings (optional).
        """
        return self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
