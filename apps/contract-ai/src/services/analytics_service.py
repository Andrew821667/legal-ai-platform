"""
Analytics Service for Contract AI System

Provides comprehensive analytics and insights:
- Risk trend analysis
- Cost tracking (LLM usage)
- Productivity metrics (time saved)
- ROI calculation
- Performance benchmarking
- Risk distribution analytics

Features:
- Real-time metrics calculation
- Historical trend analysis
- Predictive analytics
- Export to various formats (JSON, CSV, PDF)
- Integration with ML Risk Predictor

Author: AI Contract System
"""

import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
from enum import Enum
import json

from loguru import logger


class MetricType(str, Enum):
    """Metric type classification"""
    PRODUCTIVITY = "productivity"
    COST = "cost"
    QUALITY = "quality"
    RISK = "risk"
    USER_ENGAGEMENT = "user_engagement"


@dataclass
class AnalyticsMetric:
    """Single analytics metric"""
    name: str
    value: float
    unit: str
    metric_type: MetricType
    timestamp: datetime
    trend: Optional[str] = None  # 'up', 'down', 'stable'
    trend_percentage: Optional[float] = None
    benchmark: Optional[float] = None


@dataclass
class RiskTrend:
    """Risk trend over time"""
    date: datetime
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_contracts: int
    average_risk_score: float


@dataclass
class CostAnalysis:
    """LLM cost analysis"""
    period_start: datetime
    period_end: datetime
    total_cost_usd: float
    llm_calls: int
    tokens_used: int
    cost_per_contract: float
    ml_prediction_savings: float  # Cost saved by using ML predictor
    estimated_monthly_cost: float


@dataclass
class ProductivityMetrics:
    """Productivity metrics"""
    contracts_analyzed: int
    total_time_saved_hours: float
    average_analysis_time_seconds: float
    automated_tasks: int
    manual_tasks_prevented: int
    roi_multiplier: float  # e.g., 5.0 = 5x ROI


@dataclass
class RiskDistribution:
    """Risk distribution by category"""
    category: str
    count: int
    percentage: float
    average_severity: float
    trend: str  # 'increasing', 'decreasing', 'stable'


