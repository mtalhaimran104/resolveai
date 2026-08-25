from pathlib import Path
import joblib
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = (
    BASE_DIR
    / "models"
    / "priority_prediction"
)
MODEL_PATH = (
    MODEL_DIR
    / "priority_prediction_model.pkl"
)
VECTORIZER_PATH = (
    MODEL_DIR
    / "tfidf_vectorizer.pkl"
)
def load_priority_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Priority model not found: "
            f"{MODEL_PATH}"
        )
    if not VECTORIZER_PATH.exists():
        raise FileNotFoundError(
            f"Priority vectorizer not found: "
            f"{VECTORIZER_PATH}"
        )
    try:
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(
            VECTORIZER_PATH
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to load priority "
            "model artifacts."
        ) from exc
    return model, vectorizer
priority_model, priority_vectorizer = (
    load_priority_model()
)
def predict_priority(
    text: str,
) -> tuple[str, float]:
    text_tfidf = priority_vectorizer.transform(
        [text]
    )
    prediction = priority_model.predict(
        text_tfidf
    )
    probabilities = priority_model.predict_proba(
        text_tfidf
    )
    confidence = round(
        float(
            probabilities[0].max() * 100
        ),
        2,
    )
    return (
        str(prediction[0]),
        confidence,
    )
