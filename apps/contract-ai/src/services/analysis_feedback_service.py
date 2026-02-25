# -*- coding: utf-8 -*-
"""
Analysis Feedback Service - Collect and manage feedback on contract analysis
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
import json

from ..models.analyzer_models import AnalysisFeedback
from ..models.database import AnalysisResult, Contract


class AnalysisFeedbackService:
    """
    Service for collecting and managing feedback on contract analysis
    
    Used for:
    - Quality assessment of analysis results
    - ML training data collection
    - Continuous improvement
    """

    def __init__(self, db_session):
        self.db_session = db_session

    def create_feedback(
        self,
        analysis_id: str,
        contract_id: str,
        user_id: str,
        overall_rating: Optional[int] = None,
        missed_risks: Optional[List[str]] = None,
        false_positives: Optional[List[str]] = None,
        recommendations_quality: Optional[int] = None,
        suggested_changes_quality: Optional[int] = None,
        positive_aspects: Optional[str] = None,
        areas_for_improvement: Optional[str] = None,
        additional_comments: Optional[str] = None
    ) -> AnalysisFeedback:
        """
        Create feedback for analysis
        
        Args:
            analysis_id: ID of analysis result
            contract_id: ID of contract
            user_id: ID of user providing feedback
            overall_rating: Rating 1-5
            missed_risks: List of risks that were missed
            false_positives: List of incorrectly identified risks
            recommendations_quality: Quality rating 1-5
            suggested_changes_quality: Quality rating 1-5
            positive_aspects: What was good
            areas_for_improvement: What needs improvement
            additional_comments: Other comments
        
        Returns:
            Created AnalysisFeedback object
        """
        try:
            logger.info(f"Creating feedback for analysis {analysis_id}")

            feedback = AnalysisFeedback(
                analysis_id=analysis_id,
                contract_id=contract_id,
                user_id=user_id,
                overall_rating=overall_rating,
                missed_risks=missed_risks or [],
                false_positives=false_positives or [],
                recommendations_quality=recommendations_quality,
                suggested_changes_quality=suggested_changes_quality,
                positive_aspects=positive_aspects,
                areas_for_improvement=areas_for_improvement,
                additional_comments=additional_comments
            )

            self.db_session.add(feedback)
            self.db_session.commit()
            self.db_session.refresh(feedback)

            logger.info(f"Feedback created: {feedback.id}")
            return feedback

        except Exception as e:
            logger.error(f"Failed to create feedback: {e}")
            self.db_session.rollback()
            raise

    def get_feedback(self, feedback_id: int) -> Optional[AnalysisFeedback]:
        """Get feedback by ID"""
        return self.db_session.query(AnalysisFeedback).filter(
            AnalysisFeedback.id == feedback_id
        ).first()

    def get_feedback_for_analysis(self, analysis_id: str) -> List[AnalysisFeedback]:
        """Get all feedback for an analysis"""
        return self.db_session.query(AnalysisFeedback).filter(
            AnalysisFeedback.analysis_id == analysis_id
        ).all()

    def get_feedback_for_contract(self, contract_id: str) -> List[AnalysisFeedback]:
        """Get all feedback for a contract"""
        return self.db_session.query(AnalysisFeedback).filter(
            AnalysisFeedback.contract_id == contract_id
        ).all()

    def update_feedback(
        self,
        feedback_id: int,
        **updates
    ) -> Optional[AnalysisFeedback]:
        """
        Update existing feedback
        
        Args:
            feedback_id: ID of feedback to update
            **updates: Fields to update
        
        Returns:
            Updated feedback or None
        """
        try:
            feedback = self.get_feedback(feedback_id)
            if not feedback:
                logger.warning(f"Feedback {feedback_id} not found")
                return None

            for key, value in updates.items():
                if hasattr(feedback, key):
                    setattr(feedback, key, value)

            self.db_session.commit()
            self.db_session.refresh(feedback)

            logger.info(f"Feedback {feedback_id} updated")
            return feedback

        except Exception as e:
            logger.error(f"Failed to update feedback: {e}")
            self.db_session.rollback()
            raise

    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get feedback statistics
        
        Args:
            start_date: Filter from this date
            end_date: Filter to this date
        
        Returns:
            Statistics dictionary
        """
        try:
            query = self.db_session.query(AnalysisFeedback)

            if start_date:
                query = query.filter(AnalysisFeedback.created_at >= start_date)
            if end_date:
                query = query.filter(AnalysisFeedback.created_at <= end_date)

            feedbacks = query.all()

            if not feedbacks:
                return {
                    'total_feedback': 0,
                    'average_rating': None,
                    'average_recommendations_quality': None,
                    'average_suggested_changes_quality': None,
                    'total_missed_risks': 0,
                    'total_false_positives': 0,
                    'ready_for_training': 0
                }

            # Calculate statistics
            ratings = [f.overall_rating for f in feedbacks if f.overall_rating]
            rec_quality = [f.recommendations_quality for f in feedbacks if f.recommendations_quality]
            changes_quality = [f.suggested_changes_quality for f in feedbacks if f.suggested_changes_quality]

            total_missed = sum(len(f.missed_risks or []) for f in feedbacks)
            total_false = sum(len(f.false_positives or []) for f in feedbacks)

            # Count feedback ready for training (rating >= 3)
            ready_for_training = sum(1 for f in feedbacks if f.overall_rating and f.overall_rating >= 3)

            return {
                'total_feedback': len(feedbacks),
                'average_rating': sum(ratings) / len(ratings) if ratings else None,
                'average_recommendations_quality': sum(rec_quality) / len(rec_quality) if rec_quality else None,
                'average_suggested_changes_quality': sum(changes_quality) / len(changes_quality) if changes_quality else None,
                'total_missed_risks': total_missed,
                'total_false_positives': total_false,
                'ready_for_training': ready_for_training,
                'rating_distribution': self._get_rating_distribution(feedbacks)
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def _get_rating_distribution(self, feedbacks: List[AnalysisFeedback]) -> Dict[int, int]:
        """Get distribution of ratings"""
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for feedback in feedbacks:
            if feedback.overall_rating:
                distribution[feedback.overall_rating] = distribution.get(feedback.overall_rating, 0) + 1
        return distribution

    def export_training_data(
        self,
        min_rating: int = 3,
        include_false_positives: bool = True
    ) -> str:
        """
        Export feedback as training data (JSON format)
        
        Args:
            min_rating: Minimum rating to include
            include_false_positives: Include false positive info
        
        Returns:
            JSON string with training data
        """
        try:
            logger.info(f"Exporting training data (min_rating={min_rating})")

            query = self.db_session.query(AnalysisFeedback)
            if min_rating:
                query = query.filter(AnalysisFeedback.overall_rating >= min_rating)

            feedbacks = query.all()

            training_data = []
            for feedback in feedbacks:
                # Get associated analysis
                analysis = self.db_session.query(AnalysisResult).filter(
                    AnalysisResult.id == feedback.analysis_id
                ).first()

                if not analysis:
                    continue

                # Get associated contract
                contract = self.db_session.query(Contract).filter(
                    Contract.id == feedback.contract_id
                ).first()

                if not contract:
                    continue

                entry = {
                    'feedback_id': feedback.id,
                    'analysis_id': feedback.analysis_id,
                    'contract_id': feedback.contract_id,
                    'contract_type': contract.contract_type,
                    'overall_rating': feedback.overall_rating,
                    'recommendations_quality': feedback.recommendations_quality,
                    'suggested_changes_quality': feedback.suggested_changes_quality,
                    'analysis_result': analysis.result_data,
                    'missed_risks': feedback.missed_risks,
                    'positive_aspects': feedback.positive_aspects,
                    'areas_for_improvement': feedback.areas_for_improvement,
                    'timestamp': feedback.created_at.isoformat() if feedback.created_at else None
                }

                if include_false_positives:
                    entry['false_positives'] = feedback.false_positives

                training_data.append(entry)

            logger.info(f"Exported {len(training_data)} training samples")
            return json.dumps(training_data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to export training data: {e}")
            raise

    def get_common_issues(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get most common issues from feedback
        
        Args:
            limit: Number of top issues to return
        
        Returns:
            Dictionary with common issues
        """
        try:
            feedbacks = self.db_session.query(AnalysisFeedback).all()

            # Collect all missed risks
            missed_risks_counter = {}
            for feedback in feedbacks:
                for risk in feedback.missed_risks or []:
                    missed_risks_counter[risk] = missed_risks_counter.get(risk, 0) + 1

            # Collect all false positives
            false_positives_counter = {}
            for feedback in feedbacks:
                for fp in feedback.false_positives or []:
                    false_positives_counter[fp] = false_positives_counter.get(fp, 0) + 1

            # Sort by frequency
            top_missed = sorted(
                missed_risks_counter.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]

            top_false_positives = sorted(
                false_positives_counter.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]

            return {
                'most_missed_risks': [
                    {'risk': risk, 'count': count}
                    for risk, count in top_missed
                ],
                'most_false_positives': [
                    {'risk': risk, 'count': count}
                    for risk, count in top_false_positives
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get common issues: {e}")
            return {
                'most_missed_risks': [],
                'most_false_positives': []
            }

    def get_improvement_suggestions(self) -> List[str]:
        """
        Get aggregated improvement suggestions from feedback
        
        Returns:
            List of improvement areas
        """
        try:
            feedbacks = self.db_session.query(AnalysisFeedback).filter(
                AnalysisFeedback.areas_for_improvement.isnot(None)
            ).all()

            suggestions = []
            for feedback in feedbacks:
                if feedback.areas_for_improvement:
                    suggestions.append({
                        'feedback_id': feedback.id,
                        'rating': feedback.overall_rating,
                        'suggestion': feedback.areas_for_improvement,
                        'timestamp': feedback.created_at.isoformat() if feedback.created_at else None
                    })

            # Sort by rating (lowest first - most critical)
            suggestions.sort(key=lambda x: x['rating'] if x['rating'] else 5)

            return suggestions

        except Exception as e:
            logger.error(f"Failed to get improvement suggestions: {e}")
            return []


__all__ = ["AnalysisFeedbackService"]
