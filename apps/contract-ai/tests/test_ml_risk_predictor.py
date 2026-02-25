"""
Tests for ML Risk Predictor

Tests cover:
- Feature extraction
- Risk prediction
- Model training
- Feedback integration
- Edge cases
"""

import pytest
import numpy as np
from datetime import datetime

from src.ml.risk_predictor import (
    MLRiskPredictor,
    RiskLevel,
    ContractFeatureExtractor,
    quick_predict_risk
)


class TestContractFeatureExtractor:
    """Test feature extraction from contract data"""

    def test_basic_feature_extraction(self):
        """Test extraction of basic features"""
        extractor = ContractFeatureExtractor()

        contract_data = {
            'contract_type': 'supply',
            'amount': 1000000,
            'duration_days': 365,
            'has_force_majeure': True,
            'has_liability_limit': False
        }

        features = extractor.extract_features(contract_data)

        assert 'contract_type_code' in features
        assert features['contract_type_code'] == 1.0  # supply = 1.0
        assert 'amount_log' in features
        assert features['amount_log'] == pytest.approx(6.0, rel=0.1)
        assert 'duration_days' in features
        assert features['duration_days'] == 365
        assert 'has_force_majeure' in features
        assert features['has_force_majeure'] == 1.0
        assert features['has_liability_limit'] == 0.0

    def test_feature_count(self):
        """Test that all expected features are extracted"""
        extractor = ContractFeatureExtractor()
        features = extractor.extract_features({})

        # Should extract 25+ features
        assert len(features) >= 25

    def test_edge_case_zero_amount(self):
        """Test handling of zero amount"""
        extractor = ContractFeatureExtractor()
        features = extractor.extract_features({'amount': 0})

        # Should handle gracefully (log10(1) = 0)
        assert features['amount_log'] == 0.0

    def test_edge_case_very_long_duration(self):
        """Test capping of very long duration"""
        extractor = ContractFeatureExtractor()
        features = extractor.extract_features({'duration_days': 10000})

        # Should cap at 3650 (10 years)
        assert features['duration_days'] == 3650

    def test_unknown_contract_type(self):
        """Test handling of unknown contract type"""
        extractor = ContractFeatureExtractor()
        features = extractor.extract_features({'contract_type': 'unknown_type'})

        # Should map to 0.0
        assert features['contract_type_code'] == 0.0


class TestMLRiskPredictor:
    """Test ML Risk Predictor"""

    @pytest.fixture
    def predictor(self):
        """Create predictor instance"""
        return MLRiskPredictor()

    def test_initialization(self, predictor):
        """Test predictor initialization"""
        assert predictor.model is not None
        assert predictor.scaler is not None
        assert predictor.feature_extractor is not None

    def test_prediction_without_training(self, predictor):
        """Test prediction with untrained model (rule-based fallback)"""
        contract_data = {
            'contract_type': 'supply',
            'amount': 1000000,
            'duration_days': 365,
            'has_force_majeure': False,
            'has_liability_limit': False,
            'counterparty_risk_score': 70
        }

        prediction = predictor.predict(contract_data)

        assert isinstance(prediction.risk_level, RiskLevel)
        assert 0.0 <= prediction.confidence <= 1.0
        assert 0.0 <= prediction.risk_score <= 100.0
        assert isinstance(prediction.should_use_llm, bool)
        assert prediction.prediction_time_ms > 0
        assert len(prediction.features_used) >= 25

    def test_high_risk_scenario(self, predictor):
        """Test prediction for high-risk contract"""
        contract_data = {
            'contract_type': 'supply',
            'amount': 10000000,  # High amount
            'duration_days': 1825,  # 5 years
            'has_force_majeure': False,  # Missing
            'has_liability_limit': False,  # Missing
            'has_termination_clause': False,  # Missing
            'counterparty_risk_score': 80,  # High risk
            'historical_disputes': 5,  # Multiple disputes
            'penalty_rate': 0.15  # High penalty
        }

        prediction = predictor.predict(contract_data)

        # Should predict high or critical risk
        assert prediction.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert prediction.risk_score >= 60
        assert prediction.should_use_llm  # High risk should trigger LLM

    def test_low_risk_scenario(self, predictor):
        """Test prediction for low-risk contract"""
        contract_data = {
            'contract_type': 'nda',
            'amount': 0,  # No monetary value
            'duration_days': 365,
            'has_force_majeure': True,
            'has_liability_limit': True,
            'has_termination_clause': True,
            'has_confidentiality': True,
            'counterparty_risk_score': 20,  # Low risk
            'historical_disputes': 0,
            'counterparty_age_years': 10  # Established company
        }

        prediction = predictor.predict(contract_data)

        # Should predict low or minimal risk
        assert prediction.risk_level in [RiskLevel.LOW, RiskLevel.MINIMAL]
        assert prediction.risk_score <= 50
        # Low risk might not need LLM

    def test_prediction_speed(self, predictor):
        """Test that prediction is fast (<100ms)"""
        contract_data = {
            'contract_type': 'service',
            'amount': 500000,
            'duration_days': 180
        }

        prediction = predictor.predict(contract_data)

        # Should be very fast
        assert prediction.prediction_time_ms < 100  # <100ms

    def test_training_with_data(self, predictor):
        """Test model training"""
        # Generate synthetic training data
        training_data = []
        labels = []

        # High risk contracts
        for _ in range(20):
            training_data.append({
                'contract_type': 'supply',
                'amount': 5000000,
                'has_liability_limit': False,
                'counterparty_risk_score': 70
            })
            labels.append('high')

        # Low risk contracts
        for _ in range(30):
            training_data.append({
                'contract_type': 'nda',
                'amount': 0,
                'has_liability_limit': True,
                'counterparty_risk_score': 20
            })
            labels.append('low')

        # Should train without errors
        predictor.train(training_data, labels)

        # Model should now be trained
        assert hasattr(predictor.model, 'predict_proba')

    def test_quick_predict_function(self):
        """Test convenience function"""
        contract_data = {
            'contract_type': 'service',
            'amount': 250000,
            'duration_days': 90
        }

        prediction = quick_predict_risk(contract_data)

        assert isinstance(prediction.risk_level, RiskLevel)
        assert prediction.risk_score >= 0


