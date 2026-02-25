# -*- coding: utf-8 -*-
"""
Review Queue Service - Complete task management system for human review workflow

Features:
- Priority queue with 3 levels (high, medium, low)
- Task assignment to specific users
- Deadline tracking with SLA monitoring
- Status workflow: pending → in_review → approved/rejected → completed
- Task filtering by status, priority, assignee
- Task history and audit log
- Bulk operations
- SLA metrics and analytics
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import json
from loguru import logger

from ..models.database import ReviewTask, Contract
from ..models.auth_models import User
from ..models.repositories import ReviewTaskRepository


class ReviewQueueService:
    """
    Service for managing human review tasks with full workflow support

    Status workflow:
    - pending: Task created, not yet assigned or started
    - in_review: Task assigned and being reviewed
    - approved: Review completed with approval decision
    - rejected: Review completed with rejection decision
    - completed: Final state after all actions taken

    Priority levels:
    - high: Urgent tasks, SLA = 4 hours
    - medium: Normal tasks, SLA = 24 hours
    - low: Non-urgent tasks, SLA = 72 hours
    """

    # Status constants
    STATUS_PENDING = "pending"
    STATUS_IN_REVIEW = "in_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed"

    # Priority constants
    PRIORITY_HIGH = "high"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_LOW = "low"

    # SLA durations (in minutes)
    SLA_DURATIONS = {
        PRIORITY_HIGH: 4 * 60,      # 4 hours
        PRIORITY_MEDIUM: 24 * 60,   # 24 hours
        PRIORITY_LOW: 72 * 60       # 72 hours
    }

    # Decision constants
    DECISION_APPROVE = "approve"
    DECISION_REJECT = "reject"
    DECISION_NEGOTIATE = "negotiate"

    def __init__(self, db_session: Session):
        """
        Initialize Review Queue Service

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.repository = ReviewTaskRepository(db_session)
        logger.info("ReviewQueueService initialized")

    # ==== Task Creation ====

    def create_task(
        self,
        contract_id: str,
        priority: str = PRIORITY_MEDIUM,
        assigned_to: Optional[str] = None,
        assigned_by: Optional[str] = None,
        deadline: Optional[datetime] = None,
        comments: Optional[str] = None
    ) -> ReviewTask:
        """
        Create a new review task

        Args:
            contract_id: Contract ID to review
            priority: Task priority (high/medium/low)
            assigned_to: User ID to assign (optional, can assign later)
            assigned_by: User ID who created the task
            deadline: Custom deadline (optional, will use SLA default)
            comments: Initial comments

        Returns:
            Created ReviewTask
        """
        logger.info(f"Creating review task for contract {contract_id}, priority={priority}")

        # Validate priority
        if priority not in [self.PRIORITY_HIGH, self.PRIORITY_MEDIUM, self.PRIORITY_LOW]:
            raise ValueError(f"Invalid priority: {priority}")

        # Validate contract exists
        contract = self.db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"Contract not found: {contract_id}")

        # Validate assignee exists if provided
        if assigned_to:
            assignee = self.db.query(User).filter(User.id == assigned_to).first()
            if not assignee:
                raise ValueError(f"User not found: {assigned_to}")

        # Calculate deadline if not provided
        if not deadline:
            expected_duration = self.SLA_DURATIONS.get(priority, self.SLA_DURATIONS[self.PRIORITY_MEDIUM])
            deadline = datetime.utcnow() + timedelta(minutes=expected_duration)
        else:
            # Calculate expected duration from deadline
            expected_duration = int((deadline - datetime.utcnow()).total_seconds() / 60)

        # Initialize history
        history = [{
            "status": self.STATUS_PENDING,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": assigned_by,
            "comment": "Task created"
        }]

        # Create task
        task = ReviewTask(
            contract_id=contract_id,
            assigned_to=assigned_to,
            assigned_by=assigned_by,
            status=self.STATUS_PENDING,
            priority=priority,
            deadline=deadline,
            comments=comments,
            expected_duration=expected_duration,
            assigned_at=datetime.utcnow() if assigned_to else None,
            history=json.dumps(history)
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Review task created: {task.id}")
        return task

    # ==== Task Assignment ====

    def assign_task(
        self,
        task_id: str,
        user_id: str,
        assigned_by: Optional[str] = None
    ) -> ReviewTask:
        """
        Assign task to a user

        Args:
            task_id: Task ID
            user_id: User ID to assign to
            assigned_by: User ID who is assigning

        Returns:
            Updated ReviewTask
        """
        logger.info(f"Assigning task {task_id} to user {user_id}")

        task = self.repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Validate user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Update task
        task.assigned_to = user_id
        task.assigned_by = assigned_by
        task.assigned_at = datetime.utcnow()

        # Add to history
        self._add_to_history(task, "assigned", assigned_by, f"Assigned to {user.name}")

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Task {task_id} assigned to {user.name}")
        return task

    def bulk_assign_tasks(
        self,
        task_ids: List[str],
        user_id: str,
        assigned_by: Optional[str] = None
    ) -> List[ReviewTask]:
        """
        Assign multiple tasks to a user

        Args:
            task_ids: List of task IDs
            user_id: User ID to assign to
            assigned_by: User ID who is assigning

        Returns:
            List of updated ReviewTasks
        """
        logger.info(f"Bulk assigning {len(task_ids)} tasks to user {user_id}")

        tasks = []
        for task_id in task_ids:
            try:
                task = self.assign_task(task_id, user_id, assigned_by)
                tasks.append(task)
            except Exception as e:
                logger.warning(f"Failed to assign task {task_id}: {e}")

        logger.info(f"Bulk assigned {len(tasks)}/{len(task_ids)} tasks")
        return tasks

    # ==== Task Status Updates ====

    def start_review(self, task_id: str, user_id: Optional[str] = None) -> ReviewTask:
        """
        Start reviewing a task (change status to in_review)

        Args:
            task_id: Task ID
            user_id: User ID who started the review

        Returns:
            Updated ReviewTask
        """
        logger.info(f"Starting review for task {task_id}")

        task = self.repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if task.status != self.STATUS_PENDING:
            raise ValueError(f"Cannot start review: task status is {task.status}")

        # Update status
        task.status = self.STATUS_IN_REVIEW
        task.started_at = datetime.utcnow()

        # Add to history
        self._add_to_history(task, self.STATUS_IN_REVIEW, user_id, "Review started")

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Review started for task {task_id}")
        return task

    def complete_review(
        self,
        task_id: str,
        decision: str,
        comments: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ReviewTask:
        """
        Complete a review with a decision

        Args:
            task_id: Task ID
            decision: Decision (approve/reject/negotiate)
            comments: Review comments
            user_id: User ID who completed the review

        Returns:
            Updated ReviewTask
        """
        logger.info(f"Completing review for task {task_id}, decision={decision}")

        task = self.repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if task.status not in [self.STATUS_IN_REVIEW, self.STATUS_PENDING]:
            raise ValueError(f"Cannot complete review: task status is {task.status}")

        # Validate decision
        if decision not in [self.DECISION_APPROVE, self.DECISION_REJECT, self.DECISION_NEGOTIATE]:
            raise ValueError(f"Invalid decision: {decision}")

        # Update status based on decision
        if decision == self.DECISION_APPROVE:
            new_status = self.STATUS_APPROVED
        elif decision == self.DECISION_REJECT:
            new_status = self.STATUS_REJECTED
        else:
            new_status = self.STATUS_IN_REVIEW  # negotiate keeps it in review

        task.status = new_status
        task.decision = decision
        task.completed_at = datetime.utcnow()

        if comments:
            task.comments = comments

        # Calculate actual duration
        if task.started_at:
            duration = (datetime.utcnow() - task.started_at).total_seconds() / 60
            task.actual_duration = int(duration)

        # Check SLA breach
        if datetime.utcnow() > task.deadline:
            task.sla_breached = True
            logger.warning(f"Task {task_id} breached SLA deadline")

        # Add to history
        self._add_to_history(task, new_status, user_id, f"Review completed: {decision}")

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Review completed for task {task_id}: {decision}")
        return task

    def mark_completed(self, task_id: str, user_id: Optional[str] = None) -> ReviewTask:
        """
        Mark task as fully completed (final state)

        Args:
            task_id: Task ID
            user_id: User ID who completed the task

        Returns:
            Updated ReviewTask
        """
        logger.info(f"Marking task {task_id} as completed")

        task = self.repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if task.status not in [self.STATUS_APPROVED, self.STATUS_REJECTED]:
            raise ValueError(f"Cannot mark as completed: task status is {task.status}")

        task.status = self.STATUS_COMPLETED

        # Add to history
        self._add_to_history(task, self.STATUS_COMPLETED, user_id, "Task finalized")

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Task {task_id} marked as completed")
        return task

    # ==== Queue Retrieval ====

    def get_pending_tasks(
        self,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50
    ) -> List[ReviewTask]:
        """
        Get pending tasks from queue

        Args:
            priority: Filter by priority (optional)
            assigned_to: Filter by assignee (optional)
            limit: Maximum number of tasks to return

        Returns:
            List of ReviewTasks ordered by priority and deadline
        """
        logger.info(f"Getting pending tasks: priority={priority}, assigned_to={assigned_to}")

        query = self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_PENDING)

        if priority:
            query = query.filter(ReviewTask.priority == priority)

        if assigned_to:
            query = query.filter(ReviewTask.assigned_to == assigned_to)

        # Order by priority (high first) and deadline
        priority_order = {
            self.PRIORITY_HIGH: 1,
            self.PRIORITY_MEDIUM: 2,
            self.PRIORITY_LOW: 3
        }

        tasks = query.limit(limit).all()

        # Sort by priority and deadline
        tasks.sort(key=lambda t: (priority_order.get(t.priority, 4), t.deadline))

        logger.info(f"Found {len(tasks)} pending tasks")
        return tasks

    def get_tasks_by_status(
        self,
        status: str,
        assigned_to: Optional[str] = None,
        limit: int = 100
    ) -> List[ReviewTask]:
        """
        Get tasks by status

        Args:
            status: Task status
            assigned_to: Filter by assignee (optional)
            limit: Maximum number of tasks

        Returns:
            List of ReviewTasks
        """
        logger.info(f"Getting tasks with status={status}, assigned_to={assigned_to}")

        query = self.db.query(ReviewTask).filter(ReviewTask.status == status)

        if assigned_to:
            query = query.filter(ReviewTask.assigned_to == assigned_to)

        tasks = query.order_by(ReviewTask.created_at.desc()).limit(limit).all()

        logger.info(f"Found {len(tasks)} tasks with status {status}")
        return tasks

    def get_user_tasks(
        self,
        user_id: str,
        status: Optional[str] = None,
        include_completed: bool = False
    ) -> List[ReviewTask]:
        """
        Get all tasks assigned to a user

        Args:
            user_id: User ID
            status: Filter by status (optional)
            include_completed: Include completed tasks

        Returns:
            List of ReviewTasks
        """
        logger.info(f"Getting tasks for user {user_id}, status={status}")

        query = self.db.query(ReviewTask).filter(ReviewTask.assigned_to == user_id)

        if status:
            query = query.filter(ReviewTask.status == status)
        elif not include_completed:
            query = query.filter(ReviewTask.status != self.STATUS_COMPLETED)

        tasks = query.order_by(ReviewTask.deadline.asc()).all()

        logger.info(f"Found {len(tasks)} tasks for user {user_id}")
        return tasks

    def get_overdue_tasks(self, assigned_to: Optional[str] = None) -> List[ReviewTask]:
        """
        Get tasks that have passed their deadline

        Args:
            assigned_to: Filter by assignee (optional)

        Returns:
            List of overdue ReviewTasks
        """
        logger.info(f"Getting overdue tasks, assigned_to={assigned_to}")

        query = self.db.query(ReviewTask).filter(
            and_(
                ReviewTask.deadline < datetime.utcnow(),
                ReviewTask.status.in_([self.STATUS_PENDING, self.STATUS_IN_REVIEW])
            )
        )

        if assigned_to:
            query = query.filter(ReviewTask.assigned_to == assigned_to)

        tasks = query.order_by(ReviewTask.deadline.asc()).all()

        logger.info(f"Found {len(tasks)} overdue tasks")
        return tasks

    # ==== SLA and Metrics ====

    def get_sla_metrics(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get SLA metrics for tasks

        Args:
            user_id: Filter by user (optional)
            start_date: Start date for metrics (optional)
            end_date: End date for metrics (optional)

        Returns:
            Dictionary with SLA metrics
        """
        logger.info(f"Calculating SLA metrics for user={user_id}")

        query = self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_COMPLETED)

        if user_id:
            query = query.filter(ReviewTask.assigned_to == user_id)

        if start_date:
            query = query.filter(ReviewTask.created_at >= start_date)

        if end_date:
            query = query.filter(ReviewTask.created_at <= end_date)

        tasks = query.all()

        if not tasks:
            return {
                "total_tasks": 0,
                "sla_met": 0,
                "sla_breached": 0,
                "sla_compliance_rate": 0.0,
                "avg_completion_time": 0,
                "by_priority": {}
            }

        total = len(tasks)
        breached = sum(1 for t in tasks if t.sla_breached)
        met = total - breached

        avg_duration = sum(t.actual_duration or 0 for t in tasks) / total if total > 0 else 0

        # Metrics by priority
        by_priority = {}
        for priority in [self.PRIORITY_HIGH, self.PRIORITY_MEDIUM, self.PRIORITY_LOW]:
            priority_tasks = [t for t in tasks if t.priority == priority]
            if priority_tasks:
                p_total = len(priority_tasks)
                p_breached = sum(1 for t in priority_tasks if t.sla_breached)
                p_avg = sum(t.actual_duration or 0 for t in priority_tasks) / p_total

                by_priority[priority] = {
                    "total": p_total,
                    "sla_met": p_total - p_breached,
                    "sla_breached": p_breached,
                    "compliance_rate": ((p_total - p_breached) / p_total * 100) if p_total > 0 else 0,
                    "avg_completion_time": p_avg
                }

        metrics = {
            "total_tasks": total,
            "sla_met": met,
            "sla_breached": breached,
            "sla_compliance_rate": (met / total * 100) if total > 0 else 0,
            "avg_completion_time": avg_duration,
            "by_priority": by_priority
        }

        logger.info(f"SLA metrics calculated: compliance={metrics['sla_compliance_rate']:.1f}%")
        return metrics

    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get current queue statistics

        Returns:
            Dictionary with queue statistics
        """
        logger.info("Getting queue statistics")

        stats = {
            "pending": self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_PENDING).count(),
            "in_review": self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_IN_REVIEW).count(),
            "approved": self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_APPROVED).count(),
            "rejected": self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_REJECTED).count(),
            "completed": self.db.query(ReviewTask).filter(ReviewTask.status == self.STATUS_COMPLETED).count(),
        }

        stats["total"] = sum(stats.values())

        # Overdue count
        stats["overdue"] = self.db.query(ReviewTask).filter(
            and_(
                ReviewTask.deadline < datetime.utcnow(),
                ReviewTask.status.in_([self.STATUS_PENDING, self.STATUS_IN_REVIEW])
            )
        ).count()

        # By priority
        stats["by_priority"] = {
            self.PRIORITY_HIGH: self.db.query(ReviewTask).filter(
                and_(
                    ReviewTask.priority == self.PRIORITY_HIGH,
                    ReviewTask.status.in_([self.STATUS_PENDING, self.STATUS_IN_REVIEW])
                )
            ).count(),
            self.PRIORITY_MEDIUM: self.db.query(ReviewTask).filter(
                and_(
                    ReviewTask.priority == self.PRIORITY_MEDIUM,
                    ReviewTask.status.in_([self.STATUS_PENDING, self.STATUS_IN_REVIEW])
                )
            ).count(),
            self.PRIORITY_LOW: self.db.query(ReviewTask).filter(
                and_(
                    ReviewTask.priority == self.PRIORITY_LOW,
                    ReviewTask.status.in_([self.STATUS_PENDING, self.STATUS_IN_REVIEW])
                )
            ).count(),
        }

        logger.info(f"Queue stats: {stats['total']} total, {stats['overdue']} overdue")
        return stats

    # ==== Helper Methods ====

    def _add_to_history(
        self,
        task: ReviewTask,
        status: str,
        user_id: Optional[str],
        comment: str
    ) -> None:
        """Add entry to task history"""
        history = json.loads(task.history) if task.history else []

        history.append({
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "comment": comment
        })

        task.history = json.dumps(history)

    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get full history of a task

        Args:
            task_id: Task ID

        Returns:
            List of history entries
        """
        task = self.repository.get_by_id(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        return json.loads(task.history) if task.history else []


# Export
__all__ = ["ReviewQueueService"]
