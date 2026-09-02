"""
Resolve AI - Improved FAQ Retrieval Engine
==========================================

Drop-in replacement for:
    ai_service/app/retrieval/faq_retrieval.py

Goals:
- Strong semantic + lexical + keyword + topic + intent matching.
- Prevent unrelated FAQs from winning just because they share one word.
- Correctly handle paraphrases such as:
      "How do I recover my LMS password?"
      "What are the engineering fees?"
      "Tell me about the Quantum Computing program"
- Return detailed confidence information.
- Preserve the expected public API:
      normalize_text
      extract_keywords
      extract_topics
      extract_intents
      FAQRetriever
      faq_retriever

The retriever is intentionally conservative for unrelated questions.
An FAQ system should NOT answer "What is Python?" or "What is the weather?"
unless those topics actually exist in the IUB FAQ knowledge base.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# CONFIGURATION
# ============================================================

FAQ_THRESHOLD = 0.30
TOP_K = 40

HIGH_CONFIDENCE_THRESHOLD = 0.80
MEDIUM_CONFIDENCE_THRESHOLD = 0.62

# Final ranking weights.
SEMANTIC_WEIGHT = 0.48
KEYWORD_WEIGHT = 0.16
LEXICAL_WEIGHT = 0.14
TOPIC_WEIGHT = 0.12
INTENT_WEIGHT = 0.06
TYPE_WEIGHT = 0.04

# Extra confidence calibration.
MARGIN_WEIGHT = 0.12

# Query/result safety.
MIN_SEMANTIC_FOR_TOPIC_MATCH = 0.24
MIN_SEMANTIC_GENERAL = 0.38
MIN_FINAL_SCORE = 0.34


# ============================================================
# TEXT NORMALIZATION
# ============================================================

STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "been",
    "being", "to", "of", "for", "in", "on", "at", "by", "with", "from",
    "and", "or", "but", "as", "this", "that", "these", "those",
    "i", "me", "my", "mine", "we", "our", "you", "your", "yours",
    "he", "she", "it", "they", "them", "their", "his", "her",
    "do", "does", "did", "can", "could", "would", "should", "will",
    "how", "what", "when", "where", "who", "which", "why",
    "tell", "please", "about", "want", "need", "get", "give",
    "much", "many", "per", "than", "into", "through", "also",
}

SYNONYMS = {
    "recover": "reset",
    "recovery": "reset",
    "forgot": "reset",
    "forgotten": "reset",
    "lost": "reset",
    "working": "problem",
    "works": "problem",
    "cost": "fee",
    "costs": "fee",
    "fees": "fee",
    "charges": "fee",
    "charge": "fee",
    "price": "fee",
    "tuition": "fee",
    "cost": "fee",
    "costs": "fee",
    "programmes": "program",
    "programs": "program",
    "programme": "program",
    "department": "department",
    "faculty": "faculty",
    "complaint": "complaint",
    "grievance": "complaint",
    "issue": "problem",
    "issues": "problem",
    "contact": "support",
    "helpdesk": "support",
    "help": "support",
    "lms": "lms",
    "portal": "portal",
    "student": "student",
    "engineering": "engineering",
    "quantum": "quantum",
    "computing": "computing",
}


def normalize_text(text: Any) -> str:
    """Normalize text while preserving useful domain words."""
    if text is None:
        return ""

    text = str(text).lower().strip()

    # Common punctuation/formatting normalization.
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"[^a-z0-9\u0600-\u06ff\u0750-\u077f\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _tokens(text: Any) -> List[str]:
    normalized = normalize_text(text)
    raw = re.findall(r"[a-z0-9\u0600-\u06ff\u0750-\u077f]+", normalized)

    result = []
    for token in raw:
        if token in STOPWORDS:
            continue
        result.append(SYNONYMS.get(token, token))

    return result


def extract_keywords(text: Any) -> Set[str]:
    """Return meaningful normalized keywords."""
    return set(_tokens(text))


# ============================================================
# TOPIC / INTENT DETECTION
# ============================================================

TOPIC_PATTERNS = {
    "password": {
        "password", "reset", "forgot", "recover", "recovery",
        "login", "credential", "credentials",
    },
    "lms": {
        "lms", "learning", "moodle",
    },
    "portal": {
        "portal", "student", "login", "account",
    },
    "registration": {
        "register", "registration", "registrations",
        "enroll", "enrollment", "add", "drop",
    },
    "engineering": {
        "engineering", "telecommunication", "electrical",
        "biomedical", "robotics", "aircraft", "aviation",
        "information engineering",
    },
    "fee": {
        "fee", "fees", "cost", "costs",
        "charge", "charges",
        "tuition", "price",
        "payment", "payments",
    },
    "quantum": {
        "quantum", "computing", "algorithm", "algorithms",
        "quantum information",
    },
    "complaint": {
        "complaint", "grievance", "complain", "issue",
    },
    "admission": {
        "admission", "admissions", "apply", "application",
        "enroll", "enrollment", "deadline",
    },
    "scholarship": {
        "scholarship", "financial", "aid", "stipend",
    },
    "migration": {
        "migration", "migrate", "transfer",
    },
    "hostel": {
        "hostel", "accommodation", "room",
    },
    "library": {
        "library", "books", "timing", "timings",
    },
    "support": {
        "support", "helpdesk", "help", "contact", "it",
    },
}

INTENT_PATTERNS = {
    "procedure": {
        "apply",
        "procedure",
        "recover",
        "request",
        "register",
        "how",
        "submit",
        "reset",
        "change",
    },

    "fee": {
        "price",
        "payment",
        "charge",
        "charges",
        "costs",
        "cost",
        "tuition",
        "fee",
        "fees",
    },

    "date": {
        "launched",
        "date",
        "deadline",
        "launch",
        "when",
    },

    "location": {
        "campus",
        "office",
        "where",
        "located",
        "location",
    },

    "person": {
        "who",
        "dean",
        "professor",
        "doctor",
        "prof",
    },

    "general": {
        "which",
        "describe",
        "about",
        "tell",
        "what",
    },

    "problem": {
        "unable",
        "cannot",
        "cant",
        "working",
        "failed",
        "failure",
        "problem",
        "issue",
        "trouble",
        "error",
    },
}


def extract_topics(text: Any) -> Set[str]:
    """Detect canonical domain topics. Related words map to one topic."""
    normalized = normalize_text(text)
    keywords = extract_keywords(text)
    topics: Set[str] = set()

    for topic, words in TOPIC_PATTERNS.items():
        if keywords.intersection(words):
            topics.add(topic)

    # Canonical fee topic: fee/fees/cost/tuition/charges are one concept.
    fee_words = {
        "fee", "fees", "cost", "costs", "charge", "charges",
        "tuition", "price", "payment", "payments"
    }
    if keywords.intersection(fee_words):
        topics.add("fee")

    if "bs engineering" in normalized:
        topics.add("engineering")
        topics.add("fee")

    if "engineering fee" in normalized or "engineering fees" in normalized:
        topics.add("engineering")
        topics.add("fee")

    if "lms password" in normalized or "lms account" in normalized:
        topics.add("lms")
        topics.add("password")

    if "student portal" in normalized:
        topics.add("portal")

    if "portal password" in normalized:
        topics.add("portal")
        topics.add("password")

    if "quantum computing" in normalized:
        topics.add("quantum")
        topics.add("computing")

    # Course registration is its own topic.
    if (
        "course registration" in normalized
        or "register for courses" in normalized
        or "register courses" in normalized
        or "course enrollment" in normalized
        or "enroll in courses" in normalized
    ):
        topics.add("registration")

    return topics


def extract_intents(text: Any) -> Set[str]:
    keywords = extract_keywords(text)
    normalized = normalize_text(text)
    intents: Set[str] = set()

    for intent, words in INTENT_PATTERNS.items():
        if keywords.intersection(words):
            intents.add(intent)

    if re.search(r"\bwhat\s+is\b|\btell\s+me\s+about\b", normalized):
        intents.add("general")

    if re.search(r"\bhow\s+(do|can|to)\b", normalized):
        intents.add("procedure")

    if re.search(r"\bhow\s+much\b|\bwhat\s+is\s+the\s+fee\b", normalized):
        intents.add("fee")

    if re.search(r"\bwho\s+is\b", normalized):
        intents.add("person")

    if re.search(r"\bwhere\b", normalized):
        intents.add("location")

    if re.search(r"\bwhen\b", normalized):
        intents.add("date")

    # Problem / failure intent
    if re.search(
        r"\b(unable|cannot|can.t|cant|not\s+working|does\s+not\s+work|"
        r"doesn.t\s+work|failed|failure|problem|issue|trouble|error)\b",
        normalized,
    ):
        intents.add("problem")

    # A failure/problem query should not be treated
    # as a simple procedure query.
    if re.search(
        r"\b(unable|cannot|can't|cant|not\s+working|"
        r"does\s+not\s+work|doesn't\s+work|failed|failure|"
        r"problem|issue|trouble|error)\b",
        normalized,
    ):
        intents.discard("procedure")

    return intents


def _question_type(text: Any) -> str:
    normalized = normalize_text(text)

    if re.search(r"\bhow\s+(do|can|to)\b|\bapply\b|\bregister\b|\breset\b|\brecover\b|\bchange\b", normalized):
        return "procedure"

    if re.search(r"\bhow\s+much\b|\bfee\b|\bfees\b|\bcost\b|\bcharges?\b|\bprice\b", normalized):
        return "fee"

    if re.search(r"\bwhen\b|\bdeadline\b|\bdate\b|\blaunch(?:ed)?\b", normalized):
        return "date"

    if re.search(r"\bwhere\b|\blocation\b|\blocated\b|\boffice\b|\bcampus\b", normalized):
        return "location"

    if re.search(r"\bwho\b|\bprof\.?\b|\bdr\.?\b|\bdean\b", normalized):
        return "person"

    return "general"


def _type_score(query_type: str, faq_type: str) -> float:
    if query_type == faq_type:
        return 1.0

    # Some pairs are naturally related.
    related = {
        ("general", "date"): 0.35,
        ("general", "person"): 0.45,
        ("general", "location"): 0.45,
        ("general", "procedure"): 0.40,
        ("general", "fee"): 0.35,
        ("fee", "general"): 0.30,
        ("procedure", "general"): 0.30,
        ("person", "general"): 0.30,
        ("date", "general"): 0.30,
        ("location", "general"): 0.30,
    }

    return related.get((query_type, faq_type), 0.0)


# ============================================================
# SCORING HELPERS
# ============================================================

def _keyword_score(query_keywords: Set[str], faq_keywords: Set[str]) -> float:
    if not query_keywords or not faq_keywords:
        return 0.0

    overlap = query_keywords.intersection(faq_keywords)

    # Recall against query is important for short user questions.
    query_recall = len(overlap) / max(1, len(query_keywords))

    # Precision prevents one common word from looking perfect.
    faq_precision = len(overlap) / max(1, len(faq_keywords))

    return min(1.0, 0.70 * query_recall + 0.30 * faq_precision)


def _lexical_similarity(query_keywords: Set[str], faq_keywords: Set[str]) -> float:
    if not query_keywords or not faq_keywords:
        return 0.0

    q = " ".join(sorted(query_keywords))
    f = " ".join(sorted(faq_keywords))

    if not q or not f:
        return 0.0

    qset = set(q.split())
    fset = set(f.split())

    union = qset | fset
    if not union:
        return 0.0

    return len(qset & fset) / len(union)


def _topic_score(query_topics: Set[str], faq_topics: Set[str]) -> float:
    if not query_topics:
        return 0.0
    if not faq_topics:
        return 0.0

    overlap = query_topics.intersection(faq_topics)

    if not overlap:
        return 0.0

    return len(overlap) / max(1, len(query_topics))


def _intent_score(query_intents: Set[str], faq_intents: Set[str]) -> float:
    if not query_intents or not faq_intents:
        return 0.0

    overlap = query_intents.intersection(faq_intents)

    if not overlap:
        return 0.0

    return len(overlap) / max(1, len(query_intents))


def _contains_strong_entity(query: str, faq_question: str) -> bool:
    """Protect named entities / domain phrases from being lost."""
    q = normalize_text(query)
    f = normalize_text(faq_question)

    protected_phrases = [
        "dr sabih anwar",
        "sabih anwar",
        "quantum computing",
        "lms password",
        "lms account",
        "student portal",
        "portal password",
        "bs engineering",
        "engineering fee",
        "engineering fees",
        "faculty of engineering",
        "student complaint",
        "financial hold",
        "omar khayyam scholarship",
    ]

    for phrase in protected_phrases:
        if phrase in q and phrase in f:
            return True

    # Names: if the query contains a distinctive capitalized-looking
    # normalized pair, matching the same pair is strong evidence.
    words = q.split()
    for i in range(len(words) - 1):
        pair = f"{words[i]} {words[i + 1]}"
        if len(words[i]) >= 4 and len(words[i + 1]) >= 4 and pair in f:
            return True

    return False


def _topic_conflict(query_topics: Set[str], faq_topics: Set[str]) -> bool:
    """
    Prevent dangerous cross-topic matches.

    Examples:
      LMS password != portal password
      engineering fee != scholarship
      driving license != IUB complaint
    """
    exclusive_pairs = [
        ("lms", "portal"),
        ("engineering", "scholarship"),
        ("engineering", "hostel"),
        ("quantum", "hostel"),
        ("complaint", "scholarship"),
    ]

    for a, b in exclusive_pairs:
        if a in query_topics and b in faq_topics and b not in query_topics:
            return True
        if b in query_topics and a in faq_topics and a not in query_topics:
            return True

    return False


def _confidence_level(score: float) -> str:
    if score >= HIGH_CONFIDENCE_THRESHOLD:
        return "High"
    if score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "Medium"
    return "Low"


# ============================================================
# DATA LOADING
# ============================================================

def _find_data_file() -> Optional[Path]:
    """
    Find the FAQ dataset safely.

    Priority:
    1. FAQ_DATA_PATH / FAQ_FILE environment variable.
    2. /app/data/faq_dataset.csv (Docker-mounted project data).
    3. Project-local data/faq_dataset.csv when running outside Docker.
    4. Other FAQ-like files, but ONLY if they contain question + answer columns.

    This deliberately ignores files such as iub_programs.csv and
    iub_postgraduate_programs.csv because those are program catalogs, not FAQs.
    """
    env_path = os.getenv("FAQ_DATA_PATH") or os.getenv("FAQ_FILE")
    here = Path(__file__).resolve()

    # Current repository layout:
    # resolveai/
    #   data/faq_dataset.csv
    #   ai_service/app/retrieval/faq_retrieval.py
    project_root = here.parents[3]

    explicit_candidates = []
    if env_path:
        explicit_candidates.append(Path(env_path))

    explicit_candidates.extend([
        Path("/app/data/faq_dataset.csv"),
        Path("/app/data/faq_dataset.xlsx"),
        project_root / "data" / "faq_dataset.csv",
        project_root / "data" / "faq_dataset.xlsx",
        Path("/data/faq_dataset.csv"),
        Path("/data/faq_dataset.xlsx"),
    ])

    # Additional names are allowed, but are validated before selection.
    faq_names = [
        "faq_dataset.csv", "faq_dataset.xlsx",
        "faq.csv", "faqs.csv", "FAQ.csv",
        "faq_data.csv", "faq_data.xlsx",
        "iub_faq.csv", "iub_faqs.csv",
        "knowledge_base.csv", "knowledge_base.xlsx",
        "faq.xlsx", "faqs.xlsx", "FAQ.xlsx",
        "iub_faq.xlsx",
    ]

    search_roots = [
        project_root / "data",
        Path("/app/data"),
        Path("/data"),
        here.parent,
        here.parent.parent,
        here.parent.parent.parent,
    ]

    for root in search_roots:
        for name in faq_names:
            explicit_candidates.append(root / name)

    def has_faq_columns(path: Path) -> bool:
        """Return True only for files containing question and answer columns."""
        try:
            suffix = path.suffix.lower()
            if suffix == ".csv":
                header = pd.read_csv(path, nrows=0, encoding="utf-8-sig")
            elif suffix in {".xlsx", ".xls"}:
                header = pd.read_excel(path, nrows=0)
            else:
                return False

            columns = {
                normalize_text(str(col)).replace(" ", "_")
                for col in header.columns
            }

            question_columns = {
                "question", "questions", "faq_question", "query", "prompt"
            }
            answer_columns = {
                "answer", "answers", "faq_answer", "response", "content"
            }

            return bool(columns & question_columns) and bool(columns & answer_columns)
        except Exception:
            return False

    seen = set()

    # First pass: exact preferred files.
    for candidate in explicit_candidates:
        try:
            candidate = candidate.resolve()
        except Exception:
            continue

        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)

        if candidate.exists() and candidate.is_file() and has_faq_columns(candidate):
            return candidate

    # Final fallback: search only FAQ/knowledge/question-like filenames.
    for root in search_roots:
        if not root.exists():
            continue
        try:
            for pattern in ("*.csv", "*.xlsx", "*.xls"):
                for candidate in root.rglob(pattern):
                    low = candidate.name.lower()
                    if not any(x in low for x in ("faq", "knowledge", "question", "qa")):
                        continue
                    try:
                        candidate = candidate.resolve()
                    except Exception:
                        continue
                    key = str(candidate).lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    if has_faq_columns(candidate):
                        return candidate
        except Exception:
            continue

    return None

def _load_dataframe(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()

    if suffix == ".csv":
        # utf-8-sig handles Excel-generated CSV files.
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            return pd.read_csv(path)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)

    raise ValueError(f"Unsupported FAQ file format: {path}")


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalize column names.
    rename = {}
    for col in df.columns:
        normalized = normalize_text(col).replace(" ", "_")
        rename[col] = normalized

    df = df.rename(columns=rename)

    question_candidates = [
        "question",
        "questions",
        "faq_question",
        "query",
        "prompt",
    ]

    answer_candidates = [
        "answer",
        "answers",
        "faq_answer",
        "response",
        "content",
    ]

    qcol = next((c for c in question_candidates if c in df.columns), None)
    acol = next((c for c in answer_candidates if c in df.columns), None)

    if qcol is None or acol is None:
        raise ValueError(
            "FAQ dataset must contain question and answer columns. "
            f"Found columns: {list(df.columns)}"
        )

    if qcol != "question":
        df["question"] = df[qcol]

    if acol != "answer":
        df["answer"] = df[acol]

    df["question"] = df["question"].fillna("").astype(str)
    df["answer"] = df["answer"].fillna("").astype(str)

    # Remove completely empty records.
    df = df[
        (df["question"].str.strip() != "")
        & (df["answer"].str.strip() != "")
    ].reset_index(drop=True)

    return df


# ============================================================
# FAQ RETRIEVER
# ============================================================

class FAQRetriever:
    def __init__(self, data_path: Optional[str] = None):
        if data_path:
            path = Path(data_path)
        else:
            path = _find_data_file()

        if path is None:
            raise FileNotFoundError(
                "FAQ dataset was not found. Set FAQ_DATA_PATH or FAQ_FILE "
                "to the CSV/XLSX file containing question and answer columns."
            )

        self.data_path = str(path)
        self.data = _prepare_dataframe(_load_dataframe(path))

        self.normalized_questions = [
            normalize_text(x)
            for x in self.data["question"].tolist()
        ]

        # Use both word and character TF-IDF.
        self.word_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            max_df=0.98,
        )

        self.char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            sublinear_tf=True,
            max_features=30000,
        )

        self.word_vectors = self.word_vectorizer.fit_transform(
            self.normalized_questions
        )

        self.char_vectors = self.char_vectorizer.fit_transform(
            self.normalized_questions
        )

        self.question_keywords = [
            extract_keywords(x)
            for x in self.normalized_questions
        ]

        self.question_topics = [
            extract_topics(x)
            for x in self.normalized_questions
        ]

        self.question_intents = [
            extract_intents(x)
            for x in self.normalized_questions
        ]

        self.question_types = [
            _question_type(x)
            for x in self.normalized_questions
        ]

    # --------------------------------------------------------
    # Candidate generation
    # --------------------------------------------------------

    def _semantic_scores(self, query: str) -> Tuple[Any, Any, Any]:
        normalized = normalize_text(query)

        word_query = self.word_vectorizer.transform([normalized])
        char_query = self.char_vectorizer.transform([normalized])

        word_scores = cosine_similarity(
            word_query,
            self.word_vectors,
        )[0]

        char_scores = cosine_similarity(
            char_query,
            self.char_vectors,
        )[0]

        # Word matching carries more meaning; char matching catches
        # spelling variations, typos and morphology.
        semantic_scores = (
            0.75 * word_scores +
            0.25 * char_scores
        )

        return semantic_scores, word_scores, char_scores

    # --------------------------------------------------------
    # Exact matching
    # --------------------------------------------------------

    def _exact_match(
        self,
        query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
    ) -> Optional[Dict[str, Any]]:

        normalized_query = normalize_text(query)

        # Exact normalized question.
        for index, faq_question in enumerate(self.normalized_questions):
            if normalized_query == faq_question:
                return self._build_result(
                    index=index,
                    score=1.0,
                    semantic_score=1.0,
                    keyword_score=1.0,
                    lexical_score=1.0,
                    topic_score=1.0,
                    intent_score=1.0,
                    question_type_score=1.0,
                    margin=1.0,
                    confidence_score=1.0,
                    confidence_level="High",
                    source="exact_faq_match",
                )

        # Strong phrase/entity match with very high lexical overlap.
        for index, faq_question in enumerate(self.normalized_questions):
            if not _contains_strong_entity(query, faq_question):
                continue

            faq_keywords = self.question_keywords[index]
            kw = _keyword_score(query_keywords, faq_keywords)

            if kw >= 0.80:
                return self._build_result(
                    index=index,
                    score=0.98,
                    semantic_score=0.98,
                    keyword_score=kw,
                    lexical_score=max(kw, 0.90),
                    topic_score=1.0 if query_topics else 0.0,
                    intent_score=1.0 if query_intents else 0.0,
                    question_type_score=1.0,
                    margin=0.90,
                    confidence_score=0.98,
                    confidence_level="High",
                    source="strong_entity_match",
                )

        return None

    # --------------------------------------------------------
    # Main retrieval
    # --------------------------------------------------------

    def get_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Main FAQ retrieval.

        Strategy:
        1. Exact match.
        2. Semantic scores.
        3. HARD ROUTE: Admission Date/Deadline
        4. HARD ROUTE: Course Registration Problems
        5. Generate semantic/lexical/topic/intent candidates.
        6. Apply domain-specific routing.
        7. Apply conservative validation.
        """

        # --------------------------------------------------------
        # Validate query
        # --------------------------------------------------------
        if query is None:
            return None

        query = str(query).strip()

        if not query:
            return None

        # --------------------------------------------------------
        # Query features
        # --------------------------------------------------------
        query_keywords = extract_keywords(query)
        query_topics = extract_topics(query)
        query_intents = extract_intents(query)
        query_type = _question_type(query)

        if not query_keywords:
            return None

        normalized_query = normalize_text(query)

        # --------------------------------------------------------
        # Exact match
        # --------------------------------------------------------
        exact = self._exact_match(
            query,
            query_keywords,
            query_topics,
            query_intents,
        )

        if exact is not None:
            return exact

        # --------------------------------------------------------
        # Semantic scores
        # --------------------------------------------------------
        semantic_scores, word_scores, char_scores = self._semantic_scores(
            query
        )

        # ========================================================
        # HARD ROUTE: ADMISSION DATE / DEADLINE
        # ========================================================
        # When the user asks for an admission date/deadline,
        # prefer admission + date FAQs.
        #
        # Do NOT allow fee deadlines to win unless the user
        # explicitly asks about fees/payment.
        # ========================================================

        is_admission_date_query = (
            "admission" in query_topics
            and "date" in query_intents
            and "fee" not in query_topics
            and "registration" not in query_topics
        )

        normalized_admission_query = normalize_text(query)

        asks_admission_deadline = bool(
            re.search(
                r"\b(deadline|last\s+date|closing\s+date|last\s+day)\b",
                normalized_admission_query,
            )
        )

        asks_admission_opening = bool(
            re.search(
                r"\b(admission|admissions)\b.*\b(open|opens|opening)\b|"
                r"\bwhen\b.*\badmission",
                normalized_admission_query,
            )
        )

        if is_admission_date_query:

            admission_date_candidates = []

            for index in range(len(self.data)):

                faq_topics = self.question_topics[index]
                faq_intents = self.question_intents[index]

                # Must be admission related.
                if "admission" not in faq_topics:
                    continue

                # Must be a date/deadline FAQ.
                if "date" not in faq_intents:
                    continue

                # Do not allow unrelated domain-specific admissions.
                if "fee" in faq_topics:
                    continue
                if "hostel" in faq_topics:
                    continue
                if "scholarship" in faq_topics:
                    continue
                if "migration" in faq_topics:
                    continue

                faq_question = normalize_text(
                    self.data.iloc[index]["question"]
                )

                # Strong admission-date wording.
                if not re.search(
                    r"\b(admission|admissions|apply|application)\b",
                    faq_question,
                ):
                    continue

                semantic_score = float(
                    semantic_scores[index]
                )

                keyword_score = _keyword_score(
                    query_keywords,
                    self.question_keywords[index],
                )

                lexical_score = _lexical_similarity(
                    query_keywords,
                    self.question_keywords[index],
                )

                topic_score = _topic_score(
                    query_topics,
                    faq_topics,
                )

                intent_score = _intent_score(
                    query_intents,
                    faq_intents,
                )

                question_type_score = _type_score(
                    query_type,
                    self.question_types[index],
                )

                routing_score = (
                    0.40 * semantic_score
                    + 0.15 * keyword_score
                    + 0.10 * lexical_score
                    + 0.20 * topic_score
                    + 0.15 * intent_score
                )

                # Prefer the FAQ whose wording matches the exact
                # date request, rather than merely mentioning a deadline.
                direct_date_bonus = 0.0

                if asks_admission_deadline:
                    if re.search(
                        r"\b(last\s+date|application\s+deadline|deadline|closing\s+date)\b",
                        faq_question,
                    ):
                        direct_date_bonus += 0.35

                    # "after the deadline" answers a different question.
                    if re.search(
                        r"\b(after|late|missed)\b.*\bdeadline\b",
                        faq_question,
                    ):
                        direct_date_bonus -= 0.25

                elif asks_admission_opening:
                    if re.search(
                        r"\b(open|opens|opening)\b",
                        faq_question,
                    ):
                        direct_date_bonus += 0.30

                else:
                    if re.search(
                        r"\bwhen\b|\blast\s+date\b|\bdeadline\b",
                        faq_question,
                    ):
                        direct_date_bonus += 0.15

                routing_score += direct_date_bonus

                admission_date_candidates.append(
                    {
                        "index": int(index),
                        "semantic_score": semantic_score,
                        "keyword_score": keyword_score,
                        "lexical_score": lexical_score,
                        "topic_score": topic_score,
                        "intent_score": intent_score,
                        "question_type_score": question_type_score,
                        "routing_score": routing_score,
                    }
                )

            if admission_date_candidates:

                admission_date_candidates.sort(
                    key=lambda x: (
                        x["routing_score"],
                        x["intent_score"],
                        x["semantic_score"],
                        x["keyword_score"],
                    ),
                    reverse=True,
                )

                selected = admission_date_candidates[0]
                selected_index = selected["index"]

                if len(admission_date_candidates) > 1:
                    margin = max(
                        0.0,
                        selected["routing_score"]
                        - admission_date_candidates[1]["routing_score"],
                    )
                else:
                    margin = selected["routing_score"]

                confidence_score = min(
                    1.0,
                    max(
                        selected["routing_score"],
                        selected["intent_score"],
                        selected["topic_score"],
                    ),
                )

                confidence_level = _confidence_level(
                    confidence_score
                )

                return self._build_result(
                    index=selected_index,
                    score=selected["routing_score"],
                    semantic_score=selected["semantic_score"],
                    keyword_score=selected["keyword_score"],
                    lexical_score=selected["lexical_score"],
                    topic_score=selected["topic_score"],
                    intent_score=selected["intent_score"],
                    question_type_score=selected[
                        "question_type_score"
                    ],
                    margin=margin,
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    source="admission_date_routing",
                    question_type=self.question_types[
                        selected_index
                    ],
                )

        # ========================================================
        # HARD ROUTE: COURSE REGISTRATION PROBLEMS
        # ========================================================
        # If the student explicitly says that course registration
        # is not working, do NOT let complaint/portal FAQs win.
        # Search the complete FAQ dataset for the best genuine
        # course-registration FAQ and return it directly.
        # ========================================================

        is_course_registration_problem = (
            "registration" in query_topics
            and "problem" in query_intents
            and "complaint" not in query_topics
            and bool(
                re.search(
                    r"\b(course|courses)\b",
                    normalized_query,
                )
            )
            and bool(
                re.search(
                    r"\b(registration|register|enroll|enrollment)\b",
                    normalized_query,
                )
            )
        )

        if is_course_registration_problem:

            registration_candidates = []

            for index in range(len(self.data)):

                faq_topics = self.question_topics[index]

                # Must actually be about registration.
                if "registration" not in faq_topics:
                    continue

                # Never use complaint FAQ for a registration problem.
                if "complaint" in faq_topics:
                    continue

                faq_question = normalize_text(
                    self.data.iloc[index]["question"]
                )

                # Must be an actual course-registration FAQ.
                # "Enrollment certificate" or other generic enrollment
                # questions must NOT qualify.
                is_course_registration_faq = bool(
                    re.search(
                        r"\b(course|courses)\s+(registration|enrollment)\b",
                        faq_question,
                    )
                    or re.search(
                        r"\b(register|enroll)\b.{0,50}\b(course|courses)\b",
                        faq_question,
                    )
                    or re.search(
                        r"\b(course|courses)\b.{0,50}\b(register|enroll)\b",
                        faq_question,
                    )
                )

                if not is_course_registration_faq:
                    continue

                semantic_score = float(
                    semantic_scores[index]
                )

                keyword_score = _keyword_score(
                    query_keywords,
                    self.question_keywords[index],
                )

                lexical_score = _lexical_similarity(
                    query_keywords,
                    self.question_keywords[index],
                )

                topic_score = _topic_score(
                    query_topics,
                    faq_topics,
                )

                intent_score = _intent_score(
                    query_intents,
                    self.question_intents[index],
                )

                question_type_score = _type_score(
                    query_type,
                    self.question_types[index],
                )

                # Registration-specific ranking.
                routing_score = (
                    0.45 * semantic_score
                    + 0.15 * keyword_score
                    + 0.10 * lexical_score
                    + 0.20 * topic_score
                    + 0.10 * intent_score
                )

                registration_candidates.append(
                    {
                        "index": int(index),
                        "semantic_score": semantic_score,
                        "keyword_score": keyword_score,
                        "lexical_score": lexical_score,
                        "topic_score": topic_score,
                        "intent_score": intent_score,
                        "question_type_score": question_type_score,
                        "routing_score": routing_score,
                    }
                )

            if registration_candidates:

                registration_candidates.sort(
                    key=lambda x: (
                        x["routing_score"],
                        x["semantic_score"],
                        x["keyword_score"],
                        x["lexical_score"],
                    ),
                    reverse=True,
                )

                selected = registration_candidates[0]

                selected_index = selected["index"]

                # Calculate separation from second-best FAQ.
                if len(registration_candidates) > 1:
                    margin = max(
                        0.0,
                        selected["routing_score"]
                        - registration_candidates[1]["routing_score"],
                    )
                else:
                    margin = selected["routing_score"]

                confidence_score = min(
                    1.0,
                    max(
                        selected["semantic_score"],
                        selected["routing_score"],
                    ),
                )

                if confidence_score >= 0.65:
                    confidence_level = "High"
                elif confidence_score >= 0.45:
                    confidence_level = "Medium"
                else:
                    confidence_level = "Low"

                return self._build_result(
                    index=selected_index,
                    score=selected["routing_score"],
                    semantic_score=selected["semantic_score"],
                    keyword_score=selected["keyword_score"],
                    lexical_score=selected["lexical_score"],
                    topic_score=selected["topic_score"],
                    intent_score=selected["intent_score"],
                    question_type_score=selected[
                        "question_type_score"
                    ],
                    margin=margin,
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    source="course_registration_routing",
                    question_type=self.question_types[
                        selected_index
                    ],
                )

        # --------------------------------------------------------
        # Candidate generation continues...
        # --------------------------------------------------------
        ranked_indexes = semantic_scores.argsort()[::-1][:TOP_K]

        candidates: List[Dict[str, Any]] = []

        # --------------------------------------------------------
        # Candidate scoring
        # --------------------------------------------------------
        for index in ranked_indexes:

            semantic_score = float(semantic_scores[index])

            faq_keywords = self.question_keywords[index]
            faq_topics = self.question_topics[index]
            faq_intents = self.question_intents[index]
            faq_type = self.question_types[index]

            keyword_score = _keyword_score(
                query_keywords,
                faq_keywords,
            )

            lexical_score = _lexical_similarity(
                query_keywords,
                faq_keywords,
            )

            topic_score = _topic_score(
                query_topics,
                faq_topics,
            )

            intent_score = _intent_score(
                query_intents,
                faq_intents,
            )

            question_type_score = _type_score(
                query_type,
                faq_type,
            )

            # --------------------------------------------
            # Hard topic conflict
            # --------------------------------------------
            if _topic_conflict(
                query_topics,
                faq_topics,
            ):
                continue

            # --------------------------------------------
            # Base score
            # --------------------------------------------
            score = (
                semantic_score * SEMANTIC_WEIGHT
                + keyword_score * KEYWORD_WEIGHT
                + lexical_score * LEXICAL_WEIGHT
                + topic_score * TOPIC_WEIGHT
                + intent_score * INTENT_WEIGHT
                + question_type_score * TYPE_WEIGHT
            )

            # --------------------------------------------
            # Strong entity match
            # --------------------------------------------
            entity_match = _contains_strong_entity(
                query,
                self.data.iloc[index]["question"],
            )

            if entity_match:
                score += 0.10

            # --------------------------------------------
            # Strong topic agreement
            # --------------------------------------------
            if query_topics and topic_score >= 0.75:
                score += 0.05

            # --------------------------------------------
            # Strong intent agreement
            # --------------------------------------------
            if query_intents and intent_score >= 0.80:
                score += 0.03

            # ====================================================
            # COURSE REGISTRATION ROUTING
            # ====================================================

            faq_question = normalize_text(
                self.data.iloc[index]["question"]
            )

            faq_is_course_registration = bool(
                re.search(
                    r"\b(course|courses)\s+(registration|enrollment)\b",
                    faq_question,
                )
                or re.search(
                    r"\b(register|enroll)\b.{0,50}\b(course|courses)\b",
                    faq_question,
                )
                or re.search(
                    r"\b(course|courses)\b.{0,50}\b(register|enroll)\b",
                    faq_question,
                )
            )

            faq_is_complaint = (
                "complaint" in faq_topics
            )

            if is_course_registration_problem:

                # Genuine course-registration FAQ = strong bonus.
                if (
                    "registration" in faq_topics
                    and faq_is_course_registration
                    and not faq_is_complaint
                ):
                    score += 0.60

                # Complaint FAQ = strong penalty.
                if faq_is_complaint:
                    score -= 0.80

                # Registration FAQ without course context is weaker.
                elif (
                    "registration" in faq_topics
                    and not faq_is_course_registration
                ):
                    score -= 0.10

            # ====================================================
            # ADMISSION DATE DOMAIN PROTECTION
            # ====================================================
            if is_admission_date_query:
                if "admission" in faq_topics and "date" in faq_intents:
                    score += 0.20
                else:
                    score -= 0.20

                if "hostel" in faq_topics and "hostel" not in query_topics:
                    score -= 0.50
                if "fee" in faq_topics and "fee" not in query_topics:
                    score -= 0.50

            # ====================================================
            # NORMAL REGISTRATION
            # ====================================================
            elif "registration" in query_topics:

                if "registration" in faq_topics:
                    score += 0.20
                else:
                    score -= 0.20

                # A registration problem should not select complaint.
                if (
                    "problem" in query_intents
                    and faq_is_complaint
                    and "complaint" not in query_topics
                ):
                    score -= 0.60

            # ====================================================
            # COMPLAINT ROUTING
            # ====================================================
            if "complaint" in query_topics:

                if "complaint" in faq_topics:
                    score += 0.20

                elif "registration" in faq_topics:
                    score -= 0.15

            # ====================================================
            # ENGINEERING + FEE
            # ====================================================
            if (
                "engineering" in query_topics
                and "fee" in query_topics
            ):
                if (
                    "engineering" in faq_topics
                    and "fee" in faq_topics
                ):
                    score += 0.25

                elif (
                    "engineering" in faq_topics
                    and "fee" not in faq_topics
                ):
                    score -= 0.12

            # ====================================================
            # LMS + PASSWORD
            # ====================================================
            if (
                "lms" in query_topics
                and "password" in query_topics
            ):
                if (
                    "lms" in faq_topics
                    and "password" in faq_topics
                ):
                    score += 0.20

                elif (
                    "portal" in faq_topics
                    and "lms" not in faq_topics
                ):
                    score -= 0.18

            # ====================================================
            # PORTAL + PASSWORD
            # ====================================================
            if (
                "portal" in query_topics
                and "password" in query_topics
            ):
                if (
                    "portal" in faq_topics
                    and "password" in faq_topics
                ):
                    score += 0.18

                elif (
                    "lms" in faq_topics
                    and "portal" not in faq_topics
                ):
                    score -= 0.15

            # ====================================================
            # QUANTUM
            # ====================================================
            if "quantum" in query_topics:
                if "quantum" in faq_topics:
                    score += 0.18

            score = max(
                0.0,
                min(1.0, score),
            )

            candidates.append(
                {
                    "index": int(index),
                    "semantic_score": semantic_score,
                    "word_score": float(word_scores[index]),
                    "char_score": float(char_scores[index]),
                    "keyword_score": keyword_score,
                    "lexical_score": lexical_score,
                    "topic_score": topic_score,
                    "intent_score": intent_score,
                    "question_type": faq_type,
                    "question_type_score": question_type_score,
                    "entity_match": entity_match,
                    "score": score,
                }
            )

        # --------------------------------------------------------
        # No candidates
        # --------------------------------------------------------
        if not candidates:
            return None

        # --------------------------------------------------------
        # Normal ranking
        # --------------------------------------------------------
        candidates.sort(
            key=lambda item: (
                item["score"],
                item["semantic_score"],
                item["topic_score"],
                item["keyword_score"],
                item["lexical_score"],
            ),
            reverse=True,
        )

        best = candidates[0]

        # --------------------------------------------------------
        # IMPORTANT:
        # From this point onward, ALWAYS use the selected candidate.
        # Do not use stale loop variables such as semantic_score/index/topic_score.
        # --------------------------------------------------------

        index = best["index"]

        semantic_score = best["semantic_score"]
        keyword_score = best["keyword_score"]
        lexical_score = best["lexical_score"]
        topic_score = best["topic_score"]
        intent_score = best["intent_score"]
        type_score = best["question_type_score"]

        # --------------------------------------------------------
        # Calculate margin against next candidate
        # --------------------------------------------------------
        sorted_scores = sorted(
            [c["score"] for c in candidates],
            reverse=True,
        )

        if len(sorted_scores) >= 2:
            margin = max(
                0.0,
                best["score"] - sorted_scores[1],
            )
        else:
            margin = best["score"]

        # ========================================================
        # FINAL ACCEPTANCE
        # ========================================================

        # Normal topic query.
        if query_topics:

            if (
                topic_score < 0.50
                and semantic_score < MIN_SEMANTIC_FOR_TOPIC_MATCH
                and not best["entity_match"]
            ):
                return None

        # General query.
        else:

            if (
                semantic_score < MIN_SEMANTIC_GENERAL
                and not best["entity_match"]
            ):
                return None

        # Standard minimum score.
        if best["score"] < MIN_FINAL_SCORE:
            return None

        # Weak ambiguous match.
        if (
            semantic_score < 0.42
            and margin < 0.015
            and topic_score < 0.75
            and not best["entity_match"]
        ):
            return None

        # --------------------------------------------------------
        # Confidence
        # --------------------------------------------------------
        confidence_score = min(
            1.0,
            (
                0.70 * best["score"]
                + 0.20 * semantic_score
                + 0.10 * min(1.0, margin * 5.0)
            ),
        )

        confidence_level = _confidence_level(
            confidence_score
        )

        # --------------------------------------------------------
        # Return result
        # --------------------------------------------------------
        return self._build_result(
            index=index,
            score=best["score"],
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            lexical_score=lexical_score,
            topic_score=topic_score,
            intent_score=intent_score,
            question_type_score=type_score,
            margin=margin,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            source="faq_retrieval",
            question_type=best["question_type"],
        )

    # --------------------------------------------------------
    # Result builder
    # --------------------------------------------------------

    def _build_result(
        self,
        index: int,
        score: float,
        semantic_score: float,
        keyword_score: float,
        lexical_score: float,
        topic_score: float,
        intent_score: float,
        question_type_score: float,
        margin: float,
        confidence_score: float,
        confidence_level: str,
        source: str,
        question_type: Optional[str] = None,
    ) -> Dict[str, Any]:

        if question_type is None:
            question_type = self.question_types[index]

        return {
            "answer": self.data.iloc[index]["answer"],
            "question": self.data.iloc[index]["question"],

            # Backward-compatible main score.
            "score": round(float(score), 4),

            "semantic_score": round(
                float(semantic_score), 4
            ),

            "keyword_score": round(
                float(keyword_score), 4
            ),

            "lexical_score": round(
                float(lexical_score), 4
            ),

            "topic_score": round(
                float(topic_score), 4
            ),

            "intent_score": round(
                float(intent_score), 4
            ),

            "question_type": question_type,

            "question_type_score": round(
                float(question_type_score), 4
            ),

            "margin": round(
                float(margin), 4
            ),

            "confidence_score": round(
                float(confidence_score), 4
            ),

            "confidence_level": confidence_level,

            "source": source,
        }


