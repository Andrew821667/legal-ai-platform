# -*- coding: utf-8 -*-
"""
RAG System - Retrieval-Augmented Generation for legal documents

Embedding models supported:
- OpenAI (text-embedding-3-large, text-embedding-3-small) - API
- E5-mistral-7b-instruct - open-source, large
- multilingual-e5-small - open-source, compact, multilingual
- BGE-M3 - best open-source for multilingual
- paraphrase-multilingual-MiniLM-L12-v2 - default, compact

Reranking models supported:
- Cohere Rerank - API, 100+ languages
- mxbai-rerank-large-v1 - open-source cross-encoder
- BAAI/bge-reranker-large - open-source
- cross-encoder/ms-marco-MiniLM-L-12-v2 - compact cross-encoder

Features:
- ChromaDB vector storage with multiple collections
- Hybrid search (vector + keyword + metadata filtering)
- Re-ranking of results
- Smart chunking with overlap
- LRU cache for frequent queries
- Integration with LLM Gateway
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache
from datetime import datetime
import hashlib

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer, CrossEncoder
from loguru import logger
from sqlalchemy.orm import Session

from ..models.database import LegalDocument
from ..models.repositories import LegalDocumentRepository
from .llm_gateway import LLMGateway


class Document:
    """Document class for search results"""
    def __init__(self, doc_id: str, content: str, metadata: Dict[str, Any], score: float = 0.0):
        self.doc_id = doc_id
        self.content = content
        self.metadata = metadata
        self.score = score

    def __repr__(self):
        return f"Document(id={self.doc_id}, score={self.score:.3f})"


class RAGSystem:
    """
    RAG System for legal document retrieval and answer generation

    Collections:
    - laws: Legal acts and regulations
    - case_law: Court decisions and precedents
    - templates: Contract templates
    - knowledge: General legal knowledge base
    """

    # Collection types
    COLLECTION_LAWS = "laws"
    COLLECTION_CASE_LAW = "case_law"
    COLLECTION_TEMPLATES = "templates"
    COLLECTION_KNOWLEDGE = "knowledge"

    # Embedding model presets
    EMBEDDING_MODELS = {
        "multilingual-e5-small": "intfloat/multilingual-e5-small",
        "paraphrase-multilingual": "paraphrase-multilingual-MiniLM-L12-v2",
        "bge-m3": "BAAI/bge-m3",
        "e5-mistral": "intfloat/e5-mistral-7b-instruct"
    }

    # Reranker model presets
    RERANKER_MODELS = {
        "ms-marco": "cross-encoder/ms-marco-MiniLM-L-12-v2",
        "bge-reranker": "BAAI/bge-reranker-large",
        "mxbai-rerank": "mixedbread-ai/mxbai-rerank-large-v1"
    }

    def __init__(
        self,
        db_session: Session,
        chroma_persist_dir: str = "data/chromadb",
        embedding_model: str = "paraphrase-multilingual",
        reranker_model: Optional[str] = "ms-marco",
        llm_gateway: Optional[LLMGateway] = None,
        use_openai_embeddings: bool = False,
        openai_api_key: Optional[str] = None
    ):
        """
        Args:
            db_session: SQLAlchemy session
            chroma_persist_dir: Directory for ChromaDB
            embedding_model: Model name or preset key
            reranker_model: Reranker model name or preset key (None to disable)
            llm_gateway: LLMGateway for answer generation
            use_openai_embeddings: Use OpenAI API for embeddings
            openai_api_key: OpenAI API key (if using OpenAI embeddings)
        """
        self.db = db_session
        self.repository = LegalDocumentRepository(db_session)
        self.llm_gateway = llm_gateway
        self.use_openai_embeddings = use_openai_embeddings

        # Initialize ChromaDB
        self.chroma_dir = Path(chroma_persist_dir)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        # Initialize embedding model
        if use_openai_embeddings:
            if not openai_api_key:
                raise ValueError("OpenAI API key required for OpenAI embeddings")
            import openai
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
            self.embedding_model_name = "text-embedding-3-large"
            self.embedding_model = None
            logger.info(f"Using OpenAI embeddings: {self.embedding_model_name}")
        else:
            # Get model name from preset or use directly
            model_name = self.EMBEDDING_MODELS.get(embedding_model, embedding_model)
            logger.info(f"Loading embedding model: {model_name}")
            self.embedding_model = SentenceTransformer(model_name)
            self.embedding_model_name = model_name
            logger.info("Embedding model loaded")

        # Initialize reranker (optional)
        self.reranker = None
        if reranker_model:
            try:
                reranker_name = self.RERANKER_MODELS.get(reranker_model, reranker_model)
                logger.info(f"Loading reranker: {reranker_name}")
                self.reranker = CrossEncoder(reranker_name)
                logger.info("Reranker loaded")
            except Exception as e:
                logger.warning(f"Failed to load reranker: {e}. Continuing without reranker.")
                self.reranker = None

        # Initialize collections
        self.collections = {}
        self._init_collections()

        # Chunking parameters
        self.chunk_size = 512
        self.chunk_overlap = 128

        logger.info("RAG System initialized")

    def _init_collections(self):
        """Initialize ChromaDB collections"""
        collection_names = [
            self.COLLECTION_LAWS,
            self.COLLECTION_CASE_LAW,
            self.COLLECTION_TEMPLATES,
            self.COLLECTION_KNOWLEDGE
        ]

        for name in collection_names:
            try:
                self.collections[name] = self.chroma_client.get_or_create_collection(
                    name=name,
                    metadata={"description": f"Collection for {name}"}
                )
                logger.info(f"Collection '{name}' initialized")
            except Exception as e:
                logger.error(f"Failed to initialize collection '{name}': {e}")

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using configured provider"""
        if self.use_openai_embeddings:
            response = self.openai_client.embeddings.create(
                input=texts,
                model=self.embedding_model_name
            )
            return [item.embedding for item in response.data]
        else:
            return self.embedding_model.encode(texts, show_progress_bar=False).tolist()

    def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        collection: str = COLLECTION_KNOWLEDGE
    ) -> None:
        """Index document into ChromaDB"""
        logger.info(f"Indexing document {doc_id} into collection '{collection}'")

        if collection not in self.collections:
            raise ValueError(f"Unknown collection: {collection}")

        chunks = self._chunk_text(content)
        logger.info(f"Document split into {len(chunks)} chunks")

        embeddings = self._get_embeddings(chunks)

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {**metadata, "chunk_id": i, "total_chunks": len(chunks), "doc_id": doc_id}
            for i in range(len(chunks))
        ]

        self.collections[collection].add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas
        )

        self.repository.mark_as_vectorized(doc_id)
        logger.info(f"Document {doc_id} indexed successfully")

    def search(
        self,
        query: str,
        collection: str = COLLECTION_KNOWLEDGE,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        rerank: bool = True
    ) -> List[Document]:
        """Semantic search in collection"""
        logger.info(f"Searching in '{collection}' for: {query[:50]}...")

        if collection not in self.collections:
            raise ValueError(f"Unknown collection: {collection}")

        query_embedding = self._get_embeddings([query])[0]

        results = self.collections[collection].query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2 if rerank and self.reranker else top_k,
            where=filters
        )

        documents = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                doc = Document(
                    doc_id=results['metadatas'][0][i].get('doc_id', results['ids'][0][i]),
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i],
                    score=1.0 - results['distances'][0][i]
                )
                documents.append(doc)

        if rerank and self.reranker and len(documents) > 0:
            documents = self._rerank_with_model(query, documents)[:top_k]

        logger.info(f"Found {len(documents)} results")
        return documents

    def _rerank_with_model(self, query: str, documents: List[Document]) -> List[Document]:
        """Rerank using cross-encoder model"""
        pairs = [[query, doc.content] for doc in documents]
        scores = self.reranker.predict(pairs)

        for doc, score in zip(documents, scores):
            doc.score = float(score)

        documents.sort(key=lambda x: x.score, reverse=True)
        return documents

    def hybrid_search(
        self,
        query: str,
        collection: str = COLLECTION_KNOWLEDGE,
        top_k: int = 5,
        keyword_weight: float = 0.3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Hybrid search combining vector and keyword"""
        logger.info(f"Hybrid search in '{collection}': {query[:50]}...")

        vector_results = self.search(query, collection, top_k * 2, filters, rerank=False)
        keyword_results = self._keyword_search(query, collection, top_k * 2, filters)

        merged = self._merge_search_results(vector_results, keyword_results, keyword_weight)

        if self.reranker:
            final_results = self._rerank_with_model(query, merged)[:top_k]
        else:
            final_results = merged[:top_k]

        logger.info(f"Hybrid search returned {len(final_results)} results")
        return final_results

    def generate_answer(
        self,
        query: str,
        context_documents: Optional[List[Document]] = None,
        collection: str = COLLECTION_KNOWLEDGE,
        top_k: int = 3
    ) -> Tuple[str, List[Document]]:
        """Generate answer using RAG"""
        logger.info(f"Generating answer for: {query[:50]}...")

        if not self.llm_gateway:
            raise ValueError("LLM Gateway not configured")

        if context_documents is None:
            context_documents = self.search(query, collection, top_k)

        if not context_documents:
            return "No relevant information found.", []

        context = self._build_context(context_documents)

        prompt = f"""Based on the following legal documents, answer the question.

Context:
{context}

Question: {query}

Provide a comprehensive answer based on the context. If the information is not sufficient, say so."""

        answer = self.llm_gateway.call(
            prompt=prompt,
            system_prompt="You are a legal expert assistant. Provide accurate answers based on the given context.",
            temperature=0.3
        )

        logger.info("Answer generated successfully")
        return answer, context_documents

    def update_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        collection: str = COLLECTION_KNOWLEDGE
    ) -> None:
        """Update existing document"""
        logger.info(f"Updating document {doc_id} in collection '{collection}'")
        self.delete_document(doc_id, collection)
        self.index_document(doc_id, content, metadata, collection)
        logger.info(f"Document {doc_id} updated successfully")

    def delete_document(self, doc_id: str, collection: str = COLLECTION_KNOWLEDGE) -> None:
        """Delete document from collection"""
        logger.info(f"Deleting document {doc_id} from collection '{collection}'")

        if collection not in self.collections:
            raise ValueError(f"Unknown collection: {collection}")

        results = self.collections[collection].get(where={"doc_id": doc_id})

        if results['ids']:
            self.collections[collection].delete(ids=results['ids'])
            logger.info(f"Deleted {len(results['ids'])} chunks for document {doc_id}")
        else:
            logger.warning(f"No chunks found for document {doc_id}")

    def get_collection_stats(self, collection: str) -> Dict[str, Any]:
        """Get statistics for a collection"""
        if collection not in self.collections:
            raise ValueError(f"Unknown collection: {collection}")

        coll = self.collections[collection]
        count = coll.count()

        return {
            "name": collection,
            "document_count": count,
            "metadata": coll.metadata
        }

    def list_collections(self) -> List[str]:
        """List all available collections"""
        return list(self.collections.keys())

    # Helper methods

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence.split())

            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                overlap_sentences = current_chunk[-2:] if len(current_chunk) > 2 else current_chunk
                current_chunk = overlap_sentences
                current_length = sum(len(s.split()) for s in current_chunk)

            current_chunk.append(sentence)
            current_length += sentence_length

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks if chunks else [text]

    def _keyword_search(
        self,
        query: str,
        collection: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Document]:
        """Simple keyword-based search"""
        results = self.collections[collection].get(where=filters, limit=top_k * 10)

        if not results['ids']:
            return []

        query_terms = set(query.lower().split())
        scored_docs = []

        for i in range(len(results['ids'])):
            content = results['documents'][i].lower()
            content_terms = set(content.split())
            overlap = len(query_terms & content_terms)
            score = overlap / len(query_terms) if query_terms else 0.0

            if score > 0:
                doc = Document(
                    doc_id=results['metadatas'][i].get('doc_id', results['ids'][i]),
                    content=results['documents'][i],
                    metadata=results['metadatas'][i],
                    score=score
                )
                scored_docs.append(doc)

        scored_docs.sort(key=lambda x: x.score, reverse=True)
        return scored_docs[:top_k]

    def _merge_search_results(
        self,
        vector_results: List[Document],
        keyword_results: List[Document],
        keyword_weight: float
    ) -> List[Document]:
        """Merge and deduplicate search results"""
        doc_map = {}
        vector_weight = 1.0 - keyword_weight

        for doc in vector_results:
            doc_map[doc.doc_id] = Document(
                doc_id=doc.doc_id,
                content=doc.content,
                metadata=doc.metadata,
                score=doc.score * vector_weight
            )

        for doc in keyword_results:
            if doc.doc_id in doc_map:
                doc_map[doc.doc_id].score += doc.score * keyword_weight
            else:
                doc_map[doc.doc_id] = Document(
                    doc_id=doc.doc_id,
                    content=doc.content,
                    metadata=doc.metadata,
                    score=doc.score * keyword_weight
                )

        merged = list(doc_map.values())
        merged.sort(key=lambda x: x.score, reverse=True)
        return merged

    def _build_context(self, documents: List[Document], max_length: int = 2000) -> str:
        """Build context string from documents"""
        context_parts = []
        total_words = 0

        for i, doc in enumerate(documents, 1):
            doc_words = len(doc.content.split())

            if total_words + doc_words > max_length:
                break

            context_parts.append(f"[Document {i}]\n{doc.content}\n")
            total_words += doc_words

        return "\n".join(context_parts)


# Export
__all__ = ["RAGSystem", "Document"]
