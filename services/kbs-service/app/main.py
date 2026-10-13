"""
KBS Service — Knowledge Base System with RAG
Uses ChromaDB for vector storage + OpenRouter for embeddings/generation.
"""
import uuid
from contextlib import asynccontextmanager
from typing import List

import structlog
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import settings
from app.rag.chroma_client import chroma_client
from app.rag.pipeline import RAGPipeline

logger = structlog.get_logger()
rag = RAGPipeline()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("📚 KBS Service starting...")
    await chroma_client.connect()
    logger.info("✅ KBS Service ready", chroma_url=settings.CHROMA_URL)
    yield
    logger.info("🛑 KBS shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="KBS — Knowledge Base System",
        description="RAG-powered Knowledge Base for Smart Factory / Nexus",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Upload document ──────────────────────────────────────────────
    @app.post("/api/v1/documents", tags=["documents"])
    async def upload_document(
        file: UploadFile = File(None),
        text: str = Form(None),
        title: str = Form("Untitled"),
        collection: str = Form("nexus-kb"),
        tags: str = Form(""),
    ):
        """Ingest document into KBS (file upload or raw text)."""
        if file:
            content = (await file.read()).decode("utf-8", errors="replace")
            source = file.filename
        elif text:
            content = text
            source = "manual-input"
        else:
            raise HTTPException(400, "Provide file or text")

        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        doc_id = await rag.ingest(
            collection=collection,
            content=content,
            metadata={"title": title, "source": source, "tags": tag_list},
        )
        return {"success": True, "document_id": doc_id, "collection": collection}

    # ── List documents ───────────────────────────────────────────────
    @app.get("/api/v1/documents", tags=["documents"])
    async def list_documents(collection: str = "nexus-kb"):
        docs = await chroma_client.list_documents(collection)
        return {"data": docs, "total": len(docs)}

    # ── Delete document ──────────────────────────────────────────────
    @app.delete("/api/v1/documents/{doc_id}", tags=["documents"])
    async def delete_document(doc_id: str, collection: str = "nexus-kb"):
        await chroma_client.delete_document(collection, doc_id)
        return {"success": True}

    # ── RAG Query ────────────────────────────────────────────────────
    class QueryRequest(BaseModel):
        query: str
        collection: str = "nexus-kb"
        top_k: int = 5
        with_answer: bool = True

    @app.post("/api/v1/query", tags=["rag"])
    async def rag_query(body: QueryRequest):
        """Retrieve relevant chunks and optionally generate an answer."""
        chunks = await rag.retrieve(body.collection, body.query, body.top_k)
        result = {"query": body.query, "chunks": chunks}
        if body.with_answer:
            answer = await rag.generate(body.query, chunks)
            result["answer"] = answer
        return result

    # ── Collections ──────────────────────────────────────────────────
    @app.get("/api/v1/collections", tags=["collections"])
    async def list_collections():
        cols = await chroma_client.list_collections()
        return {"collections": cols}

    @app.post("/api/v1/collections", tags=["collections"])
    async def create_collection(name: str = Form(...)):
        await chroma_client.get_or_create_collection(name)
        return {"success": True, "name": name}

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "healthy", "service": "kbs-service"}

    return app


app = create_app()