# ============================================================
# SINGLETON USED BY THE EXISTING APPLICATION
# ============================================================

faq_retriever = FAQRetriever(
    os.getenv("FAQ_DATA_PATH") or os.getenv("FAQ_FILE") or _find_data_file()
)


# ============================================================
# OPTIONAL SERVICE-STYLE HELPER
# ============================================================

def retrieve_faq(query: str) -> Dict[str, Any]:
    """
    Compatibility helper for code that expects a service-style response.

    Always returns an object containing confidence information.
    """
    result = faq_retriever.get_answer(query)

    if result is None:
        return {
            "found": False,
            "answer": "",
            "question": "",
            "score": 0.0,
            "similarity_score": 0.0,
            "confidence_score": 0.0,
            "confidence_level": "Low",
            "source": "faq_not_found",
            "semantic_score": 0.0,
            "keyword_score": 0.0,
            "lexical_score": 0.0,
            "topic_score": 0.0,
            "intent_score": 0.0,
            "question_type": _question_type(query),
            "question_type_score": 0.0,
            "margin": 0.0,
        }

    return {
        "found": True,
        "answer": result["answer"],
        "question": result["question"],
        "score": result["score"],
        "similarity_score": result["semantic_score"],
        "confidence_score": result["confidence_score"],
        "confidence_level": result["confidence_level"],
        "source": result["source"],
        "semantic_score": result["semantic_score"],
        "keyword_score": result["keyword_score"],
        "lexical_score": result["lexical_score"],
        "topic_score": result["topic_score"],
        "intent_score": result["intent_score"],
        "question_type": result["question_type"],
        "question_type_score": result["question_type_score"],
        "margin": result["margin"],
    }


if __name__ == "__main__":
    print("FAQ retriever loaded.")
    print("FAQ file:", faq_retriever.data_path)
    print("Rows:", len(faq_retriever.data))
    print("Word vectors:", faq_retriever.word_vectors.shape)
    print("Char vectors:", faq_retriever.char_vectors.shape)