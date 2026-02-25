# -*- coding: utf-8 -*-
"""
Base Agent class for all AI agents in the Contract AI System

Provides common functionality:
- LLM interaction via LLMGateway
- State management
- Error handling
- Logging
- Result formatting
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from ..services.llm_gateway import LLMGateway


class AgentResult:
    """Standard result object for all agents"""

    def __init__(
        self,
        success: bool,
        data: Dict[str, Any],
        error: Optional[str] = None,
        next_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            success: Whether the agent execution was successful
            data: Result data from the agent
            error: Error message if execution failed
            next_action: Suggested next action for orchestrator
            metadata: Additional metadata (execution time, etc.)
        """
        self.success = success
        self.data = data
        self.error = error
        self.next_action = next_action
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "next_action": self.next_action,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }

    def __repr__(self):
        return f"AgentResult(success={self.success}, next_action={self.next_action})"


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents

    All agents must implement:
    - execute() method for main logic
    - get_name() method to return agent name
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        db_session: Session,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base agent

        Args:
            llm_gateway: LLM Gateway for AI interactions
            db_session: Database session
            config: Agent-specific configuration
        """
        self.llm = llm_gateway
        self.db = db_session
        self.config = config or {}
        self.execution_history: List[Dict[str, Any]] = []

        logger.info(f"{self.get_name()} initialized")

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """
        Execute the agent's main logic

        Args:
            state: Current workflow state

        Returns:
            AgentResult with execution results
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return the agent's name"""
        pass

    def get_system_prompt(self) -> str:
        """
        Get system prompt for this agent
        Can be overridden by subclasses
        """
        return "You are a helpful AI assistant for legal contract processing."

    def call_llm(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Call LLM with error handling

        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt (uses default if not provided)

        Returns:
            LLM response text
        """
        try:
            if system_prompt is None:
                system_prompt = self.get_system_prompt()

            response = self.llm.call(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response

        except Exception as e:
            logger.error(f"{self.get_name()} LLM call failed: {e}")
            raise

    def log_execution(
        self,
        action: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        duration: float
    ) -> None:
        """
        Log agent execution for audit trail

        Args:
            action: Action performed
            input_data: Input data
            output_data: Output data
            duration: Execution duration in seconds
        """
        log_entry = {
            "agent": self.get_name(),
            "action": action,
            "input": input_data,
            "output": output_data,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.execution_history.append(log_entry)
        logger.info(f"{self.get_name()} executed {action} in {duration:.2f}s")

    def validate_state(self, state: Dict[str, Any], required_keys: List[str]) -> bool:
        """
        Validate that state contains required keys

        Args:
            state: State to validate
            required_keys: List of required key names

        Returns:
            True if valid, raises ValueError if not
        """
        missing_keys = [key for key in required_keys if key not in state]

        if missing_keys:
            error_msg = f"{self.get_name()}: Missing required state keys: {missing_keys}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        return True

    def create_success_result(
        self,
        data: Dict[str, Any],
        next_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """Create a success result"""
        return AgentResult(
            success=True,
            data=data,
            next_action=next_action,
            metadata=metadata
        )

    def create_error_result(
        self,
        error: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """Create an error result"""
        return AgentResult(
            success=False,
            data=data or {},
            error=error,
            metadata=metadata
        )

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get value from agent config"""
        return self.config.get(key, default)


# Export
__all__ = ["BaseAgent", "AgentResult"]
