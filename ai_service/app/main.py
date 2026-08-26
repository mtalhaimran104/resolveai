from fastapi import FastAPI
from app.api.routers.classification import (
    router as classification_router,
)
from app.api.routers.priority_prediction import (
    router as priority_router,
)
app = FastAPI(
    title="ResolveAI ML Service",
    description=(
        "AI-powered ticket classification and priority "
        "prediction service for ResolveAI Help Desk."
    ),
    version="1.0.0",
)
@app.get(
    "/health",
    tags=["Health"],
)
def health_check():
    return {
        "status": "healthy",
    }
app.include_router(classification_router)
app.include_router(priority_router)
