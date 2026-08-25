import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

SENTIMENT_MODEL = "cardiffnlp/twitter-xlm-roberta-base-sentiment"


# ============================================================
# DEVICE
# ============================================================

DEVICE = torch.device("cpu")


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading multilingual sentiment model...")

sentiment_tokenizer = AutoTokenizer.from_pretrained(
    SENTIMENT_MODEL,
    use_fast=False
)

sentiment_model = AutoModelForSequenceClassification.from_pretrained(
    SENTIMENT_MODEL
)

sentiment_model.to(DEVICE)
sentiment_model.eval()

print("Sentiment model loaded successfully.")


# ============================================================
# SENTIMENT ANALYSIS
# ============================================================

def analyze_sentiment(text: str):

    inputs = sentiment_tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True
    )

    inputs = {
        key: value.to(DEVICE)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = sentiment_model(**inputs)

    probabilities = torch.softmax(
        outputs.logits,
        dim=-1
    )

    predicted_class = torch.argmax(
        probabilities,
        dim=-1
    ).item()

    # Cardiff NLP model:
    # 0 = Negative
    # 1 = Neutral
    # 2 = Positive

    labels = {
        0: "negative",
        1: "neutral",
        2: "positive"
    }

    sentiment = labels.get(
        predicted_class,
        "neutral"
    )

    # Actual probability of the predicted sentiment.
    # This is the model's confidence score.
    confidence_score = float(
        probabilities[0][predicted_class].item()
    )

    return sentiment, confidence_score