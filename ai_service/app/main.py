from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers import article_faq
from app.api.routers import (
    classification,
    priority_prediction,
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
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AI ENDPOINTS
# ============================================================

app.include_router(classification.router)
app.include_router(priority_prediction.router)
app.include_router(faq.router)
app.include_router(sentiment.router)
app.include_router(summarization.router)
app.include_router(student_query.router)
app.include_router(article_faq.router)

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