class AnalyticsService:
    """
    Comprehensive Analytics Service

    Responsibilities:
    1. Collect metrics from all system components
    2. Calculate trends and aggregations
    3. Generate insights and recommendations
    4. Provide data for dashboard visualization
    5. Export analytics reports
    """

    def __init__(self, db_session=None):
        self.db_session = db_session

        # Metrics storage (in-memory cache)
        self.metrics_cache: Dict[str, List[AnalyticsMetric]] = defaultdict(list)

        # Load historical data
        self._load_historical_metrics()

    def _load_historical_metrics(self):
        """Load historical metrics from database"""
        try:
            from ..models import AnalyticsMetricLog
            from datetime import datetime, timedelta

            # Load metrics from last 90 days
            cutoff_date = datetime.utcnow() - timedelta(days=90)

            recent_metrics = self.db_session.query(AnalyticsMetricLog).filter(
                AnalyticsMetricLog.timestamp >= cutoff_date
            ).order_by(AnalyticsMetricLog.timestamp.desc()).limit(10000).all()

            # Group metrics by name
            for metric in recent_metrics:
                self.metrics_cache[metric.metric_name].append({
                    'value': metric.value,
                    'timestamp': metric.timestamp,
                    'user_id': metric.user_id,
                    'extra_metadata': metric.extra_metadata
                })

            logger.info(f"📊 Analytics Service initialized - loaded {len(recent_metrics)} historical metrics")

        except Exception as e:
            logger.warning(f"Could not load historical metrics: {e}")
            logger.info("📊 Analytics Service initialized - using in-memory cache only")

    def get_dashboard_summary(
        self,
        user_id: Optional[str] = None,
        period_days: int = 30
    ) -> Dict:
        """
        Get dashboard summary with key metrics

        Returns:
            Dictionary with:
            - headline_metrics: Quick stats (contracts, time saved, etc.)
            - risk_trends: Risk trends over time
            - cost_analysis: Cost breakdown
            - productivity: Productivity metrics
            - top_risks: Most common risks
            - recommendations: Actionable insights
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Calculate all metrics
        headline = self._calculate_headline_metrics(start_date, end_date, user_id)
        risk_trends = self._calculate_risk_trends(start_date, end_date, user_id)
        costs = self._calculate_cost_analysis(start_date, end_date, user_id)
        productivity = self._calculate_productivity_metrics(start_date, end_date, user_id)
        top_risks = self._get_top_risks(start_date, end_date, user_id, limit=10)
        risk_distribution = self._calculate_risk_distribution(start_date, end_date, user_id)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            headline, risk_trends, costs, productivity
        )

        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': period_days
            },
            'headline_metrics': {k: asdict(v) for k, v in headline.items()},
            'risk_trends': [asdict(t) for t in risk_trends],
            'cost_analysis': asdict(costs),
            'productivity': asdict(productivity),
            'top_risks': top_risks,
            'risk_distribution': [asdict(r) for r in risk_distribution],
            'recommendations': recommendations,
            'generated_at': datetime.now().isoformat()
        }

    def _calculate_headline_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str]
    ) -> Dict[str, AnalyticsMetric]:
        """Calculate headline metrics for dashboard cards"""

        # Mock data for demonstration
        # In production, query database

        total_contracts = 127
        time_saved_hours = 847.5
        cost_saved_usd = 12450.0
        acceptance_rate = 0.94  # 94% of recommendations accepted

        # Calculate trends (comparison to previous period)
        previous_period_days = (end_date - start_date).days
        comparison_start = start_date - timedelta(days=previous_period_days)

        # Mock previous period data
        previous_contracts = 98
        previous_time_saved = 654.0

        contracts_trend = ((total_contracts - previous_contracts) / previous_contracts) * 100
        time_saved_trend = ((time_saved_hours - previous_time_saved) / previous_time_saved) * 100

        metrics = {
            'total_contracts': AnalyticsMetric(
                name="Total Contracts Analyzed",
                value=total_contracts,
                unit="contracts",
                metric_type=MetricType.PRODUCTIVITY,
                timestamp=end_date,
                trend="up" if contracts_trend > 0 else "down",
                trend_percentage=abs(contracts_trend)
            ),
            'time_saved': AnalyticsMetric(
                name="Time Saved",
                value=time_saved_hours,
                unit="hours",
                metric_type=MetricType.PRODUCTIVITY,
                timestamp=end_date,
                trend="up" if time_saved_trend > 0 else "down",
                trend_percentage=abs(time_saved_trend),
                benchmark=800.0  # Monthly target
            ),
            'cost_saved': AnalyticsMetric(
                name="Cost Saved",
                value=cost_saved_usd,
                unit="USD",
                metric_type=MetricType.COST,
                timestamp=end_date,
                trend="up",
                trend_percentage=18.5
            ),
            'acceptance_rate': AnalyticsMetric(
                name="Recommendation Acceptance Rate",
                value=acceptance_rate * 100,
                unit="%",
                metric_type=MetricType.QUALITY,
                timestamp=end_date,
                trend="stable",
                trend_percentage=2.1,
                benchmark=90.0
            ),
            'average_risk_score': AnalyticsMetric(
                name="Average Risk Score",
                value=42.3,
                unit="score",
                metric_type=MetricType.RISK,
                timestamp=end_date,
                trend="down",  # Lower risk is better
                trend_percentage=8.2
            )
        }

        return metrics

    def _calculate_risk_trends(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str]
    ) -> List[RiskTrend]:
        """Calculate risk trends over time (daily/weekly)"""

        # Mock data - in production, query database
        trends = []
        current_date = start_date

        while current_date <= end_date:
            # Mock risk distribution
            total = 15
            critical = max(1, int(total * 0.05))  # 5% critical
            high = max(2, int(total * 0.15))      # 15% high
            medium = max(5, int(total * 0.40))    # 40% medium
            low = total - critical - high - medium

            avg_risk = (
                critical * 90 +
                high * 70 +
                medium * 45 +
                low * 20
            ) / total

            trends.append(RiskTrend(
                date=current_date,
                critical_count=critical,
                high_count=high,
                medium_count=medium,
                low_count=low,
                total_contracts=total,
                average_risk_score=avg_risk
            ))

            current_date += timedelta(days=7)  # Weekly data points

        return trends

    def _calculate_cost_analysis(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str]
    ) -> CostAnalysis:
        """Calculate LLM cost analysis"""

        # Mock data
        llm_calls = 847
        tokens_used = 4_235_000
        cost_per_1k_tokens = 0.01  # GPT-4 Turbo pricing

        total_cost = (tokens_used / 1000) * cost_per_1k_tokens

        # ML predictor savings (60% of contracts use ML instead of LLM)
        ml_prediction_rate = 0.60
        ml_savings = total_cost * ml_prediction_rate / (1 - ml_prediction_rate)

        contracts_analyzed = 127
        cost_per_contract = total_cost / contracts_analyzed

        # Estimate monthly cost
        days_in_period = (end_date - start_date).days
        estimated_monthly = (total_cost / days_in_period) * 30

        return CostAnalysis(
            period_start=start_date,
            period_end=end_date,
            total_cost_usd=round(total_cost, 2),
            llm_calls=llm_calls,
            tokens_used=tokens_used,
            cost_per_contract=round(cost_per_contract, 2),
            ml_prediction_savings=round(ml_savings, 2),
            estimated_monthly_cost=round(estimated_monthly, 2)
        )

    def _calculate_productivity_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str]
    ) -> ProductivityMetrics:
        """Calculate productivity metrics"""

        contracts_analyzed = 127

        # Average time savings per contract
        # Manual review: ~8 hours per contract
        # AI-assisted review: ~1.5 hours per contract
        # Time saved: 6.5 hours per contract
        time_saved_per_contract = 6.5
        total_time_saved = contracts_analyzed * time_saved_per_contract

        # Average AI analysis time
        average_analysis_time = 45.0  # seconds

        # Automated tasks (no human intervention needed)
        automated_tasks = int(contracts_analyzed * 0.30)  # 30% fully automated

        # Manual tasks prevented
        manual_tasks_prevented = contracts_analyzed * 8  # 8 manual tasks per contract

        # ROI calculation
        # Cost of AI system: $500/month
        # Value of time saved: $50/hour * total_time_saved
        ai_system_cost = 500
        hourly_rate = 50
        value_of_time_saved = hourly_rate * total_time_saved
        roi_multiplier = value_of_time_saved / ai_system_cost if ai_system_cost > 0 else 0

        return ProductivityMetrics(
            contracts_analyzed=contracts_analyzed,
            total_time_saved_hours=round(total_time_saved, 1),
            average_analysis_time_seconds=average_analysis_time,
            automated_tasks=automated_tasks,
            manual_tasks_prevented=manual_tasks_prevented,
            roi_multiplier=round(roi_multiplier, 1)
        )

    def _get_top_risks(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str],
        limit: int = 10
    ) -> List[Dict]:
        """Get most common risks detected"""

        # Mock data
        top_risks = [
            {
                'risk_type': 'Unlimited Liability',
                'count': 23,
                'severity': 'high',
                'avg_impact_score': 85.2,
                'trend': 'increasing'
            },
            {
                'risk_type': 'Missing Force Majeure Clause',
                'count': 18,
                'severity': 'medium',
                'avg_impact_score': 62.5,
                'trend': 'stable'
            },
            {
                'risk_type': 'Unclear Payment Terms',
                'count': 15,
                'severity': 'medium',
                'avg_impact_score': 58.3,
                'trend': 'decreasing'
            },
            {
                'risk_type': 'No Termination Clause',
                'count': 12,
                'severity': 'high',
                'avg_impact_score': 71.0,
                'trend': 'stable'
            },
            {
                'risk_type': 'Excessive Penalties',
                'count': 11,
                'severity': 'critical',
                'avg_impact_score': 92.5,
                'trend': 'decreasing'
            },
            {
                'risk_type': 'Unclear Scope of Work',
                'count': 9,
                'severity': 'medium',
                'avg_impact_score': 55.8,
                'trend': 'stable'
            },
            {
                'risk_type': 'Missing Confidentiality Clause',
                'count': 8,
                'severity': 'medium',
                'avg_impact_score': 48.2,
                'trend': 'decreasing'
            },
            {
                'risk_type': 'Automatic Renewal Without Notice',
                'count': 7,
                'severity': 'medium',
                'avg_impact_score': 53.5,
                'trend': 'stable'
            },
            {
                'risk_type': 'One-Sided Dispute Resolution',
                'count': 6,
                'severity': 'high',
                'avg_impact_score': 78.0,
                'trend': 'stable'
            },
            {
                'risk_type': 'Unreasonable Warranty Period',
                'count': 5,
                'severity': 'low',
                'avg_impact_score': 35.2,
                'trend': 'decreasing'
            }
        ]

        return top_risks[:limit]

    def _calculate_risk_distribution(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[str]
    ) -> List[RiskDistribution]:
        """Calculate risk distribution by category"""

        # Mock data
        categories = {
            'Financial': (45, 68.5, 'stable'),
            'Legal': (38, 72.3, 'decreasing'),
            'Operational': (32, 58.2, 'stable'),
            'Reputational': (12, 45.8, 'increasing'),
            'Compliance': (18, 81.2, 'decreasing')
        }

        total_risks = sum(count for count, _, _ in categories.values())

        distributions = []
        for category, (count, avg_severity, trend) in categories.items():
            distributions.append(RiskDistribution(
                category=category,
                count=count,
                percentage=round((count / total_risks) * 100, 1),
                average_severity=avg_severity,
                trend=trend
            ))

        # Sort by count descending
        distributions.sort(key=lambda x: x.count, reverse=True)

        return distributions

    def _generate_recommendations(
        self,
        headline: Dict[str, AnalyticsMetric],
        risk_trends: List[RiskTrend],
        costs: CostAnalysis,
        productivity: ProductivityMetrics
    ) -> List[Dict[str, str]]:
        """Generate actionable recommendations based on analytics"""

        recommendations = []

        # ROI recommendation
        if productivity.roi_multiplier >= 10:
            recommendations.append({
                'type': 'success',
                'title': 'Excellent ROI',
                'message': f'System is delivering {productivity.roi_multiplier:.1f}x ROI! '
                          f'Consider expanding usage to more teams.',
                'priority': 'low'
            })
        elif productivity.roi_multiplier < 3:
            recommendations.append({
                'type': 'warning',
                'title': 'Low ROI',
                'message': f'Current ROI is {productivity.roi_multiplier:.1f}x. '
                          f'Consider reviewing usage patterns and training users.',
                'priority': 'high'
            })

        # Cost optimization
        ml_savings_percentage = (costs.ml_prediction_savings / costs.total_cost_usd) * 100
        if ml_savings_percentage < 40:
            recommendations.append({
                'type': 'info',
                'title': 'Cost Optimization Opportunity',
                'message': f'ML predictor is saving {ml_savings_percentage:.0f}% of LLM costs. '
                          f'Training with more data could increase savings to 60%+.',
                'priority': 'medium'
            })

        # Risk trends
        if risk_trends:
            latest_trend = risk_trends[-1]
            critical_percentage = (latest_trend.critical_count / latest_trend.total_contracts) * 100

            if critical_percentage > 10:
                recommendations.append({
                    'type': 'warning',
                    'title': 'High Critical Risk Rate',
                    'message': f'{critical_percentage:.0f}% of contracts have critical risks. '
                              f'Review template library and approval workflows.',
                    'priority': 'high'
                })

        # Acceptance rate
        acceptance_metric = headline.get('acceptance_rate')
        if acceptance_metric and acceptance_metric.value < 85:
            recommendations.append({
                'type': 'warning',
                'title': 'Low Recommendation Acceptance',
                'message': f'Only {acceptance_metric.value:.0f}% of AI recommendations are accepted. '
                          f'Consider retraining models or reviewing recommendation quality.',
                'priority': 'high'
            })

        # Productivity gains
        if productivity.total_time_saved_hours < 500:
            recommendations.append({
                'type': 'info',
                'title': 'Increase System Adoption',
                'message': f'Only {productivity.total_time_saved_hours:.0f} hours saved this period. '
                          f'Promote system usage to realize more value.',
                'priority': 'medium'
            })

        # Default recommendation if all is well
        if not recommendations:
            recommendations.append({
                'type': 'success',
                'title': 'System Performing Well',
                'message': 'All metrics are within expected ranges. Continue current usage patterns.',
                'priority': 'low'
            })

        return recommendations

    def export_analytics_report(
        self,
        format: str = 'json',
        period_days: int = 30,
        user_id: Optional[str] = None
    ) -> str:
        """
        Export analytics report

        Args:
            format: 'json', 'csv', or 'pdf'
            period_days: Number of days to include
            user_id: Optional user ID for filtering

        Returns:
            File path to generated report
        """
        dashboard_data = self.get_dashboard_summary(user_id, period_days)

        output_dir = "reports/analytics"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analytics_report_{timestamp}.{format}"
        filepath = os.path.join(output_dir, filename)

        if format == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False, default=str)

        elif format == 'csv':
            # Flatten data to CSV
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write headline metrics
                writer.writerow(['Metric', 'Value', 'Unit', 'Trend', 'Trend %'])
                for metric in dashboard_data['headline_metrics'].values():
                    writer.writerow([
                        metric['name'],
                        metric['value'],
                        metric['unit'],
                        metric.get('trend'),
                        metric.get('trend_percentage')
                    ])

        elif format == 'pdf':
            # Generate PDF report with charts
            import io
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, Image, KeepTogether
            )
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
            import plotly.graph_objects as go

            logger.info("📄 Generating PDF report with charts...")

            # Create PDF document
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()

            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#3B82F6'),
                spaceAfter=30,
                alignment=TA_CENTER
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#1E40AF'),
                spaceAfter=12,
                spaceBefore=20
            )

            # Title
            story.append(Paragraph("📊 Analytics Report", title_style))
            story.append(Paragraph(
                f"Period: {dashboard_data['period']['start'][:10]} to {dashboard_data['period']['end'][:10]}",
                styles['Normal']
            ))
            story.append(Spacer(1, 0.3*inch))

            # Headline Metrics
            story.append(Paragraph("Key Metrics", heading_style))

            metrics_data = [['Metric', 'Value', 'Unit', 'Trend']]
            for metric_name, metric in dashboard_data['headline_metrics'].items():
                trend_text = f"{metric.get('trend_percentage', 0):+.1f}%" if metric.get('trend_percentage') else 'N/A'
                metrics_data.append([
                    metric['name'],
                    str(metric['value']),
                    metric['unit'],
                    trend_text
                ])

            metrics_table = Table(metrics_data, colWidths=[3*inch, 1.5*inch, 1*inch, 1*inch])
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(metrics_table)
            story.append(Spacer(1, 0.3*inch))

            # Risk Trends Chart
            if dashboard_data.get('risk_trends'):
                story.append(Paragraph("Risk Trends Over Time", heading_style))

                try:
                    # Create plotly chart
                    risk_data = dashboard_data['risk_trends']
                    dates = [r['date'] for r in risk_data]
                    critical = [r['critical'] for r in risk_data]
                    high = [r['high'] for r in risk_data]
                    medium = [r['medium'] for r in risk_data]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=dates, y=critical, name='Critical', line=dict(color='red')))
                    fig.add_trace(go.Scatter(x=dates, y=high, name='High', line=dict(color='orange')))
                    fig.add_trace(go.Scatter(x=dates, y=medium, name='Medium', line=dict(color='yellow')))

                    fig.update_layout(
                        title='Risk Levels Trend',
                        xaxis_title='Date',
                        yaxis_title='Count',
                        height=400,
                        width=700
                    )

                    # Export to image
                    img_bytes = fig.to_image(format="png", width=700, height=400)
                    img_buffer = io.BytesIO(img_bytes)
                    img = Image(img_buffer, width=6*inch, height=3.4*inch)
                    story.append(img)
                    story.append(Spacer(1, 0.2*inch))

                except Exception as e:
                    logger.warning(f"Could not generate risk trends chart: {e}")
                    story.append(Paragraph("(Chart generation skipped)", styles['Italic']))

            # Top Risks
            story.append(PageBreak())
            story.append(Paragraph("Top Identified Risks", heading_style))

            if dashboard_data.get('top_risks'):
                risks_data = [['Risk', 'Severity', 'Count']]
                for risk in dashboard_data['top_risks'][:10]:
                    risks_data.append([
                        risk.get('risk_type', 'Unknown'),
                        risk.get('severity', 'N/A'),
                        str(risk.get('count', 0))
                    ])

                risks_table = Table(risks_data, colWidths=[4*inch, 1.5*inch, 1*inch])
                risks_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DC2626')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(risks_table)

            story.append(Spacer(1, 0.3*inch))

            # Cost Analysis
            if dashboard_data.get('cost_analysis'):
                story.append(Paragraph("Cost Analysis", heading_style))
                cost_data = dashboard_data['cost_analysis']

                cost_info = [
                    ['Total LLM Cost', f"${cost_data.get('total_cost', 0):.2f}"],
                    ['Total Tokens Used', f"{cost_data.get('total_tokens', 0):,}"],
                    ['Average Cost per Contract', f"${cost_data.get('cost_per_contract', 0):.2f}"],
                    ['Cost Saved', f"${cost_data.get('cost_saved', 0):.2f}"],
                ]

                cost_table = Table(cost_info, colWidths=[4*inch, 2.5*inch])
                cost_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey)
                ]))
                story.append(cost_table)

            story.append(Spacer(1, 0.3*inch))

            # Recommendations
            if dashboard_data.get('recommendations'):
                story.append(PageBreak())
                story.append(Paragraph("💡 Recommendations", heading_style))

                for i, rec in enumerate(dashboard_data['recommendations'], 1):
                    rec_text = f"<b>{i}.</b> {rec}"
                    story.append(Paragraph(rec_text, styles['Normal']))
                    story.append(Spacer(1, 0.1*inch))

            # Footer
            story.append(Spacer(1, 0.5*inch))
            story.append(Paragraph(
                f"Generated at: {dashboard_data['generated_at']}",
                styles['Italic']
            ))
            story.append(Paragraph(
                "Contract AI System - Analytics Report",
                styles['Italic']
            ))

            # Build PDF
            doc.build(story)
            logger.info(f"✅ PDF report generated successfully: {filepath}")

        logger.info(f"📄 Analytics report exported: {filepath}")
        return filepath

    def track_metric(
        self,
        name: str,
        value: float,
        unit: str,
        metric_type: MetricType,
        user_id: Optional[str] = None,
        contract_id: Optional[int] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Track a custom metric

        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            metric_type: Type of metric
            user_id: Optional user ID for filtering
            contract_id: Optional contract ID for context
            metadata: Optional additional metadata
        """
        metric = AnalyticsMetric(
            name=name,
            value=value,
            unit=unit,
            metric_type=metric_type,
            timestamp=datetime.now()
        )

        self.metrics_cache[name].append(metric)

        # Persist to database
        try:
            from ..models import AnalyticsMetricLog

            log_entry = AnalyticsMetricLog(
                metric_name=name,
                metric_type=metric_type.value,
                value=value,
                unit=unit,
                user_id=user_id,
                contract_id=contract_id,
                extra_metadata=metadata,
                timestamp=datetime.now()
            )

            self.db_session.add(log_entry)
            self.db_session.commit()

            logger.debug(f"📊 Tracked and persisted metric: {name} = {value} {unit}")

        except Exception as e:
            logger.warning(f"Could not persist metric to database: {e}")
            logger.debug(f"📊 Tracked metric (in-memory only): {name} = {value} {unit}")


# Singleton instance
_analytics_instance = None


def get_analytics_service(db_session=None) -> AnalyticsService:
    """Get singleton analytics service instance"""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = AnalyticsService(db_session)
    return _analytics_instance
