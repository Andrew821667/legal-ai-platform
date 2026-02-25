# -*- coding: utf-8 -*-
"""
Orchestrator Agent - Central coordinator for all agents using LangGraph

Manages the entire workflow:
1. Onboarding: Parse and classify incoming documents
2. Generation/Analysis: Create or analyze contracts
3. Review Queue: Human-in-the-loop review
4. Post-review: Handle approved/rejected/negotiate outcomes
5. Changes Analysis: Process tracked changes if present
6. Export: Final document export

Uses LangGraph StateGraph for flexible workflow management
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import json
from loguru import logger
from sqlalchemy.orm import Session

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from ..services.llm_gateway import LLMGateway
from ..services.review_queue_service import ReviewQueueService
from ..models.database import Contract
from .base_agent import BaseAgent, AgentResult
from .onboarding_agent import OnboardingAgent
from .contract_generator_agent import ContractGeneratorAgent
from .contract_analyzer_agent import ContractAnalyzerAgent
from .disagreement_processor_agent import DisagreementProcessorAgent
from .changes_analyzer_agent import ChangesAnalyzerAgent
from .quick_export_agent import QuickExportAgent


class WorkflowState(dict):
    """
    Workflow state that passes between agents

    Key fields:
    - contract_id: Database ID of the contract
    - document_type: Type of document (contract, disagreement, tracked_changes)
    - current_agent: Current agent name
    - history: List of agent executions
    - data: Accumulated data from agents
    - review_status: Status from human review (pending, approved, rejected, negotiate)
    - error: Error message if any
    - completed: Whether workflow is completed
    """
    pass


class OrchestratorAgent:
    """
    Orchestrator Agent - Coordinates all agents using LangGraph

    Workflow graph:
    ```
    START
      ↓
    ONBOARDING (parse, classify)
      ↓
    [Route based on document_type]
      ├→ generator (if new contract)
      ├→ analyzer (if existing contract)
      └→ disagreement (if disagreement doc)
      ↓
    REVIEW_QUEUE (human review)
      ↓
    [Route based on review decision]
      ├→ export (if approved)
      ├→ disagreement (if rejected/negotiate)
      └→ rework (if needs changes)
      ↓
    CHANGES_ANALYZER (if tracked changes present)
      ↓
    EXPORT
      ↓
    END
    ```
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        db_session: Session,
        review_queue_service: ReviewQueueService,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Orchestrator

        Args:
            llm_gateway: LLM Gateway for all agents
            db_session: Database session
            review_queue_service: Review queue service for human-in-the-loop
            config: Orchestrator configuration
        """
        self.llm = llm_gateway
        self.db = db_session
        self.review_queue = review_queue_service
        self.config = config or {}

        # Initialize all agents
        self.agents = {
            'onboarding': OnboardingAgent(llm_gateway, db_session, config),
            'generator': ContractGeneratorAgent(llm_gateway, db_session, config),
            'analyzer': ContractAnalyzerAgent(llm_gateway, db_session, config),
            'disagreement': DisagreementProcessorAgent(llm_gateway, db_session, config),
            'changes': ChangesAnalyzerAgent(llm_gateway, db_session, config),
            'export': QuickExportAgent(llm_gateway, db_session, config)
        }

        # Build workflow graph
        self.graph = self._build_graph()

        logger.info("OrchestratorAgent initialized with LangGraph")

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow"""

        # Create graph with WorkflowState
        workflow = StateGraph(WorkflowState)

        # Add all nodes (agent executors)
        workflow.add_node("onboarding", self._execute_onboarding)
        workflow.add_node("generator", self._execute_generator)
        workflow.add_node("analyzer", self._execute_analyzer)
        workflow.add_node("disagreement", self._execute_disagreement)
        workflow.add_node("review_queue", self._execute_review_queue)
        workflow.add_node("changes", self._execute_changes)
        workflow.add_node("export", self._execute_export)

        # Set entry point
        workflow.set_entry_point("onboarding")

        # Add edges with routing logic
        workflow.add_conditional_edges(
            "onboarding",
            self._route_after_onboarding,
            {
                "generator": "generator",
                "analyzer": "analyzer",
                "disagreement": "disagreement"
            }
        )

        # After generation/analysis/disagreement → review queue
        workflow.add_edge("generator", "review_queue")
        workflow.add_edge("analyzer", "review_queue")
        workflow.add_edge("disagreement", "review_queue")

        # Route after review based on decision
        workflow.add_conditional_edges(
            "review_queue",
            self._route_after_review,
            {
                "export": "export",
                "disagreement": "disagreement",
                "changes": "changes",
                "end": END
            }
        )

        # Changes analyzer → export
        workflow.add_edge("changes", "export")

        # Export → END
        workflow.add_edge("export", END)

        return workflow.compile()

    # === Node Executors ===

    def _execute_onboarding(self, state: WorkflowState) -> WorkflowState:
        """Execute onboarding agent"""
        logger.info("Executing Onboarding Agent")

        agent = self.agents['onboarding']
        result = agent.execute(state)

        state['current_agent'] = 'onboarding'
        state['history'] = state.get('history', [])
        state['history'].append({
            'agent': 'onboarding',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result.to_dict()
        })

        if result.success:
            state['data'] = {**state.get('data', {}), **result.data}
            state['next_action'] = result.next_action
        else:
            state['error'] = result.error

        return state

    def _execute_generator(self, state: WorkflowState) -> WorkflowState:
        """Execute contract generator agent"""
        logger.info("Executing Contract Generator Agent")

        agent = self.agents['generator']
        result = agent.execute(state)

        state['current_agent'] = 'generator'
        state['history'].append({
            'agent': 'generator',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result.to_dict()
        })

        if result.success:
            state['data'] = {**state.get('data', {}), **result.data}
        else:
            state['error'] = result.error

        return state

    def _execute_analyzer(self, state: WorkflowState) -> WorkflowState:
        """Execute contract analyzer agent"""
        logger.info("Executing Contract Analyzer Agent")

        agent = self.agents['analyzer']
        result = agent.execute(state)

        state['current_agent'] = 'analyzer'
        state['history'].append({
            'agent': 'analyzer',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result.to_dict()
        })

        if result.success:
            state['data'] = {**state.get('data', {}), **result.data}
        else:
            state['error'] = result.error

        return state

    def _execute_disagreement(self, state: WorkflowState) -> WorkflowState:
        """Execute disagreement processor agent"""
        logger.info("Executing Disagreement Processor Agent")

        agent = self.agents['disagreement']
        result = agent.execute(state)

        state['current_agent'] = 'disagreement'
        state['history'].append({
            'agent': 'disagreement',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result.to_dict()
        })

        if result.success:
            state['data'] = {**state.get('data', {}), **result.data}
        else:
            state['error'] = result.error

        return state

    def _execute_review_queue(self, state: WorkflowState) -> WorkflowState:
        """Create review task and wait for human review"""
        logger.info("Creating review task")

        contract_id = state.get('contract_id')

        try:
            # Determine priority based on risks/urgency
            priority = self._determine_priority(state)

            # Create review task
            task = self.review_queue.create_task(
                contract_id=contract_id,
                priority=priority,
                comments=f"Review required after {state['current_agent']}"
            )

            state['review_task_id'] = task.id
            state['review_status'] = 'pending'
            state['current_agent'] = 'review_queue'
            state['history'].append({
                'agent': 'review_queue',
                'timestamp': datetime.utcnow().isoformat(),
                'action': 'task_created',
                'task_id': task.id
            })

            logger.info(f"Review task created: {task.id}")

        except Exception as e:
            logger.error(f"Failed to create review task: {e}")
            state['error'] = str(e)

        return state

    def _execute_changes(self, state: WorkflowState) -> WorkflowState:
        """Execute changes analyzer agent"""
        logger.info("Executing Changes Analyzer Agent")

        agent = self.agents['changes']
        result = agent.execute(state)

        state['current_agent'] = 'changes'
        state['history'].append({
            'agent': 'changes',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result.to_dict()
        })

        if result.success:
            state['data'] = {**state.get('data', {}), **result.data}
        else:
            state['error'] = result.error

        return state

    def _execute_export(self, state: WorkflowState) -> WorkflowState:
        """Execute export agent"""
        logger.info("Executing Quick Export Agent")

        agent = self.agents['export']
        result = agent.execute(state)

        state['current_agent'] = 'export'
        state['completed'] = True
        state['history'].append({
            'agent': 'export',
            'timestamp': datetime.utcnow().isoformat(),
            'result': result.to_dict()
        })

        if result.success:
            state['data'] = {**state.get('data', {}), **result.data}
        else:
            state['error'] = result.error

        return state

    # === Routing Logic ===

    def _route_after_onboarding(self, state: WorkflowState) -> str:
        """Route after onboarding based on document type"""

        document_type = state.get('document_type', 'contract')

        routing = {
            'contract': 'analyzer',        # Existing contract → analyze
            'disagreement': 'disagreement', # Disagreement doc → process
            'new_contract': 'generator',   # New contract request → generate
            'tracked_changes': 'analyzer'   # Tracked changes → analyze first
        }

        next_node = routing.get(document_type, 'analyzer')
        logger.info(f"Routing after onboarding: {document_type} → {next_node}")

        return next_node

    def _route_after_review(self, state: WorkflowState) -> str:
        """Route after review based on decision"""

        review_status = state.get('review_status', 'pending')
        has_tracked_changes = state.get('has_tracked_changes', False)

        if review_status == 'approved':
            # If approved and has tracked changes, analyze them first
            if has_tracked_changes:
                logger.info("Routing to changes analyzer (approved with tracked changes)")
                return "changes"
            else:
                logger.info("Routing to export (approved)")
                return "export"

        elif review_status == 'rejected':
            logger.info("Routing to disagreement processor (rejected)")
            return "disagreement"

        elif review_status == 'negotiate':
            logger.info("Routing to disagreement processor (negotiate)")
            return "disagreement"

        else:
            # Still pending or error
            logger.info("Review incomplete, ending workflow")
            return "end"

    def _determine_priority(self, state: WorkflowState) -> str:
        """Determine review task priority based on state"""

        # Check for critical risks
        risks = state.get('data', {}).get('risks', {})
        if risks.get('CRITICAL') or risks.get('HIGH'):
            return 'high'

        # Check document type
        if state.get('document_type') == 'disagreement':
            return 'high'

        return 'medium'

    # === Public Interface ===

    def start_workflow(
        self,
        contract_id: str,
        file_path: str,
        document_type: str = 'contract',
        initial_data: Optional[Dict[str, Any]] = None
    ) -> WorkflowState:
        """
        Start contract processing workflow

        Args:
            contract_id: Database ID of contract
            file_path: Path to contract file
            document_type: Type of document (contract, disagreement, new_contract, tracked_changes)
            initial_data: Additional initial data

        Returns:
            Final workflow state
        """
        logger.info(f"Starting workflow for contract {contract_id}")

        # Initialize state
        initial_state = WorkflowState({
            'contract_id': contract_id,
            'file_path': file_path,
            'document_type': document_type,
            'data': initial_data or {},
            'history': [],
            'completed': False,
            'started_at': datetime.utcnow().isoformat()
        })

        try:
            # Run workflow
            final_state = self.graph.invoke(initial_state)

            logger.info(f"Workflow completed for contract {contract_id}")
            return final_state

        except Exception as e:
            logger.error(f"Workflow failed for contract {contract_id}: {e}")
            initial_state['error'] = str(e)
            initial_state['completed'] = False
            return initial_state

    def resume_workflow(
        self,
        task_id: str,
        review_decision: str,
        comments: Optional[str] = None
    ) -> WorkflowState:
        """
        Resume workflow after human review

        Args:
            task_id: Review task ID
            review_decision: Review decision (approve, reject, negotiate)
            comments: Review comments

        Returns:
            Updated workflow state
        """
        logger.info(f"Resuming workflow for task {task_id}, decision={review_decision}")

        try:
            # Get review task
            task = self.db.query(self.review_queue.repository.model).filter_by(id=task_id).first()
            if not task:
                raise ValueError(f"Review task not found: {task_id}")

            # Update review task
            self.review_queue.complete_review(
                task_id=task_id,
                decision=review_decision,
                comments=comments
            )

            # Load state from task/contract
            contract_id = task.contract_id

            # Reconstruct state (in production, this would be persisted)
            state = WorkflowState({
                'contract_id': contract_id,
                'review_task_id': task_id,
                'review_status': review_decision,
                'review_comments': comments,
                'data': {},
                'history': [],
                'completed': False
            })

            # Continue workflow from review_queue node
            # Note: In full implementation, would need to properly restore state
            logger.info("Workflow resumed (stub - full state restoration needed)")

            return state

        except Exception as e:
            logger.error(f"Failed to resume workflow: {e}")
            raise

    def get_workflow_status(self, contract_id: str) -> Dict[str, Any]:
        """
        Get current workflow status for a contract

        Args:
            contract_id: Contract ID

        Returns:
            Status dictionary
        """
        # In production, this would query persisted workflow state
        contract = self.db.query(Contract).filter_by(id=contract_id).first()

        if not contract:
            raise ValueError(f"Contract not found: {contract_id}")

        return {
            'contract_id': contract_id,
            'status': contract.status,
            'current_stage': 'onboarding',  # Would be tracked in state
            'completed': False
        }


# Export
__all__ = ["OrchestratorAgent", "WorkflowState"]
