import joblib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "priority_prediction" / "priority_prediction_model.pkl"
VECTORIZER_PATH = BASE_DIR / "models" / "priority_prediction" / "tfidf_vectorizer.pkl"

priority_model = joblib.load(MODEL_PATH)
priority_vectorizer = joblib.load(VECTORIZER_PATH)

def predict_priority(text: str) -> str:
    text_tfidf = priority_vectorizer.transform([text])
    prediction = priority_model.predict(text_tfidf)
    return prediction[0]
