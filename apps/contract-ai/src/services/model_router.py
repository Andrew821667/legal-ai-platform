"""
Smart Model Router for Contract AI System v2.0
Intelligent selection between DeepSeek-V3, Claude 4.5 Sonnet, GPT-4o, and GPT-4o-mini
"""
from typing import Optional, Dict, Any
from src.config.llm_config import get_llm_config
import logging

logger = logging.getLogger(__name__)


class ModelRouter:
    """
    Smart Router for LLM model selection.

    Strategy:
    - DeepSeek-V3: Primary worker for 90% of tasks
    - Claude 4.5: Expert fallback for complex scans/documents
    - GPT-4o: Reserve channel if primary/fallback unavailable
    - GPT-4o-mini: Testing and validation
    """

    def __init__(self, rag_service: Optional[Any] = None):
        """
        Initialize Model Router.

        Args:
            rag_service: Optional RAG service for context-aware routing
        """
        self.config = get_llm_config()
        self.rag = rag_service
        logger.info(f"ModelRouter initialized with default model: {self.config.ROUTER_DEFAULT_MODEL}")

    def select_model(
        self,
        doc_complexity_score: float = 0.0,
        is_scanned_image: bool = False,
        force_model: Optional[str] = None,
        use_rag_context: bool = True,
        user_mode: str = "optimal"
    ) -> str:
        """
        Select the best model for processing a document.

        Args:
            doc_complexity_score: Document complexity (0.0-1.0)
                - 0.0-0.5: Simple (standard contract, good quality)
                - 0.5-0.8: Medium (complex tables, multiple parties)
                - 0.8-1.0: Complex (poor scan, handwritten notes, nested tables)
            is_scanned_image: True if document is a scan/photo (not native PDF/DOCX)
            force_model: Force specific model (deepseek-v3, claude-sonnet-4-20250514, gpt-4o, gpt-4o-mini)
            use_rag_context: Use RAG to check similar documents' processing history
            user_mode: User preference mode
                - 'optimal': Auto-select (DeepSeek by default) - recommended
                - 'expert': Always use Claude 4.5 Sonnet
                - 'testing': Use GPT-4o-mini for cost-effective testing

        Returns:
            Model name to use
        """
        # Force model override (highest priority)
        if force_model:
            logger.info(f"Force model selected: {force_model}")
            return self._normalize_model_name(force_model)

        # User mode override
        if user_mode == "expert":
            logger.info("Expert mode: using Claude 4.5 Sonnet")
            return self.config.ANTHROPIC_MODEL

        if user_mode == "testing":
            logger.info("Testing mode: using GPT-4o-mini")
            return self.config.OPENAI_MODEL_MINI

        # RAG-assisted routing (if available)
        if use_rag_context and self.rag:
            rag_suggestion = self._get_rag_suggestion(doc_complexity_score)
            if rag_suggestion:
                logger.info(f"RAG suggested model: {rag_suggestion}")
                return rag_suggestion

        # Rule-based routing
        selected_model = self._rule_based_selection(
            doc_complexity_score, is_scanned_image
        )

        logger.info(
            f"Selected model: {selected_model} "
            f"(complexity={doc_complexity_score:.2f}, is_scan={is_scanned_image})"
        )
        return selected_model

    def _rule_based_selection(
        self,
        doc_complexity_score: float,
        is_scanned_image: bool
    ) -> str:
        """
        Rule-based model selection logic.

        Rules:
        1. Scanned image + high complexity → Claude (best Vision capabilities)
        2. Complexity > threshold → Claude (expert handling)
        3. Default → DeepSeek (cost-effective workhorse)
        """
        # Rule 1: Complex scanned images need Claude's Vision
        if is_scanned_image and doc_complexity_score > self.config.ROUTER_COMPLEXITY_THRESHOLD:
            logger.debug("Routing to Claude: complex scanned image")
            return self.config.ANTHROPIC_MODEL

        # Rule 2: High complexity (even native docs) → Claude
        if doc_complexity_score > self.config.ROUTER_COMPLEXITY_THRESHOLD:
            logger.debug("Routing to Claude: high complexity score")
            return self.config.ANTHROPIC_MODEL

        # Rule 3: Default to DeepSeek (90% of cases)
        logger.debug("Routing to DeepSeek: standard document")
        return self.config.DEEPSEEK_MODEL

    def _get_rag_suggestion(self, doc_complexity_score: float) -> Optional[str]:
        """
        Get model suggestion from RAG based on similar documents.

        Logic:
        - Find similar documents that were successfully processed
        - If 80%+ were handled by DeepSeek successfully → use DeepSeek
        - If many failed with DeepSeek → use Claude

        Args:
            doc_complexity_score: Document complexity score

        Returns:
            Suggested model name or None
        """
        if not self.rag:
            return None

        try:
            # Query RAG for similar documents
            similar_docs = self.rag.find_similar_processed_docs(
                complexity_score=doc_complexity_score,
                limit=10
            )

            if not similar_docs:
                logger.debug("No similar documents found in RAG")
                return None

            # Analyze success rates by model
            model_stats = {}
            for doc in similar_docs:
                model = doc.get("model_used")
                success = doc.get("success", False)

                if model not in model_stats:
                    model_stats[model] = {"success": 0, "total": 0}

                model_stats[model]["total"] += 1
                if success:
                    model_stats[model]["success"] += 1

            # Check if DeepSeek has high success rate
            if "deepseek-v3" in model_stats:
                deepseek_stats = model_stats["deepseek-v3"]
                success_rate = deepseek_stats["success"] / deepseek_stats["total"]

                if success_rate >= 0.8 and deepseek_stats["total"] >= 3:
                    logger.debug(f"RAG: DeepSeek success rate {success_rate:.1%} on similar docs")
                    return self.config.DEEPSEEK_MODEL

            # If DeepSeek failed often, use Claude
            logger.debug("RAG: Suggesting Claude due to DeepSeek failures on similar docs")
            return self.config.ANTHROPIC_MODEL

        except Exception as e:
            logger.warning(f"RAG suggestion failed: {e}")
            return None

    def _normalize_model_name(self, model: str) -> str:
        """
        Normalize model name to full model identifier.

        Args:
            model: Short or full model name

        Returns:
            Full model identifier
        """
        model_map = {
            "deepseek": self.config.DEEPSEEK_MODEL,
            "deepseek-v3": self.config.DEEPSEEK_MODEL,
            "claude": self.config.ANTHROPIC_MODEL,
            "claude-4-5-sonnet": self.config.ANTHROPIC_MODEL,
            "claude-sonnet-4-20250514": self.config.ANTHROPIC_MODEL,
            "gpt-4o": self.config.OPENAI_MODEL,
            "gpt-4o-mini": self.config.OPENAI_MODEL_MINI,
            "openai": self.config.OPENAI_MODEL,
        }

        return model_map.get(model.lower(), model)

    def get_fallback_model(self, failed_model: str) -> Optional[str]:
        """
        Get fallback model when primary model fails.

        Fallback chain:
        - DeepSeek fails → Claude
        - Claude fails → GPT-4o
        - GPT-4o fails → None (no more fallbacks)

        Args:
            failed_model: Model that failed

        Returns:
            Fallback model name or None
        """
        if not self.config.ROUTER_ENABLE_FALLBACK:
            return None

        fallback_chain = {
            self.config.DEEPSEEK_MODEL: self.config.ANTHROPIC_MODEL,
            self.config.ANTHROPIC_MODEL: self.config.OPENAI_MODEL,
            self.config.OPENAI_MODEL: None,
            self.config.OPENAI_MODEL_MINI: self.config.DEEPSEEK_MODEL,
        }

        fallback = fallback_chain.get(failed_model)
        if fallback:
            logger.info(f"Fallback: {failed_model} → {fallback}")
        else:
            logger.warning(f"No fallback available for {failed_model}")

        return fallback

    def estimate_cost(
        self,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int
    ) -> float:
        """
        Estimate cost for processing with a given model.

        Args:
            model: Model name
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens

        Returns:
            Estimated cost in USD
        """
        return self.config.calculate_cost(
            model=model,
            tokens_input=estimated_input_tokens,
            tokens_output=estimated_output_tokens
        )

    def get_model_info(self, model: str) -> Dict[str, Any]:
        """
        Get information about a model.

        Args:
            model: Model name

        Returns:
            Dict with model info (role, cost, strengths)
        """
        model_info = {
            self.config.DEEPSEEK_MODEL: {
                "role": "Primary Worker",
                "cost_per_1m_input": self.config.COST_DEEPSEEK_INPUT,
                "cost_per_1m_output": self.config.COST_DEEPSEEK_OUTPUT,
                "strengths": ["Cost-effective", "Fast", "Good for standard documents"],
                "weaknesses": ["May struggle with poor scans", "Complex nested tables"],
            },
            self.config.ANTHROPIC_MODEL: {
                "role": "Expert Fallback",
                "cost_per_1m_input": self.config.COST_CLAUDE_INPUT,
                "cost_per_1m_output": self.config.COST_CLAUDE_OUTPUT,
                "strengths": ["Best Vision", "Complex document understanding", "High accuracy"],
                "weaknesses": ["Expensive", "Slower"],
            },
            self.config.OPENAI_MODEL: {
                "role": "Reserve Channel",
                "cost_per_1m_input": self.config.COST_GPT4O_INPUT,
                "cost_per_1m_output": self.config.COST_GPT4O_OUTPUT,
                "strengths": ["Reliable", "Good balance", "Wide availability"],
                "weaknesses": ["Mid-tier cost", "Not specialized"],
            },
            self.config.OPENAI_MODEL_MINI: {
                "role": "Testing & Validation",
                "cost_per_1m_input": self.config.COST_GPT4O_MINI_INPUT,
                "cost_per_1m_output": self.config.COST_GPT4O_MINI_OUTPUT,
                "strengths": ["Very cheap", "Fast", "Good for testing"],
                "weaknesses": ["Lower accuracy", "Limited capabilities"],
            },
        }

        return model_info.get(model, {"role": "Unknown", "strengths": [], "weaknesses": []})


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    router = ModelRouter()

    # Example 1: Simple document
    model = router.select_model(doc_complexity_score=0.3)
    print(f"Simple doc → {model}")

    # Example 2: Complex scanned document
    model = router.select_model(doc_complexity_score=0.9, is_scanned_image=True)
    print(f"Complex scan → {model}")

    # Example 3: Force model
    model = router.select_model(force_model="claude")
    print(f"Forced → {model}")

    # Example 4: Expert mode
    model = router.select_model(user_mode="expert")
    print(f"Expert mode → {model}")

    # Example 5: Cost estimation
    cost = router.estimate_cost("deepseek-v3", 1000, 500)
    print(f"Cost (DeepSeek, 1k in + 500 out) → ${cost:.6f}")
