# app/main.py

from fastapi import FastAPI

from app.api.routers import (
    classification,
    priority_prediction,
    faq,
    sentiment,
    summarization,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="ResolveAI AI Service",
    description=(
        "AI-powered student support service "
        "for The Islamia University of Bahawalpur"
    ),
    version="2.0.0",
)


# ============================================================
# AI ENDPOINTS
# ============================================================

app.include_router(
    classification.router
)

app.include_router(
    priority_prediction.router
)

app.include_router(
    faq.router
)

app.include_router(
    sentiment.router
)

app.include_router(
    summarization.router
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ResolveAI AI Service"
    }


# ============================================================
# TEST ENDPOINT
# ============================================================

@app.get("/hello")
def hello():
    return {
        "message": "Hello World"
    }


