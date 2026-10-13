"""RAG Pipeline — chunk, embed, retrieve, generate."""
import uuid
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.core.config import settings
from app.rag.chroma_client import chroma_client

logger = structlog.get_logger()

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


class RAGPipeline:
    """Full RAG: Chunk → Embed → Store → Retrieve → Generate."""

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + CHUNK_SIZE])
            chunks.append(chunk)
            i += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks or [text]

    async def ingest(self, collection: str, content: str, metadata: Dict) -> str:
        """Chunk content and store in ChromaDB."""
        doc_id = str(uuid.uuid4())
        chunks = self._chunk_text(content)

        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{**metadata, "doc_id": doc_id, "chunk_index": i, "tags": ",".join(metadata.get("tags", []))} for i in range(len(chunks))]

        # Try to get embeddings; fall back to ChromaDB default embedding
        embeddings = await self._embed(chunks)

        await chroma_client.add_documents(
            collection_name=collection,
            chunks=chunks,
            metadatas=metadatas,
            ids=chunk_ids,
            embeddings=embeddings,
        )
        logger.info("Document ingested", doc_id=doc_id, chunks=len(chunks), collection=collection)
        return doc_id

    async def retrieve(self, collection: str, query: str, top_k: int = 5) -> List[Dict]:
        """Semantic search in ChromaDB.

        Embed the query with the same model used at ingest time so the vector
        dimensions match (falls back to Chroma's default embedder otherwise).
        """
        query_embeddings = await self._embed([query])
        return await chroma_client.query(
            collection, [query], n_results=top_k, query_embeddings=query_embeddings,
        )

    async def generate(self, query: str, chunks: List[Dict]) -> str:
        """Generate answer using retrieved context (RAG)."""
        context = "\n\n---\n\n".join([c["text"] for c in chunks[:5]])
        system = """Bạn là Nexus — AI assistant của Smart Factory.
Dựa trên CONTEXT bên dưới để trả lời câu hỏi của người dùng.
Nếu không tìm thấy câu trả lời trong context, hãy nói rõ là không có thông tin.
Trả lời ngắn gọn, chính xác."""

        user = f"""CONTEXT:
{context}

QUESTION: {query}

Answer:"""

        return await self._llm_complete(system, user)

    async def _embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Get embeddings from OpenRouter — returns None if not available (ChromaDB will use default)."""
        if not settings.OPENROUTER_API_KEY or settings.OPENROUTER_API_KEY.startswith("your_"):
            return None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/embeddings",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                    json={"model": "openai/text-embedding-3-small", "input": texts},
                )
                if r.status_code == 200:
                    data = r.json()
                    return [item["embedding"] for item in data["data"]]
        except Exception as e:
            logger.warning("Embedding failed, using ChromaDB default", error=str(e))
        return None

    async def _llm_complete(self, system: str, user: str) -> str:
        if settings.OPENROUTER_API_KEY and not settings.OPENROUTER_API_KEY.startswith("your_"):
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "HTTP-Referer": "http://localhost:8080",
                        "X-Title": "smart-factory-kbs",
                    },
                    json={
                        "model": settings.OPENROUTER_MODEL,
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                        "temperature": 0.2,
                        "max_tokens": 1024,
                    },
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        return "[KBS Mock] Cấu hình OPENROUTER_API_KEY để dùng RAG generation thực sự."