class TestModelPersistence:
    """Test model saving and loading"""

    def test_model_save_and_load(self, tmp_path):
        """Test saving and loading model"""
        model_path = str(tmp_path / "test_model.pkl")
        scaler_path = str(tmp_path / "test_scaler.pkl")

        # Create and train predictor
        predictor1 = MLRiskPredictor(model_path=model_path)

        training_data = [
            {'contract_type': 'supply', 'amount': 1000000} for _ in range(50)
        ]
        labels = ['high'] * 25 + ['low'] * 25

        predictor1.train(training_data, labels)

        # Create new predictor that should load saved model
        predictor2 = MLRiskPredictor(model_path=model_path)

        # Should have loaded the model
        assert predictor2.model is not None
        assert hasattr(predictor2.model, 'predict_proba')


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_contract_data(self):
        """Test prediction with empty contract data"""
        predictor = MLRiskPredictor()
        prediction = predictor.predict({})

        # Should handle gracefully with defaults
        assert isinstance(prediction.risk_level, RiskLevel)

    def test_missing_features(self):
        """Test prediction with minimal features"""
        predictor = MLRiskPredictor()
        prediction = predictor.predict({
            'contract_type': 'supply'
        })

        # Should fill in defaults
        assert prediction.risk_score >= 0

    def test_invalid_contract_type(self):
        """Test with completely invalid contract type"""
        predictor = MLRiskPredictor()
        prediction = predictor.predict({
            'contract_type': '!@#$%^&*()'
        })

        # Should still produce valid prediction
        assert isinstance(prediction.risk_level, RiskLevel)


class TestFeatureImportance:
    """Test feature importance analysis"""

    def test_get_feature_importance(self):
        """Test getting feature importance from trained model"""
        predictor = MLRiskPredictor()

        # Train model
        training_data = []
        labels = []
        for i in range(100):
            training_data.append({
                'contract_type': 'supply',
                'amount': 1000000 if i % 2 == 0 else 100000,
                'has_liability_limit': i % 2 == 0
            })
            labels.append('high' if i % 2 == 0 else 'low')

        predictor.train(training_data, labels)

        # Get feature importance
        importance = predictor.get_feature_importance()

        assert isinstance(importance, dict)
        assert len(importance) > 0
        # Amount should be important feature
        assert 'amount_log' in importance


class TestRealWorldScenarios:
    """Test real-world contract scenarios"""

    def test_typical_supply_contract(self):
        """Test typical supply contract"""
        predictor = MLRiskPredictor()

        contract_data = {
            'contract_type': 'supply',
            'amount': 500000,
            'duration_days': 180,
            'payment_terms_days': 30,
            'has_force_majeure': True,
            'has_liability_limit': True,
            'has_dispute_resolution': True,
            'counterparty_age_years': 5,
            'historical_contracts': 10,
            'historical_disputes': 0
        }

        prediction = predictor.predict(contract_data)

        # Should be medium risk
        assert prediction.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]

    def test_high_value_long_term_contract(self):
        """Test high-value, long-term contract"""
        predictor = MLRiskPredictor()

        contract_data = {
            'contract_type': 'service',
            'amount': 10000000,
            'duration_days': 1825,  # 5 years
            'payment_terms_days': 60,
            'has_force_majeure': True,
            'has_liability_limit': True,
            'has_termination_clause': True,
            'counterparty_age_years': 15,
            'historical_contracts': 50
        }

        prediction = predictor.predict(contract_data)

        # High value should increase risk
        assert prediction.risk_score >= 40

    def test_nda_contract(self):
        """Test NDA contract"""
        predictor = MLRiskPredictor()

        contract_data = {
            'contract_type': 'nda',
            'amount': 0,
            'duration_days': 730,
            'has_confidentiality': True,
            'has_termination_clause': True
        }

        prediction = predictor.predict(contract_data)

        # NDA typically low risk
        assert prediction.risk_level in [RiskLevel.LOW, RiskLevel.MINIMAL]


# Performance benchmarks
@pytest.mark.benchmark
class TestPerformance:
    """Performance benchmarks"""

    def test_prediction_performance(self, benchmark):
        """Benchmark prediction speed"""
        predictor = MLRiskPredictor()
        contract_data = {
            'contract_type': 'supply',
            'amount': 1000000,
            'duration_days': 365
        }

        result = benchmark(predictor.predict, contract_data)

        # Should be very fast
        assert result.prediction_time_ms < 100

    def test_batch_prediction_performance(self, benchmark):
        """Benchmark batch predictions"""
        predictor = MLRiskPredictor()

        contracts = [
            {
                'contract_type': 'supply',
                'amount': 1000000 * (i + 1),
                'duration_days': 365
            }
            for i in range(100)
        ]

        def batch_predict():
            return [predictor.predict(c) for c in contracts]

        results = benchmark(batch_predict)

        # Should process 100 contracts in reasonable time
        assert len(results) == 100
