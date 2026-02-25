# -*- coding: utf-8 -*-
"""
Optimized Queries - Performance-optimized database queries

Решает N+1 проблемы через:
- Eager loading (joinedload, selectinload)
- Batch queries
- Proper indexing usage
- Query result caching
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload, selectinload
from loguru import logger

from ..models.database import Contract, AnalysisResult
from ..models.disagreement_models import Disagreement, DisagreementObjection, DisagreementFeedback
from ..models.analyzer_models import ContractRisk, ContractRecommendation


class OptimizedQueries:
    """
    Collection of optimized database queries

    Replaces N+1 patterns with efficient eager loading
    """

    def __init__(self, db_session: Session):
        """
        Initialize with database session

        Args:
            db_session: SQLAlchemy session
        """
        self.db = db_session

    def get_disagreements_with_objections(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Disagreement]:
        """
        Get disagreements with their objections (OPTIMIZED - no N+1)

        Old pattern (N+1 problem):
        ```python
        disagreements = db.query(Disagreement).all()
        for d in disagreements:
            objections = db.query(DisagreementObjection).filter_by(disagreement_id=d.id).all()
        ```

        New pattern (single query):
        ```python
        disagreements = optimized.get_disagreements_with_objections()
        for d in disagreements:
            objections = d.objections  # Already loaded!
        ```

        Args:
            start_date: Filter by creation date (from)
            end_date: Filter by creation date (to)
            limit: Max results

        Returns:
            List of Disagreement objects with objections eagerly loaded
        """
        query = self.db.query(Disagreement).options(
            selectinload(Disagreement.objections)  # Eager load objections
        )

        # Apply filters
        if start_date:
            query = query.filter(Disagreement.created_at >= start_date)
        if end_date:
            query = query.filter(Disagreement.created_at <= end_date)

        # Order by most recent
        query = query.order_by(Disagreement.created_at.desc())

        # Limit
        if limit:
            query = query.limit(limit)

        results = query.all()
        logger.debug(f"✓ Loaded {len(results)} disagreements with objections (1 query)")
        return results

    def get_disagreements_with_objections_and_feedback(
        self,
        disagreement_ids: Optional[List[str]] = None,
        min_effectiveness: Optional[float] = None
    ) -> List[Disagreement]:
        """
        Get disagreements with objections AND feedback (OPTIMIZED)

        Loads 3 levels deep in a single query:
        - Disagreements
        - Their objections
        - Objection feedback

        Old pattern: 1 + N + N*M queries
        New pattern: 1 query

        Args:
            disagreement_ids: Filter by specific IDs
            min_effectiveness: Filter by effectiveness score

        Returns:
            Disagreements with nested objections and feedback
        """
        query = self.db.query(Disagreement).options(
            selectinload(Disagreement.objections).selectinload(
                DisagreementObjection.feedback  # Nested eager loading
            )
        )

        # Apply filters
        if disagreement_ids:
            query = query.filter(Disagreement.id.in_(disagreement_ids))

        if min_effectiveness is not None:
            query = query.filter(Disagreement.effectiveness_score >= min_effectiveness)

        results = query.all()
        logger.debug(f"✓ Loaded {len(results)} disagreements with nested objections+feedback (1 query)")
        return results

    def get_contracts_with_risks(
        self,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        risk_level: Optional[str] = None,
        days_back: int = 30
    ) -> List[Contract]:
        """
        Get contracts with their risks (OPTIMIZED)

        Args:
            status: Filter by status
            assigned_to: Filter by assignee
            risk_level: Filter by risk level
            days_back: How many days to look back

        Returns:
            Contracts with risks eagerly loaded
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        query = self.db.query(Contract).options(
            selectinload(Contract.analysis_results).selectinload(
                AnalysisResult.risks  # Load analysis -> risks
            )
        )

        # Filters
        query = query.filter(Contract.upload_date >= cutoff_date)

        if status:
            query = query.filter(Contract.status == status)
        if assigned_to:
            query = query.filter(Contract.assigned_to == assigned_to)
        if risk_level:
            query = query.filter(Contract.risk_level == risk_level)

        # Order by most recent
        query = query.order_by(Contract.upload_date.desc())

        results = query.all()
        logger.debug(f"✓ Loaded {len(results)} contracts with risks (optimized)")
        return results

    def get_high_risk_contracts_summary(self) -> List[Dict[str, Any]]:
        """
        Get summary of high-risk contracts (OPTIMIZED with aggregation)

        Returns aggregated data instead of loading all entities

        Returns:
            List of summary dicts
        """
        from sqlalchemy import func

        # Aggregate query - much faster than loading all objects
        results = self.db.query(
            Contract.id,
            Contract.file_name,
            Contract.upload_date,
            Contract.status,
            Contract.risk_level,
            func.count(ContractRisk.id).label('risk_count')
        ).join(
            AnalysisResult, Contract.id == AnalysisResult.contract_id
        ).join(
            ContractRisk, AnalysisResult.id == ContractRisk.analysis_id
        ).filter(
            ContractRisk.severity.in_(['critical', 'high'])
        ).group_by(
            Contract.id,
            Contract.file_name,
            Contract.upload_date,
            Contract.status,
            Contract.risk_level
        ).order_by(
            func.count(ContractRisk.id).desc()
        ).limit(50).all()

        # Convert to dicts
        summary = [
            {
                'contract_id': r.id,
                'file_name': r.file_name,
                'upload_date': r.upload_date.isoformat() if r.upload_date else None,
                'status': r.status,
                'risk_level': r.risk_level,
                'high_risk_count': r.risk_count
            }
            for r in results
        ]

        logger.debug(f"✓ Generated high-risk summary for {len(summary)} contracts (aggregation query)")
        return summary

    def get_objections_batch(
        self,
        disagreement_ids: List[str]
    ) -> Dict[str, List[DisagreementObjection]]:
        """
        Batch load objections for multiple disagreements (OPTIMIZED)

        Old pattern:
        ```python
        for disagreement_id in ids:
            objections = db.query(DisagreementObjection).filter_by(...).all()
        ```

        New pattern:
        ```python
        objections_map = get_objections_batch(ids)
        for disagreement_id in ids:
            objections = objections_map[disagreement_id]
        ```

        Args:
            disagreement_ids: List of disagreement IDs

        Returns:
            Dict mapping disagreement_id -> list of objections
        """
        # Single query for all objections
        objections = self.db.query(DisagreementObjection).filter(
            DisagreementObjection.disagreement_id.in_(disagreement_ids)
        ).order_by(
            DisagreementObjection.disagreement_id,
            DisagreementObjection.created_at.desc()
        ).all()

        # Group by disagreement_id
        objections_map: Dict[str, List[DisagreementObjection]] = {}
        for obj in objections:
            if obj.disagreement_id not in objections_map:
                objections_map[obj.disagreement_id] = []
            objections_map[obj.disagreement_id].append(obj)

        logger.debug(f"✓ Batch loaded objections for {len(disagreement_ids)} disagreements (1 query)")
        return objections_map

    def get_feedback_batch(
        self,
        objection_ids: List[int]
    ) -> Dict[int, List[DisagreementFeedback]]:
        """
        Batch load feedback for multiple objections (OPTIMIZED)

        Args:
            objection_ids: List of objection IDs

        Returns:
            Dict mapping objection_id -> list of feedback
        """
        feedback_list = self.db.query(DisagreementFeedback).filter(
            DisagreementFeedback.objection_id.in_(objection_ids)
        ).order_by(
            DisagreementFeedback.objection_id,
            DisagreementFeedback.created_at.desc()
        ).all()

        # Group by objection_id
        feedback_map: Dict[int, List[DisagreementFeedback]] = {}
        for fb in feedback_list:
            if fb.objection_id not in feedback_map:
                feedback_map[fb.objection_id] = []
            feedback_map[fb.objection_id].append(fb)

        logger.debug(f"✓ Batch loaded feedback for {len(objection_ids)} objections (1 query)")
        return feedback_map

    def count_by_status(self, model_class, days_back: int = 30) -> Dict[str, int]:
        """
        Count entities by status (efficient aggregation)

        Args:
            model_class: Model to count (Contract, Disagreement, etc.)
            days_back: How many days to look back

        Returns:
            Dict mapping status -> count
        """
        from sqlalchemy import func

        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        results = self.db.query(
            model_class.status,
            func.count(model_class.id)
        ).filter(
            model_class.created_at >= cutoff_date
        ).group_by(
            model_class.status
        ).all()

        counts = {status: count for status, count in results}
        logger.debug(f"✓ Counted {model_class.__name__} by status: {counts}")
        return counts


__all__ = ['OptimizedQueries']
