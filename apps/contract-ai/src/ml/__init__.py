"""
Machine Learning Module for Contract AI System

Components:
- risk_predictor: ML-based fast risk assessment
- model_trainer: Training pipeline for ML models
- feature_engineering: Advanced feature extraction
"""

from .risk_predictor import (
    MLRiskPredictor,
    RiskPrediction,
    RiskLevel,
    ContractFeatureExtractor,
    quick_predict_risk
)

__all__ = [
    'MLRiskPredictor',
    'RiskPrediction',
    'RiskLevel',
    'ContractFeatureExtractor',
    'quick_predict_risk'
]
