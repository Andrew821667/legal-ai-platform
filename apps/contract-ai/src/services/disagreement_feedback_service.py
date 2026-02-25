# -*- coding: utf-8 -*-
"""
Disagreement Feedback Service - Track effectiveness and collect feedback
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import json

from ..models.disagreement_models import (
    Disagreement, DisagreementObjection, DisagreementFeedback
)


class DisagreementFeedbackService:
    """
    Service for tracking disagreement effectiveness and collecting feedback
    
    Features:
    - Track counterparty responses (accepted/rejected/negotiated)
    - Quality ratings for objections
    - Effectiveness scoring for ML
    - Statistics and analytics
    - Training data export
    """

    def __init__(self, db_session):
        self.db_session = db_session

    def create_feedback(
        self,
        disagreement_id: int,
        objection_id: Optional[int],
        user_id: str,
        overall_quality: Optional[int] = None,
        usefulness_rating: Optional[int] = None,
        tone_appropriateness: Optional[int] = None,
        legal_basis_quality: Optional[int] = None,
        alternative_quality: Optional[int] = None,
        was_accepted: Optional[bool] = None,
        was_negotiated: Optional[bool] = None,
        led_to_contract_change: Optional[bool] = None,
        what_worked_well: Optional[str] = None,
        what_needs_improvement: Optional[str] = None,
        suggestions: Optional[str] = None
    ) -> DisagreementFeedback:
        """Create feedback for disagreement or specific objection"""
        try:
            logger.info(f"Creating feedback for disagreement {disagreement_id}")

            feedback = DisagreementFeedback(
                disagreement_id=disagreement_id,
                objection_id=objection_id,
                user_id=user_id,
                overall_quality=overall_quality,
                usefulness_rating=usefulness_rating,
                tone_appropriateness=tone_appropriateness,
                legal_basis_quality=legal_basis_quality,
                alternative_quality=alternative_quality,
                was_accepted=was_accepted,
                was_negotiated=was_negotiated,
                led_to_contract_change=led_to_contract_change,
                what_worked_well=what_worked_well,
                what_needs_improvement=what_needs_improvement,
                suggestions=suggestions
            )

            self.db_session.add(feedback)
            self.db_session.commit()
            self.db_session.refresh(feedback)

            # Update effectiveness score on disagreement
            self._update_effectiveness_score(disagreement_id)

            logger.info(f"Feedback created: {feedback.id}")
            return feedback

        except Exception as e:
            logger.error(f"Failed to create feedback: {e}")
            self.db_session.rollback()
            raise

    def update_objection_response(
        self,
        objection_id: int,
        counterparty_response: str,
        effectiveness_feedback: Optional[str] = None
    ):
        """Update counterparty response for objection"""
        try:
            objection = self.db_session.query(DisagreementObjection).filter(
                DisagreementObjection.id == objection_id
            ).first()

            if not objection:
                raise ValueError(f"Objection {objection_id} not found")

            objection.counterparty_response = counterparty_response
            objection.effectiveness_feedback = effectiveness_feedback

            self.db_session.commit()

            # Update disagreement effectiveness
            self._update_effectiveness_score(objection.disagreement_id)

            logger.info(f"Updated objection {objection_id} response: {counterparty_response}")

        except Exception as e:
            logger.error(f"Failed to update objection response: {e}")
            self.db_session.rollback()
            raise

    def _update_effectiveness_score(self, disagreement_id: int):
        """Calculate and update effectiveness score for disagreement"""
        try:
            disagreement = self.db_session.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement:
                return

            # Get all objections with responses
            objections = self.db_session.query(DisagreementObjection).filter(
                DisagreementObjection.disagreement_id == disagreement_id,
                DisagreementObjection.counterparty_response.isnot(None)
            ).all()

            if not objections:
                return

            # Calculate score
            total_score = 0
            for obj in objections:
                if obj.counterparty_response == 'accepted':
                    total_score += 1.0
                elif obj.counterparty_response == 'negotiated':
                    total_score += 0.5
                # rejected = 0.0

            effectiveness_score = total_score / len(objections) if objections else 0.0

            disagreement.effectiveness_score = effectiveness_score
            self.db_session.commit()

            logger.info(f"Updated effectiveness score for disagreement {disagreement_id}: {effectiveness_score:.2f}")

        except Exception as e:
            logger.error(f"Failed to update effectiveness score: {e}")

    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get disagreement statistics"""
        try:
            query = self.db_session.query(Disagreement)

            if start_date:
                query = query.filter(Disagreement.created_at >= start_date)
            if end_date:
                query = query.filter(Disagreement.created_at <= end_date)

            disagreements = query.all()

            if not disagreements:
                return {
                    'total_disagreements': 0,
                    'average_effectiveness': None,
                    'total_objections': 0,
                    'response_breakdown': {}
                }

            # Calculate stats
            effectiveness_scores = [d.effectiveness_score for d in disagreements if d.effectiveness_score is not None]
            
            # Get all objections
            all_objection_ids = []
            for d in disagreements:
                objections = self.db_session.query(DisagreementObjection).filter(
                    DisagreementObjection.disagreement_id == d.id
                ).all()
                all_objection_ids.extend([obj.id for obj in objections])

            objections = self.db_session.query(DisagreementObjection).filter(
                DisagreementObjection.id.in_(all_objection_ids)
            ).all() if all_objection_ids else []

            # Response breakdown
            response_breakdown = {
                'accepted': 0,
                'rejected': 0,
                'negotiated': 0,
                'pending': 0
            }

            for obj in objections:
                if obj.counterparty_response:
                    response_breakdown[obj.counterparty_response] = response_breakdown.get(obj.counterparty_response, 0) + 1
                else:
                    response_breakdown['pending'] += 1

            return {
                'total_disagreements': len(disagreements),
                'average_effectiveness': sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else None,
                'total_objections': len(objections),
                'response_breakdown': response_breakdown,
                'by_status': self._count_by_status(disagreements)
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def _count_by_status(self, disagreements: List[Disagreement]) -> Dict[str, int]:
        """Count disagreements by status"""
        counts = {}
        for d in disagreements:
            counts[d.status] = counts.get(d.status, 0) + 1
        return counts

    def export_training_data(
        self,
        min_effectiveness: float = 0.5,
        include_rejected: bool = False
    ) -> str:
        """Export data for ML training"""
        try:
            logger.info(f"Exporting training data (min_effectiveness={min_effectiveness})")

            query = self.db_session.query(Disagreement)
            
            if not include_rejected:
                query = query.filter(Disagreement.effectiveness_score >= min_effectiveness)

            disagreements = query.all()

            training_data = []
            for disagreement in disagreements:
                # Get objections
                objections = self.db_session.query(DisagreementObjection).filter(
                    DisagreementObjection.disagreement_id == disagreement.id
                ).all()

                # Get feedbacks
                feedbacks = self.db_session.query(DisagreementFeedback).filter(
                    DisagreementFeedback.disagreement_id == disagreement.id
                ).all()

                entry = {
                    'disagreement_id': disagreement.id,
                    'contract_id': disagreement.contract_id,
                    'analysis_id': disagreement.analysis_id,
                    'effectiveness_score': disagreement.effectiveness_score,
                    'objections': [
                        {
                            'issue_description': obj.issue_description,
                            'legal_basis': obj.legal_basis,
                            'alternative_formulation': obj.alternative_formulation,
                            'priority': obj.priority,
                            'counterparty_response': obj.counterparty_response,
                            'user_selected': obj.user_selected
                        }
                        for obj in objections
                    ],
                    'feedbacks': [
                        {
                            'overall_quality': fb.overall_quality,
                            'usefulness_rating': fb.usefulness_rating,
                            'was_accepted': fb.was_accepted,
                            'was_negotiated': fb.was_negotiated,
                            'led_to_contract_change': fb.led_to_contract_change
                        }
                        for fb in feedbacks
                    ],
                    'timestamp': disagreement.created_at.isoformat() if disagreement.created_at else None
                }

                training_data.append(entry)

            logger.info(f"Exported {len(training_data)} training samples")
            return json.dumps(training_data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to export training data: {e}")
            raise

    def get_top_performing_objections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get objections with highest acceptance rate"""
        try:
            objections = self.db_session.query(DisagreementObjection).filter(
                DisagreementObjection.counterparty_response == 'accepted'
            ).limit(limit * 2).all()  # Get more to filter

            # Sort by priority and user_selected
            top_objections = []
            for obj in objections:
                top_objections.append({
                    'id': obj.id,
                    'priority': obj.priority,
                    'issue_description': obj.issue_description,
                    'legal_basis': obj.legal_basis,
                    'alternative_formulation': obj.alternative_formulation,
                    'response': obj.counterparty_response
                })

            return top_objections[:limit]

        except Exception as e:
            logger.error(f"Failed to get top objections: {e}")
            return []


__all__ = ["DisagreementFeedbackService"]
