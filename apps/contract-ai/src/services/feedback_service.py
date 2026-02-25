# -*- coding: utf-8 -*-
"""
Feedback Service - Collect and export training data for ML fine-tuning
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from ..models.database import ContractFeedback, Contract, User


class FeedbackService:
    """
    Service for collecting user feedback and exporting training data

    Collects:
    - User ratings (1-5)
    - Acceptance status
    - User corrections
    - Generation parameters
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def create_feedback(
        self,
        contract_id: str,
        user_id: str,
        rating: Optional[int] = None,
        acceptance_status: Optional[bool] = None,
        user_corrections: Optional[Dict] = None,
        generation_params: Optional[Dict] = None,
        template_id: Optional[str] = None,
        rag_context_used: Optional[Dict] = None,
        validation_errors: int = 0,
        validation_warnings: int = 0,
        generation_duration: Optional[float] = None,
        user_comment: Optional[str] = None
    ) -> ContractFeedback:
        """Create feedback record"""

        logger.info(f"Creating feedback for contract {contract_id}")

        feedback = ContractFeedback(
            contract_id=contract_id,
            user_id=user_id,
            rating=rating,
            acceptance_status=acceptance_status,
            user_corrections=user_corrections or {},
            generation_params=generation_params or {},
            template_id=template_id,
            rag_context_used=rag_context_used or {},
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            generation_duration=generation_duration,
            user_comment=user_comment
        )

        self.db_session.add(feedback)
        self.db_session.commit()
        self.db_session.refresh(feedback)

        logger.info(f"Feedback created: ID {feedback.id}")
        return feedback

    def update_feedback(
        self,
        feedback_id: int,
        rating: Optional[int] = None,
        acceptance_status: Optional[bool] = None,
        user_corrections: Optional[Dict] = None,
        user_comment: Optional[str] = None
    ) -> Optional[ContractFeedback]:
        """Update existing feedback"""

        feedback = self.db_session.query(ContractFeedback).filter(
            ContractFeedback.id == feedback_id
        ).first()

        if not feedback:
            logger.warning(f"Feedback {feedback_id} not found")
            return None

        if rating is not None:
            feedback.rating = rating
        if acceptance_status is not None:
            feedback.acceptance_status = acceptance_status
        if user_corrections is not None:
            feedback.user_corrections = user_corrections
        if user_comment is not None:
            feedback.user_comment = user_comment

        feedback.updated_at = datetime.utcnow()

        self.db_session.commit()
        self.db_session.refresh(feedback)

        logger.info(f"Feedback {feedback_id} updated")
        return feedback

    def get_feedback(self, contract_id: str) -> Optional[ContractFeedback]:
        """Get feedback for a contract"""

        return self.db_session.query(ContractFeedback).filter(
            ContractFeedback.contract_id == contract_id
        ).first()

    def get_all_feedback(
        self,
        min_rating: Optional[int] = None,
        acceptance_status: Optional[bool] = None,
        limit: int = 100
    ) -> List[ContractFeedback]:
        """Get all feedback with filters"""

        query = self.db_session.query(ContractFeedback)

        if min_rating is not None:
            query = query.filter(ContractFeedback.rating >= min_rating)

        if acceptance_status is not None:
            query = query.filter(ContractFeedback.acceptance_status == acceptance_status)

        query = query.order_by(ContractFeedback.created_at.desc()).limit(limit)

        return query.all()

    def export_training_data(
        self,
        min_rating: int = 3,
        accepted_only: bool = True,
        output_format: str = "jsonl"
    ) -> str:
        """
        Export training data for fine-tuning

        Args:
            min_rating: Minimum rating to include (1-5)
            accepted_only: Only include accepted contracts
            output_format: 'jsonl' or 'json'

        Returns:
            Formatted training data as string
        """

        logger.info(f"Exporting training data: min_rating={min_rating}, accepted_only={accepted_only}")

        # Get feedback records
        query = self.db_session.query(ContractFeedback)

        if min_rating:
            query = query.filter(ContractFeedback.rating >= min_rating)

        if accepted_only:
            query = query.filter(ContractFeedback.acceptance_status == True)

        feedbacks = query.all()

        logger.info(f"Found {len(feedbacks)} feedback records for export")

        training_examples = []

        for feedback in feedbacks:
            # Get contract content
            contract = self.db_session.query(Contract).filter(
                Contract.id == feedback.contract_id
            ).first()

            if not contract:
                continue

            # Format training example
            example = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a legal contract generation expert. Generate contracts based on templates and parameters."
                    },
                    {
                        "role": "user",
                        "content": self._format_user_prompt(feedback.generation_params, feedback.rag_context_used)
                    },
                    {
                        "role": "assistant",
                        "content": contract.content if contract.content else ""
                    }
                ],
                "metadata": {
                    "contract_id": feedback.contract_id,
                    "rating": feedback.rating,
                    "template_id": feedback.template_id,
                    "validation_errors": feedback.validation_errors,
                    "validation_warnings": feedback.validation_warnings
                }
            }

            training_examples.append(example)

        # Format output
        if output_format == "jsonl":
            output = "\n".join([json.dumps(ex, ensure_ascii=False) for ex in training_examples])
        else:
            output = json.dumps(training_examples, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(training_examples)} training examples")
        return output

    def _format_user_prompt(self, generation_params: Dict, rag_context: Dict) -> str:
        """Format user prompt from generation parameters"""

        prompt_parts = [
            "Generate a contract with the following parameters:",
            "",
            f"Type: {generation_params.get('contract_type', 'general')}",
            f"Subject: {generation_params.get('subject', 'N/A')}",
        ]

        if generation_params.get('parties'):
            prompt_parts.append("")
            prompt_parts.append("Parties:")
            for i, party in enumerate(generation_params['parties'], 1):
                prompt_parts.append(f"  {i}. {party.get('name', 'Unknown')}")

        if generation_params.get('price'):
            price = generation_params['price']
            prompt_parts.append("")
            prompt_parts.append(f"Price: {price.get('amount', 0)} {price.get('currency', 'RUB')}")

        if generation_params.get('term'):
            term = generation_params['term']
            prompt_parts.append("")
            prompt_parts.append(f"Term: {term.get('start_date')} to {term.get('end_date')}")

        if rag_context and rag_context.get('legal_norms'):
            prompt_parts.append("")
            prompt_parts.append("Legal requirements:")
            for norm in rag_context['legal_norms'][:2]:
                prompt_parts.append(f"- {norm[:100]}...")

        return "\n".join(prompt_parts)

    def get_statistics(self) -> Dict[str, Any]:
        """Get feedback statistics"""

        total = self.db_session.query(ContractFeedback).count()

        accepted = self.db_session.query(ContractFeedback).filter(
            ContractFeedback.acceptance_status == True
        ).count()

        rejected = self.db_session.query(ContractFeedback).filter(
            ContractFeedback.acceptance_status == False
        ).count()

        avg_rating = self.db_session.query(
            func.avg(ContractFeedback.rating)
        ).scalar() or 0

        return {
            'total_feedback': total,
            'accepted': accepted,
            'rejected': rejected,
            'pending': total - accepted - rejected,
            'average_rating': round(float(avg_rating), 2),
            'ready_for_training': self.db_session.query(ContractFeedback).filter(
                ContractFeedback.rating >= 3,
                ContractFeedback.acceptance_status == True
            ).count()
        }


__all__ = ["FeedbackService"]
