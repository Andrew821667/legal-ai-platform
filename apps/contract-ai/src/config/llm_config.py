"""
LLM Configuration for Multi-Model Routing
Supports: DeepSeek-V3, Claude 4.5 Sonnet, GPT-4o, GPT-4o-mini
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class LLMConfig(BaseSettings):
    """
    Configuration for all supported LLM models.

    Models:
    - DeepSeek-V3: Primary worker ($0.14/1M tokens) - 90% задач
    - Claude 4.5 Sonnet: Expert fallback ($3.00/1M tokens) - сложные сканы
    - GPT-4o: Reserve channel ($2.50/1M tokens)
    - GPT-4o-mini: Testing/validation ($0.15/1M tokens)
    """

    # ========================================
    # DeepSeek Configuration
    # ========================================
    DEEPSEEK_API_KEY: str = Field(..., description="DeepSeek API key")
    DEEPSEEK_BASE_URL: str = Field(
        default="https://api.deepseek.com/v1",
        description="DeepSeek API base URL"
    )
    DEEPSEEK_MODEL: str = Field(
        default="deepseek-v3",
        description="DeepSeek model name"
    )
    DEEPSEEK_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for DeepSeek responses"
    )
    DEEPSEEK_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for DeepSeek (lower = more deterministic)"
    )

    # ========================================
    # Anthropic Claude Configuration
    # ========================================
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic API key")
    ANTHROPIC_MODEL: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model name"
    )
    ANTHROPIC_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for Claude responses"
    )
    ANTHROPIC_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for Claude"
    )

    # ========================================
    # OpenAI Configuration
    # ========================================
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL: str = Field(
        default="gpt-4o",
        description="GPT-4o model name"
    )
    OPENAI_MODEL_MINI: str = Field(
        default="gpt-4o-mini",
        description="GPT-4o-mini model name for testing"
    )
    OPENAI_MAX_TOKENS: int = Field(
        default=4096,
        description="Maximum tokens for GPT-4o responses"
    )
    OPENAI_TEMPERATURE: float = Field(
        default=0.1,
        description="Temperature for GPT-4o"
    )

    # ========================================
    # Smart Router Configuration
    # ========================================
    ROUTER_DEFAULT_MODEL: str = Field(
        default="deepseek-v3",
        description="Default model for Smart Router"
    )
    ROUTER_COMPLEXITY_THRESHOLD: float = Field(
        default=0.8,
        description="Complexity threshold for switching to Claude (0.0-1.0)"
    )
    ROUTER_ENABLE_FALLBACK: bool = Field(
        default=True,
        description="Enable fallback to alternative models on failure"
    )

    # ========================================
    # RAG Configuration
    # ========================================
    RAG_ENABLED: bool = Field(
        default=True,
        description="Enable RAG (Retrieval-Augmented Generation)"
    )
    RAG_TOP_K: int = Field(
        default=5,
        description="Number of documents to retrieve for RAG context"
    )
    RAG_SIMILARITY_THRESHOLD: float = Field(
        default=0.7,
        description="Minimum similarity score for RAG retrieval (0.0-1.0)"
    )

    # ========================================
    # Retry and Timeout Configuration
    # ========================================
    REQUEST_TIMEOUT: int = Field(
        default=120,
        description="Request timeout in seconds"
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retries on API failure"
    )
    RETRY_DELAY: float = Field(
        default=1.0,
        description="Initial delay between retries (exponential backoff)"
    )

    # ========================================
    # Cost Tracking
    # ========================================
    COST_TRACKING_ENABLED: bool = Field(
        default=True,
        description="Enable cost tracking for LLM usage"
    )

    # Costs per 1M tokens (input)
    COST_DEEPSEEK_INPUT: float = Field(default=0.14, description="DeepSeek cost per 1M input tokens")
    COST_CLAUDE_INPUT: float = Field(default=3.00, description="Claude cost per 1M input tokens")
    COST_GPT4O_INPUT: float = Field(default=2.50, description="GPT-4o cost per 1M input tokens")
    COST_GPT4O_MINI_INPUT: float = Field(default=0.15, description="GPT-4o-mini cost per 1M input tokens")

    # Costs per 1M tokens (output)
    COST_DEEPSEEK_OUTPUT: float = Field(default=0.28, description="DeepSeek cost per 1M output tokens")
    COST_CLAUDE_OUTPUT: float = Field(default=15.00, description="Claude cost per 1M output tokens")
    COST_GPT4O_OUTPUT: float = Field(default=10.00, description="GPT-4o cost per 1M output tokens")
    COST_GPT4O_MINI_OUTPUT: float = Field(default=0.60, description="GPT-4o-mini cost per 1M output tokens")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def get_model_costs(self, model: str) -> tuple[float, float]:
        """
        Get input and output costs per 1M tokens for a given model.

        Args:
            model: Model name (deepseek-v3, claude-4-5-sonnet, gpt-4o, gpt-4o-mini)

        Returns:
            Tuple of (input_cost, output_cost) per 1M tokens
        """
        costs = {
            "deepseek-v3": (self.COST_DEEPSEEK_INPUT, self.COST_DEEPSEEK_OUTPUT),
            "claude-sonnet-4-20250514": (self.COST_CLAUDE_INPUT, self.COST_CLAUDE_OUTPUT),
            "gpt-4o": (self.COST_GPT4O_INPUT, self.COST_GPT4O_OUTPUT),
            "gpt-4o-mini": (self.COST_GPT4O_MINI_INPUT, self.COST_GPT4O_MINI_OUTPUT),
        }
        return costs.get(model, (0.0, 0.0))

    def calculate_cost(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int
    ) -> float:
        """
        Calculate total cost for a given model and token usage.

        Args:
            model: Model name
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens

        Returns:
            Total cost in USD
        """
        cost_input, cost_output = self.get_model_costs(model)
        total_cost = (
            (tokens_input / 1_000_000) * cost_input +
            (tokens_output / 1_000_000) * cost_output
        )
        return round(total_cost, 6)


@lru_cache()
def get_llm_config() -> LLMConfig:
    """
    Get cached LLM configuration instance.

    Returns:
        LLMConfig instance
    """
    return LLMConfig()


# Example usage:
if __name__ == "__main__":
    config = get_llm_config()
    print(f"Default model: {config.ROUTER_DEFAULT_MODEL}")
    print(f"RAG enabled: {config.RAG_ENABLED}")

    # Calculate cost example
    cost = config.calculate_cost("deepseek-v3", tokens_input=1000, tokens_output=500)
    print(f"Cost for 1000 input + 500 output tokens (DeepSeek): ${cost:.6f}")
