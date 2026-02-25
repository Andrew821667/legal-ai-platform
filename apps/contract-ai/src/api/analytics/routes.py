"""
Analytics API Endpoints

Provides access to analytics dashboard data, metrics, and insights.

Endpoints:
- GET /api/v1/analytics/dashboard - Get dashboard summary
- GET /api/v1/analytics/risks/trends - Get risk trends
- GET /api/v1/analytics/costs - Get cost analysis
- GET /api/v1/analytics/productivity - Get productivity metrics
- POST /api/v1/analytics/export - Export analytics report
- POST /api/v1/analytics/track - Track custom metric

Author: AI Contract System
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.services.analytics_service import get_analytics_service, MetricType
from src.services.auth_service import AuthService
from src.models.database import User, SessionLocal


# Router
router = APIRouter(tags=["analytics"])


# Request/Response Models
class DashboardRequest(BaseModel):
    """Dashboard request"""
    period_days: int = Field(default=30, ge=1, le=365)
    user_id: Optional[str] = None


class DashboardResponse(BaseModel):
    """Dashboard response with all analytics data"""
    period: dict
    headline_metrics: dict
    risk_trends: list
    cost_analysis: dict
    productivity: dict
    top_risks: list
    risk_distribution: list
    recommendations: list
    generated_at: str


class TrackMetricRequest(BaseModel):
    """Track custom metric request"""
    name: str = Field(..., min_length=1, max_length=100)
    value: float
    unit: str = Field(..., min_length=1, max_length=20)
    metric_type: MetricType


class ExportRequest(BaseModel):
    """Export analytics report request"""
    format: str = Field(default='json', regex='^(json|csv|pdf)$')
    period_days: int = Field(default=30, ge=1, le=365)
    user_id: Optional[str] = None


# Dependency: Get current user
def get_current_user(token: str = Query(...)) -> User:
    """Get current authenticated user"""
    db = SessionLocal()
    try:
        auth_service = AuthService(db)
        user, error = auth_service.verify_access_token(token, db)
        if error:
            raise HTTPException(status_code=401, detail=error)
        return user
    finally:
        db.close()


# Dependency: Get DB session
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Endpoints

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Get analytics dashboard summary

    Returns comprehensive analytics including:
    - Headline metrics (contracts, time saved, costs)
    - Risk trends over time
    - Cost analysis (LLM usage)
    - Productivity metrics
    - Top 10 risks
    - Risk distribution by category
    - Actionable recommendations

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    dashboard_data = analytics.get_dashboard_summary(
        user_id=current_user.id,
        period_days=period_days
    )

    return dashboard_data


@router.get("/risks/trends")
async def get_risk_trends(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Get risk trends over time

    Returns daily/weekly risk statistics including count by severity level.

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    # Use internal method to get just risk trends
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    trends = analytics._calculate_risk_trends(start_date, end_date, current_user.id)

    return {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'days': period_days
        },
        'trends': [asdict(t) for t in trends]
    }


@router.get("/costs")
async def get_cost_analysis(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Get cost analysis (LLM usage, ML savings)

    Returns:
    - Total LLM costs
    - Token usage
    - ML predictor savings
    - Cost per contract
    - Estimated monthly cost

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    costs = analytics._calculate_cost_analysis(start_date, end_date, current_user.id)

    return asdict(costs)


@router.get("/productivity")
async def get_productivity_metrics(
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Get productivity metrics

    Returns:
    - Contracts analyzed
    - Time saved (hours)
    - ROI multiplier
    - Automated tasks count
    - Average analysis time

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    productivity = analytics._calculate_productivity_metrics(
        start_date, end_date, current_user.id
    )

    return asdict(productivity)


@router.post("/export")
async def export_analytics(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Export analytics report

    Generates downloadable report in requested format (JSON, CSV, PDF).

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    try:
        filepath = analytics.export_analytics_report(
            format=request.format,
            period_days=request.period_days,
            user_id=current_user.id
        )

        if not filepath or not os.path.exists(filepath):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate {request.format.upper()} report"
            )

        # Return file for download
        return FileResponse(
            path=filepath,
            filename=os.path.basename(filepath),
            media_type=f"application/{request.format}"
        )

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/track")
async def track_metric(
    request: TrackMetricRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Track custom metric

    Allows tracking of custom business metrics for analytics.

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    analytics.track_metric(
        name=request.name,
        value=request.value,
        unit=request.unit,
        metric_type=request.metric_type
    )

    return {
        'success': True,
        'message': f'Metric "{request.name}" tracked successfully'
    }


@router.get("/top-risks")
async def get_top_risks(
    limit: int = Query(default=10, ge=1, le=50),
    period_days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Get most common risks detected

    Returns top N risks by frequency with severity and trend information.

    **Access:** Requires authentication
    """
    analytics = get_analytics_service(db)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_days)

    top_risks = analytics._get_top_risks(
        start_date, end_date, current_user.id, limit=limit
    )

    return {
        'period': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'top_risks': top_risks
    }


# Import needed for datetime
from datetime import timedelta
from dataclasses import asdict
import os
from loguru import logger
