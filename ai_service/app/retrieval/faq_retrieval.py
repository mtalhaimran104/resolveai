# app/retrieval/faq_retrieval.py

import os
import re
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

FAQ_DATASET = os.path.join(
    BASE_DIR,
    "data",
    "faq_dataset.csv"
)


# ============================================================
# MATCHING THRESHOLDS
# ============================================================

FAQ_THRESHOLD = 0.65
HIGH_CONFIDENCE_THRESHOLD = 0.75


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text before FAQ matching.

    Handles:
    - lowercase
    - punctuation
    - extra spaces
    """

    if not isinstance(text, str):
        return ""

    text = text.lower().strip()

    # Convert punctuation to spaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove repeated whitespace.
    text = re.sub(r"\s+", " ", text)

    return text


# ============================================================
# LOAD FAQ DATASET
# ============================================================

def load_faq_dataset() -> pd.DataFrame:
    """
    Load faq_dataset.csv.

    Required columns:

        question
        answer
    """

    empty_df = pd.DataFrame(
        columns=[
            "question",
            "answer",
            "normalized_question"
        ]
    )

    if not os.path.exists(FAQ_DATASET):
        print(
            f"[FAQ RETRIEVAL] Dataset not found: "
            f"{FAQ_DATASET}"
        )
        return empty_df

    try:
        try:
            df = pd.read_csv(
                FAQ_DATASET,
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            df = pd.read_csv(
                FAQ_DATASET,
                encoding="latin-1"
            )

    except Exception as exc:
        print(
            f"[FAQ RETRIEVAL] Dataset loading error: "
            f"{exc}"
        )
        return empty_df

    # --------------------------------------------------------
    # Validate columns
    # --------------------------------------------------------

    required_columns = {
        "question",
        "answer"
    }

    missing_columns = (
        required_columns
        - set(df.columns)
    )

    if missing_columns:
        print(
            "[FAQ RETRIEVAL] Missing required columns: "
            f"{', '.join(sorted(missing_columns))}"
        )

        return empty_df

    # --------------------------------------------------------
    # Remove missing values
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "question",
            "answer"
        ]
    ).copy()

    # --------------------------------------------------------
    # Convert to strings
    # --------------------------------------------------------

    df["question"] = (
        df["question"]
        .astype(str)
        .str.strip()
    )

    df["answer"] = (
        df["answer"]
        .astype(str)
        .str.strip()
    )

    # --------------------------------------------------------
    # Normalize questions
    # --------------------------------------------------------

    df["normalized_question"] = (
        df["question"]
        .apply(normalize_text)
    )

    # --------------------------------------------------------
    # Remove empty questions/answers
    # --------------------------------------------------------

    df = df[
        (df["normalized_question"].str.len() > 0)
        &
        (df["answer"].str.len() > 0)
    ]

    # --------------------------------------------------------
    # Remove duplicate questions
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["normalized_question"],
        keep="first"
    )

    df = df.reset_index(drop=True)

    return df


# ============================================================
# FAQ DATA
# ============================================================

FAQ_DF = load_faq_dataset()


# ============================================================
# TF-IDF MODEL
# ============================================================

vectorizer = None
faq_matrix = None


def build_faq_model() -> None:
    """
    Build the TF-IDF model using all FAQ questions.
    """

    global vectorizer
    global faq_matrix

    vectorizer = None
    faq_matrix = None

    if FAQ_DF.empty:
        print(
            "[FAQ RETRIEVAL] FAQ dataset is empty."
        )
        return

    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1
        )

        faq_matrix = vectorizer.fit_transform(
            FAQ_DF["normalized_question"]
        )

        print(
            f"[FAQ RETRIEVAL] Loaded "
            f"{len(FAQ_DF)} FAQ records."
        )

    except Exception as exc:
        print(
            f"[FAQ RETRIEVAL] TF-IDF build error: "
            f"{exc}"
        )

        vectorizer = None
        faq_matrix = None


# Build model when the module is imported.
build_faq_model()


# ============================================================
# EXACT MATCH
# ============================================================

def find_exact_match(
    normalized_query: str
):
    """
    Find an exact FAQ question match.

    Exact matches are returned before TF-IDF so that
    a question already present in the dataset always
    receives its corresponding answer.
    """

    if FAQ_DF.empty:
        return None

    matches = FAQ_DF.index[
        FAQ_DF["normalized_question"]
        == normalized_query
    ]

    if len(matches) == 0:
        return None

    index = matches[0]

    return {
        "found": True,
        "question": FAQ_DF.loc[
            index,
            "question"
        ],
        "answer": FAQ_DF.loc[
            index,
            "answer"
        ],
        "similarity_score": 1.0,
        "confidence_level": "High",
        "source": "exact_faq_match"
    }


# ============================================================
# RESULT HELPERS
# ============================================================

def not_found_result(
    query: str,
    score: float = 0.0,
    source: str = "faq_not_found"
) -> dict:
    """
    Standard response when no sufficiently relevant
    FAQ answer is available.
    """

    return {
        "found": False,
        "question": query,
        "answer": (
            "I could not find a sufficiently relevant "
            "answer for this question in the available "
            "IUB FAQ knowledge base.\n\n"
            "I do not want to guess or provide incorrect "
            "university information."
        ),
        "similarity_score": round(
            float(score),
            4
        ),
        "confidence_level": "Low",
        "source": source
    }


# ============================================================
# FAQ RETRIEVAL
# ============================================================

def retrieve_faq(query: str) -> dict:
    """
    Retrieve the most relevant FAQ answer.

    Retrieval order:

    1. Validate query.
    2. Exact FAQ match.
    3. TF-IDF similarity search.
    4. Reject weak matches.
    5. Return the best FAQ answer.

    This function does NOT generate answers.
    It only returns answers that already exist in
    faq_dataset.csv.
    """

    # --------------------------------------------------------
    # Validate query
    # --------------------------------------------------------

    if query is None:
        return not_found_result(
            "",
            source="empty_query"
        )

    if not isinstance(query, str):
        query = str(query)

    query = query.strip()

    if not query:
        return {
            "found": False,
            "question": query,
            "answer": (
                "Please enter an IUB-related question."
            ),
            "similarity_score": 0.0,
            "confidence_level": "Low",
            "source": "empty_query"
        }

    normalized_query = normalize_text(
        query
    )

    if not normalized_query:
        return {
            "found": False,
            "question": query,
            "answer": (
                "Please enter a valid IUB-related "
                "question."
            ),
            "similarity_score": 0.0,
            "confidence_level": "Low",
            "source": "invalid_query"
        }

    # --------------------------------------------------------
    # Dataset check
    # --------------------------------------------------------

    if FAQ_DF.empty:
        return not_found_result(
            query,
            source="empty_faq_dataset"
        )

    # --------------------------------------------------------
    # Exact match
    # --------------------------------------------------------

    exact_result = find_exact_match(
        normalized_query
    )

    if exact_result is not None:
        return exact_result

    # --------------------------------------------------------
    # TF-IDF model check
    # --------------------------------------------------------

    if vectorizer is None or faq_matrix is None:
        return not_found_result(
            query,
            source="tfidf_unavailable"
        )

    # --------------------------------------------------------
    # Transform user query
    # --------------------------------------------------------

    try:
        query_vector = vectorizer.transform(
            [normalized_query]
        )

    except Exception as exc:
        print(
            "[FAQ RETRIEVAL] Query transformation "
            f"error: {exc}"
        )

        return not_found_result(
            query,
            source="query_transformation_error"
        )

    # --------------------------------------------------------
    # Check unknown vocabulary
    # --------------------------------------------------------

    if query_vector.nnz == 0:
        return not_found_result(
            query,
            source="no_matching_terms"
        )

    # --------------------------------------------------------
    # Calculate cosine similarity
    # --------------------------------------------------------

    try:
        similarities = cosine_similarity(
            query_vector,
            faq_matrix
        ).flatten()

    except Exception as exc:
        print(
            "[FAQ RETRIEVAL] Similarity calculation "
            f"error: {exc}"
        )

        return not_found_result(
            query,
            source="similarity_error"
        )

    if len(similarities) == 0:
        return not_found_result(
            query,
            source="no_faq_matches"
        )

    # --------------------------------------------------------
    # Find best match
    # --------------------------------------------------------

    best_index = int(
        similarities.argmax()
    )

    best_score = float(
        similarities[best_index]
    )

    best_question = FAQ_DF.iloc[
        best_index
    ]["question"]

    best_answer = FAQ_DF.iloc[
        best_index
    ]["answer"]

    # --------------------------------------------------------
    # Confidence level
    # --------------------------------------------------------

    if best_score >= HIGH_CONFIDENCE_THRESHOLD:
        confidence = "High"

    elif best_score >= FAQ_THRESHOLD:
        confidence = "Medium"

    else:
        confidence = "Low"

    # --------------------------------------------------------
    # Reject weak match
    # --------------------------------------------------------

    if best_score < FAQ_THRESHOLD:
        return not_found_result(
            query,
            score=best_score,
            source="weak_faq_match"
        )

    # --------------------------------------------------------
    # Successful retrieval
    # --------------------------------------------------------

    return {
        "found": True,
        "question": best_question,
        "answer": best_answer,
        "similarity_score": round(
            best_score,
            4
        ),
        "confidence_level": confidence,
        "source": "iub_faq_knowledge_base"
    }


# ============================================================
# RELOAD FAQ MODEL
# ============================================================

def reload_faq_model() -> None:
    """
    Reload faq_dataset.csv and rebuild the TF-IDF model.

    Useful when the CSV dataset has been changed while
    FastAPI is still running.
    """

    global FAQ_DF

    FAQ_DF = load_faq_dataset()

    build_faq_model()

    print(
        f"[FAQ RETRIEVAL] Reloaded "
        f"{len(FAQ_DF)} FAQ records."
    )


# ============================================================
# DATASET INFORMATION
# ============================================================

def get_faq_count() -> int:
    """
    Return the number of loaded FAQ records.
    """

    return len(FAQ_DF)