"""ChromaDB client — async wrapper around chromadb HTTP client."""
import uuid
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class ChromaClient:
    def __init__(self):
        self._client: Optional[chromadb.AsyncHttpClient] = None

    async def connect(self):
        host, port = self._parse_url(settings.CHROMA_URL)
        self._client = await chromadb.AsyncHttpClient(host=host, port=port)
        logger.info("ChromaDB connected", host=host, port=port)

    def _parse_url(self, url: str):
        url = url.replace("http://", "").replace("https://", "")
        parts = url.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 8001
        return host, port

    async def get_or_create_collection(self, name: str):
        return await self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    async def list_collections(self) -> List[str]:
        cols = await self._client.list_collections()
        return [c.name for c in cols]

    async def add_documents(
        self,
        collection_name: str,
        chunks: List[str],
        metadatas: List[Dict],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
    ):
        col = await self.get_or_create_collection(collection_name)
        kwargs = dict(documents=chunks, metadatas=metadatas, ids=ids)
        if embeddings:
            kwargs["embeddings"] = embeddings
        await col.add(**kwargs)

    async def query(
        self,
        collection_name: str,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict] = None,
        query_embeddings: Optional[List[List[float]]] = None,
    ) -> List[Dict]:
        col = await self.get_or_create_collection(collection_name)
        query_kwargs = dict(
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        # When documents were ingested with explicit (e.g. 1536-dim) embeddings,
        # the query must be embedded with the SAME model — passing query_texts
        # would make Chroma fall back to its 384-dim default and mismatch.
        if query_embeddings:
            query_kwargs["query_embeddings"] = query_embeddings
        else:
            query_kwargs["query_texts"] = query_texts
        results = await col.query(**query_kwargs)
        if not results.get("documents") or not results["documents"][0]:
            return []
        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            chunks.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "score": 1 - results["distances"][0][i],
                "id": results["ids"][0][i],
            })
        return chunks

    async def list_documents(self, collection_name: str) -> List[Dict]:
        try:
            col = await self.get_or_create_collection(collection_name)
            result = await col.get(include=["metadatas"])
            docs = []
            seen = set()
            for i, meta in enumerate(result["metadatas"]):
                doc_id = meta.get("doc_id", result["ids"][i])
                if doc_id not in seen:
                    seen.add(doc_id)
                    docs.append({"id": doc_id, "title": meta.get("title", ""), "source": meta.get("source", ""), "tags": meta.get("tags", "")})
            return docs
        except Exception:
            return []

    async def delete_document(self, collection_name: str, doc_id: str):
        col = await self.get_or_create_collection(collection_name)
        all_items = await col.get(where={"doc_id": doc_id})
        if all_items["ids"]:
            await col.delete(ids=all_items["ids"])


chroma_client = ChromaClient()
