"""
RAG (Retrieval-Augmented Generation) Service for Contract AI System v2.0
Uses pgvector for semantic search in knowledge_base and contracts_core
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import logging
import numpy as np

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG Service for retrieving relevant context from knowledge base and past contracts.

    Features:
    - Semantic search using pgvector (cosine similarity)
    - Multi-source retrieval (knowledge_base, contracts_core)
    - Context filtering and ranking
    - Usage statistics tracking
    """

    def __init__(
        self,
        db_session: AsyncSession,
        embedding_model: Any = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ):
        """
        Initialize RAG Service.

        Args:
            db_session: Async database session
            embedding_model: Embedding model instance (e.g., SentenceTransformer)
            top_k: Number of results to retrieve
            similarity_threshold: Minimum similarity score (0.0-1.0)
        """
        self.db = db_session
        self.embedding_model = embedding_model
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

        logger.info(f"RAGService initialized (top_k={top_k}, threshold={similarity_threshold})")

    async def retrieve_context(
        self,
        query: str,
        context_type: Optional[str] = None,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from knowledge base.

        Args:
            query: Search query text
            context_type: Filter by content type ('best_practice', 'regulation', etc.)
            top_k: Override default top_k
            filters: Additional JSONB filters on metadata

        Returns:
            List of relevant context entries with similarity scores
        """
        if not self.embedding_model:
            logger.warning("No embedding model configured, RAG disabled")
            return []

        top_k = top_k or self.top_k

        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Build query
        similarity_expr = text(
            f"1 - (embedding <=> CAST(:query_embedding AS vector))"
        )

        query_sql = select(
            text("id, content_type, title, content, metadata, source, "
                 f"{similarity_expr} as similarity")
        ).select_from(text("knowledge_base"))

        # Filters
        where_clauses = [f"{similarity_expr} >= :threshold"]

        if context_type:
            where_clauses.append("content_type = :context_type")

        where_clauses.append("is_active = true")

        if where_clauses:
            query_sql = query_sql.where(text(" AND ".join(where_clauses)))

        # Order and limit
        query_sql = query_sql.order_by(text("similarity DESC")).limit(top_k)

        # Execute query
        params = {
            "query_embedding": query_embedding.tolist(),
            "threshold": self.similarity_threshold
        }

        if context_type:
            params["context_type"] = context_type

        try:
            result = await self.db.execute(query_sql, params)
            rows = result.fetchall()

            context_results = []
            for row in rows:
                context_results.append({
                    "id": str(row.id),
                    "content_type": row.content_type,
                    "title": row.title,
                    "content": row.content,
                    "metadata": row.metadata,
                    "source": row.source,
                    "similarity": float(row.similarity)
                })

            logger.info(f"Retrieved {len(context_results)} context entries for query: '{query[:50]}...'")

            # Update usage statistics
            if context_results:
                await self._update_usage_stats([r["id"] for r in context_results])

            return context_results

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return []

    async def find_similar_contracts(
        self,
        query_text: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar contracts using semantic search.

        Args:
            query_text: Text to search for (contract description, key terms)
            top_k: Number of similar contracts to retrieve

        Returns:
            List of similar contracts with metadata
        """
        if not self.embedding_model:
            logger.warning("No embedding model configured")
            return []

        # Generate query embedding
        query_embedding = await self._generate_embedding(query_text)

        # Search in contracts_core using pgvector
        similarity_expr = text(
            "1 - (embedding <=> CAST(:query_embedding AS vector))"
        )

        query_sql = select(
            text(f"id, doc_number, signed_date, total_amount, status, "
                 f"attributes, {similarity_expr} as similarity")
        ).select_from(text("contracts_core")).where(
            text(f"{similarity_expr} >= :threshold AND embedding IS NOT NULL")
        ).order_by(
            text("similarity DESC")
        ).limit(top_k)

        try:
            result = await self.db.execute(
                query_sql,
                {
                    "query_embedding": query_embedding.tolist(),
                    "threshold": self.similarity_threshold
                }
            )
            rows = result.fetchall()

            similar_contracts = []
            for row in rows:
                similar_contracts.append({
                    "id": str(row.id),
                    "doc_number": row.doc_number,
                    "signed_date": str(row.signed_date) if row.signed_date else None,
                    "total_amount": float(row.total_amount) if row.total_amount else None,
                    "status": row.status,
                    "attributes": row.attributes,
                    "similarity": float(row.similarity)
                })

            logger.info(f"Found {len(similar_contracts)} similar contracts")
            return similar_contracts

        except Exception as e:
            logger.error(f"Similar contracts search failed: {e}")
            return []

    async def find_similar_processed_docs(
        self,
        complexity_score: float,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find similar documents that were successfully processed.
        Used by ModelRouter to make RAG-assisted routing decisions.

        Args:
            complexity_score: Document complexity score (0.0-1.0)
            limit: Maximum number of documents to retrieve

        Returns:
            List of similar processed documents with processing metadata
        """
        try:
            # Find documents with similar complexity scores from llm_usage_metrics
            query_sql = select(
                text("document_id, model_used, complexity_score, confidence_score, "
                     "status, cost_usd, processing_time_sec")
            ).select_from(text("llm_usage_metrics")).where(
                text("complexity_score BETWEEN :min_score AND :max_score "
                     "AND confidence_score >= 0.7 "
                     "AND status = 'success'")
            ).order_by(
                text("ABS(complexity_score - :target_score)")
            ).limit(limit)

            result = await self.db.execute(
                query_sql,
                {
                    "min_score": max(0.0, complexity_score - 0.2),
                    "max_score": min(1.0, complexity_score + 0.2),
                    "target_score": complexity_score
                }
            )
            rows = result.fetchall()

            processed_docs = []
            for row in rows:
                processed_docs.append({
                    "document_id": str(row.document_id) if row.document_id else None,
                    "model_used": row.model_used,
                    "complexity_score": float(row.complexity_score),
                    "confidence_score": float(row.confidence_score),
                    "success": row.status == "success",
                    "cost_usd": float(row.cost_usd) if row.cost_usd else 0.0,
                    "processing_time_sec": float(row.processing_time_sec) if row.processing_time_sec else 0.0
                })

            logger.info(f"Found {len(processed_docs)} similar processed documents")
            return processed_docs

        except Exception as e:
            logger.error(f"Similar processed docs search failed: {e}")
            return []

    async def filter_with_context(
        self,
        extracted_data: Dict[str, Any],
        context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Filter and enhance extracted data using RAG context.

        Args:
            extracted_data: Raw extracted data from LLM
            context: RAG-retrieved context entries

        Returns:
            Enhanced/validated data
        """
        # This is a placeholder for complex filtering logic
        # In production, you would:
        # 1. Validate extracted values against known patterns from context
        # 2. Fill in missing fields from similar contracts
        # 3. Flag anomalies (e.g., unusual payment terms)

        enhanced_data = extracted_data.copy()

        # Example: Validate penalty rates
        if "rules" in extracted_data:
            for rule in extracted_data["rules"]:
                if rule.get("type") == "penalty":
                    # Check against best practices
                    penalty_context = [
                        c for c in context
                        if c.get("content_type") == "template_clause"
                        and "penalty" in c.get("metadata", {}).get("category", "")
                    ]

                    if penalty_context:
                        # Log if penalty rate is unusual
                        standard_rate = penalty_context[0].get("metadata", {}).get("daily_rate", 0.001)
                        if rule.get("rate", 0) > standard_rate * 2:
                            logger.warning(f"Unusual penalty rate detected: {rule.get('rate')}")

        return enhanced_data

    async def _generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not self.embedding_model:
            # Return zero vector as fallback
            return np.zeros(1536)

        try:
            # Assuming sentence-transformers or similar
            if hasattr(self.embedding_model, 'encode'):
                embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            else:
                # Fallback
                embedding = np.zeros(1536)

            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return np.zeros(1536)

    async def _update_usage_stats(self, knowledge_ids: List[str]):
        """
        Update usage statistics for knowledge base entries.

        Args:
            knowledge_ids: List of knowledge base entry IDs
        """
        try:
            update_sql = text(
                "UPDATE knowledge_base "
                "SET usage_count = usage_count + 1, "
                "    last_used_at = NOW() "
                "WHERE id = ANY(:ids)"
            )

            await self.db.execute(update_sql, {"ids": knowledge_ids})
            await self.db.commit()

        except Exception as e:
            logger.error(f"Failed to update usage stats: {e}")

    async def add_knowledge_entry(
        self,
        content_type: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ) -> str:
        """
        Add new entry to knowledge base.

        Args:
            content_type: Type of content
            title: Entry title
            content: Full content text
            metadata: Additional metadata
            source: Source reference

        Returns:
            ID of created entry
        """
        # Generate embedding
        embedding = await self._generate_embedding(content)

        # Insert into knowledge_base
        insert_sql = text(
            "INSERT INTO knowledge_base "
            "(content_type, title, content, embedding, metadata, source, priority) "
            "VALUES (:content_type, :title, :content, CAST(:embedding AS vector), "
            "        :metadata, :source, :priority) "
            "RETURNING id"
        )

        try:
            result = await self.db.execute(
                insert_sql,
                {
                    "content_type": content_type,
                    "title": title,
                    "content": content,
                    "embedding": embedding.tolist(),
                    "metadata": metadata or {},
                    "source": source,
                    "priority": 5  # Default priority
                }
            )
            await self.db.commit()

            knowledge_id = result.scalar()
            logger.info(f"Added knowledge entry: {title} (ID: {knowledge_id})")

            return str(knowledge_id)

        except Exception as e:
            logger.error(f"Failed to add knowledge entry: {e}")
            await self.db.rollback()
            raise


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_rag():
        # This is just for demonstration
        # In real usage, you would pass a real database session
        print("RAGService test placeholder")
        print("In production, connect to real database with pgvector")

    asyncio.run(test_rag())
