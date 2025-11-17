"""AI/ML model endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import numpy as np

from app.ai.model import TradingModel
from app.ai.trainer import ModelTrainer
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])

# Global model instance
_model: Optional[TradingModel] = None


def get_model() -> TradingModel:
    """Get or create model instance."""
    global _model
    if _model is None:
        _model = TradingModel(settings.ai)
        _model.load()
    return _model


class PredictRequest(BaseModel):
    """Prediction request model."""

    features: List[float]
    threshold: Optional[float] = None


class PredictResponse(BaseModel):
    """Prediction response model."""

    is_maker: bool
    probability: float
    confidence: str


class TrainRequest(BaseModel):
    """Training request model."""

    data_path: Optional[str] = None
    test_size: float = 0.2
    random_state: int = 42


class TrainResponse(BaseModel):
    """Training response model."""

    success: bool
    accuracy: float
    message: str


@router.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    """
    Predict whether to use maker order.

    Args:
        request: Prediction request with features

    Returns:
        Prediction result
    """
    try:
        model = get_model()

        if not model.is_loaded():
            raise HTTPException(
                status_code=503, detail="Model not loaded. Please train first."
            )

        features = np.array(request.features)
        is_maker, probability = model.predict(features, request.threshold)

        confidence = "high" if abs(probability - 0.5) > 0.3 else "medium" if abs(probability - 0.5) > 0.1 else "low"

        return PredictResponse(
            is_maker=is_maker,
            probability=probability,
            confidence=confidence,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train", response_model=TrainResponse)
async def train_model(request: TrainRequest) -> TrainResponse:
    """
    Train the XGBoost model.

    Args:
        request: Training request

    Returns:
        Training result
    """
    try:
        trainer = ModelTrainer(settings.ai)
        model, metrics, feature_names = trainer.train_from_csv(
            data_path=request.data_path,
            test_size=request.test_size,
            random_state=request.random_state,
        )

        # Save model
        trading_model = TradingModel(settings.ai)
        trading_model.set_model(model, feature_names)
        trading_model.save()

        # Update global model
        global _model
        _model = trading_model

        return TrainResponse(
            success=True,
            accuracy=metrics["accuracy"],
            message=f"Model trained successfully. Test accuracy: {metrics['accuracy']:.4f}",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Training data not found: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def model_status() -> dict:
    """
    Get model status.

    Returns:
        Model status information
    """
    model = get_model()
    return {
        "loaded": model.is_loaded(),
        "model_path": settings.ai.model_path,
        "feature_count": len(model.feature_names) if model.feature_names else 0,
    }

