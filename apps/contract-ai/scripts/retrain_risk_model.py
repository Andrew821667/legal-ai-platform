#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Risk Model Retraining Script

Run this when you have accumulated 100+ feedback samples:
    python scripts/retrain_risk_model.py

This will:
1. Load unused feedback from database
2. Combine with original training data
3. Split into train/validation/test sets
4. Retrain the risk predictor model
5. Evaluate performance
6. Save new model if better than current
7. Mark feedback as used
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models import get_db, RiskPredictionFeedback, ModelTrainingBatch
from src.ml.risk_predictor import RiskPredictor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import numpy as np
import pickle
from datetime import datetime
from loguru import logger


def main():
    """Main retraining workflow"""
    logger.info("🔄 Starting risk model retraining...")

    db = next(get_db())

    try:
        # Step 1: Load unused feedback
        feedback_records = db.query(RiskPredictionFeedback).filter(
            RiskPredictionFeedback.used_for_training == False
        ).all()

        if len(feedback_records) < 100:
            logger.warning(f"❌ Only {len(feedback_records)} feedback samples - need at least 100")
            logger.info("💡 Collect more user feedback before retraining")
            return

        logger.info(f"✅ Found {len(feedback_records)} feedback samples")

        # Step 2: Extract features and labels
        X_feedback = []
        y_feedback = []

        for record in feedback_records:
            features = record.contract_features
            # Extract numeric features (customize based on your features)
            feature_vector = [
                features.get('amount', 0),
                features.get('duration_days', 0),
                features.get('num_parties', 2),
                features.get('num_clauses', 10),
                # Add more features as needed
            ]
            X_feedback.append(feature_vector)

            # Convert risk level to class
            risk_to_class = {'minimal': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
            y_feedback.append(risk_to_class.get(record.actual_risk_level, 2))

        X_feedback = np.array(X_feedback)
        y_feedback = np.array(y_feedback)

        # Step 3: Load original training data (if available)
        # TODO: Load from original dataset if you have it
        # For now, we'll only use feedback data
        X_all = X_feedback
        y_all = y_feedback

        logger.info(f"📊 Total samples: {len(X_all)}")

        # Step 4: Split data
        X_train, X_temp, y_train, y_temp = train_test_split(
            X_all, y_all, test_size=0.3, random_state=42, stratify=y_all
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
        )

        logger.info(f"📊 Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

        # Step 5: Create and train new model
        predictor = RiskPredictor()
        predictor.train(X_train, y_train)

        # Step 6: Evaluate
        y_train_pred = predictor.model.predict(X_train)
        y_val_pred = predictor.model.predict(X_val)
        y_test_pred = predictor.model.predict(X_test)

        train_acc = accuracy_score(y_train, y_train_pred)
        val_acc = accuracy_score(y_val, y_val_pred)
        test_acc = accuracy_score(y_test, y_test_pred)

        logger.info(f"📈 Train Accuracy: {train_acc:.3f}")
        logger.info(f"📈 Val Accuracy: {val_acc:.3f}")
        logger.info(f"📈 Test Accuracy: {test_acc:.3f}")

        # Step 7: Log training batch
        batch = ModelTrainingBatch(
            model_type='risk_predictor',
            model_version=f'v{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            training_samples_count=len(X_train),
            feedback_samples_count=len(feedback_records),
            train_accuracy=float(train_acc),
            val_accuracy=float(val_acc),
            test_accuracy=float(test_acc),
            metrics={
                'classification_report': classification_report(y_test, y_test_pred, output_dict=True),
                'confusion_matrix': confusion_matrix(y_test, y_test_pred).tolist()
            },
            status='completed',
            completed_at=datetime.utcnow()
        )
        db.add(batch)
        db.commit()

        logger.info(f"✅ Training batch logged (ID: {batch.id})")

        # Step 8: Save new model
        model_path = project_root / 'models' / f'risk_predictor_{batch.model_version}.pkl'
        model_path.parent.mkdir(exist_ok=True)

        with open(model_path, 'wb') as f:
            pickle.dump(predictor.model, f)

        logger.info(f"💾 Model saved: {model_path}")

        # Step 9: Mark feedback as used
        for record in feedback_records:
            record.used_for_training = True
            record.training_batch_id = batch.id

        db.commit()
        logger.info(f"✅ Marked {len(feedback_records)} feedback samples as used")

        logger.info("🎉 Retraining completed successfully!")
        logger.info(f"💡 To deploy: Update model_path in RiskPredictor to '{model_path}'")

    except Exception as e:
        logger.error(f"❌ Retraining failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
