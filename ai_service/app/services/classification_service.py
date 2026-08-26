from pathlib import Path
import joblib
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = (
    BASE_DIR
    / "models"
    / "ticket_classification"
)
MODEL_PATH = (
    MODEL_DIR
    / "ticket_classification_model.pkl"
)
VECTORIZER_PATH = (
    MODEL_DIR
    / "tfidf_vectorizer.pkl"
)
def load_classification_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Classification model not found: "
            f"{MODEL_PATH}"
        )
    if not VECTORIZER_PATH.exists():
        raise FileNotFoundError(
            f"Classification vectorizer not found: "
            f"{VECTORIZER_PATH}"
        )
    try:
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(
            VECTORIZER_PATH
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to load classification "
            "model artifacts."
        ) from exc
    return model, vectorizer
model, vectorizer = load_classification_model()
def classify_ticket(
    text: str,
) -> tuple[str, float]:
    transformed_text = vectorizer.transform(
        [text]
    )
    prediction = model.predict(
        transformed_text
    )
    probabilities = model.predict_proba(
        transformed_text
    )
    confidence = round(
        float(probabilities[0].max() * 100),
        2,
    )
    return (
        str(prediction[0]),
        confidence,
    )
