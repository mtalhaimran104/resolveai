from pathlib import Path
import json
import json
import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.svm import LinearSVC
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "support_tickets_combined.csv"
)
MODEL_DIR = (
    PROJECT_ROOT
    / "ai_service"
    / "app"
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
METRICS_PATH = (
    MODEL_DIR
    / "model_metrics.json"
)
def create_model():
    base_model = LinearSVC(
        C=10,
        random_state=42,
        max_iter=5000,
    )
    return CalibratedClassifierCV(
        estimator=base_model,
        method="sigmoid",
        cv=5,
    )
def main():
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)
    required_columns = {
        "description",
        "category",
    }
    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"Dataset must contain columns: "
            f"{required_columns}"
        )
    df = df.dropna(
        subset=["description", "category"]
    ).copy()
    X = df["description"].astype(str)
    y = df["category"].astype(str)
    print(f"Total samples: {len(df)}")
    print(f"Categories: {y.nunique()}")
    X_train, X_test, y_train, y_test = (
        train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=42,
            stratify=y,
        )
    )
    print(
        f"Training samples: "
        f"{len(X_train)}"
    )
    print(
        f"Testing samples: "
        f"{len(X_test)}"
    )
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    X_train_tfidf = (
        vectorizer.fit_transform(X_train)
    )
    X_test_tfidf = (
        vectorizer.transform(X_test)
    )
    model = create_model()
    print(
        "\nTraining calibrated "
        "category model..."
    )
    model.fit(
        X_train_tfidf,
        y_train,
    )
    predictions = model.predict(
        X_test_tfidf
    )
    accuracy = accuracy_score(
        y_test,
        predictions,
    )
    macro_f1 = f1_score(
        y_test,
        predictions,
        average="macro",
    )
    macro_precision = precision_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0,
    )
    macro_recall = recall_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0,
    )
    metrics = {
        "model_name": "ticket-classifier",
        "model_version": "1.0",
        "accuracy": round(
            float(accuracy) * 100,
            2,
        ),
        "precision": round(
            float(macro_precision) * 100,
            2,
        ),
        "recall": round(
            float(macro_recall) * 100,
            2,
        ),
        "f1_score": round(
            float(macro_f1) * 100,
            2,
        ),
    }
    print("\nTEST RESULTS")
    print(
        f"Accuracy: {accuracy:.4f}"
    )
    print(
        f"Macro F1: {macro_f1:.4f}"
    )
    print(
        "\nCLASSIFICATION REPORT"
    )
    print(
        classification_report(
            y_test,
            predictions,
            digits=4,
        )
    )
    print(
        "\n5-FOLD CROSS-VALIDATION"
    )
    cv = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=42,
    )
    cv_scores = cross_val_score(
        create_model(),
        X_train_tfidf,
        y_train,
        cv=cv,
        scoring="f1_macro",
    )
    print(
        "Fold scores:",
        [
            round(
                float(score),
                4,
            )
            for score in cv_scores
        ],
    )
    print(
        f"Mean Macro F1: "
        f"{cv_scores.mean():.4f}"
    )
    print(
        f"Std Dev: "
        f"{cv_scores.std():.4f}"
    )
    print(
        "\nRetraining final calibrated "
        "model on all data..."
    )
    final_vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    X_all_tfidf = (
        final_vectorizer.fit_transform(X)
    )
    final_model = create_model()
    final_model.fit(
        X_all_tfidf,
        y,
    )
    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    joblib.dump(
        final_model,
        MODEL_PATH,
    )
    joblib.dump(
        final_vectorizer,
        VECTORIZER_PATH,
    )
    
    metrics.update(
        {
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "total_samples": len(X),
            "cv_macro_f1": round(
                float(cv_scores.mean()) * 100,
                2,
            ),
            "classes": len(final_model.classes_),
        }
    )
    with open(
        METRICS_PATH,
        "w",
        encoding="utf-8",
    ) as metrics_file:
        json.dump(
            metrics,
            metrics_file,
            indent=4,
        )
    print(
        f"Metrics path: {METRICS_PATH}"
    )
    print(
        "\nFINAL CALIBRATED MODEL SAVED"
    )
    print(
        f"Model path: {MODEL_PATH}"
    )
    print(
        f"Vectorizer path: "
        f"{VECTORIZER_PATH}"
    )
    print(
        f"Final training samples: "
        f"{len(X)}"
    )
    print(
        f"Final TF-IDF features: "
        f"{len(final_vectorizer.vocabulary_)}"
    )
    print(
        f"Final categories: "
        f"{len(final_model.classes_)}"
    )
if __name__ == "__main__":
    main()










