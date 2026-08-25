# app/main.py

from fastapi import FastAPI

from app.api.routers import (
    faq,
    sentiment,
    summarization,
    student_query,
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
# PUBLIC AI ENDPOINTS
# ============================================================

app.include_router(
    faq.router
)

app.include_router(
    sentiment.router
)

app.include_router(
    summarization.router
)

app.include_router(
    student_query.router
)


# ============================================================
# TEST ENDPOINT
# ============================================================

@app.get("/hello")
def hello():
    return {
        "message": "Hello World"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "ResolveAI AI Service"
    }