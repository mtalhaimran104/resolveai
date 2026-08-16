from pathlib import Path
import joblib


BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = BASE_DIR / "models"

VECTORIZER_PATH = MODEL_DIR / "tfidf_vectorizer.pkl"
MODEL_PATH = MODEL_DIR / "ticket_classification_model.pkl"


vectorizer = joblib.load(VECTORIZER_PATH)
model = joblib.load(MODEL_PATH)


def classify_ticket(text: str) -> str:
    transformed_text = vectorizer.transform([text])
    prediction = model.predict(transformed_text)

    return prediction[0]

