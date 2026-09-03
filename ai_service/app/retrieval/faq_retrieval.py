"""
Resolve AI - Improved FAQ Retrieval Engine
==========================================

Enhanced with intent-based ranking to distinguish between semantically similar
but intent-different questions (e.g., "courses available" vs "eligibility").

Key improvements:
- Added question-type classification (what, how, who, where, when, which)
- Added intent extraction from both query and FAQ questions
- Enhanced ranking weights to prioritize intent alignment
- Added dynamic domain detection without hardcoding
- Improved semantic similarity with weighted components
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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

# Final ranking weights - adjusted to prioritize intent and semantic meaning
SEMANTIC_WEIGHT = 0.40
INTENT_WEIGHT = 0.25  # Increased from 0.06
KEYWORD_WEIGHT = 0.12  # Reduced from 0.16
LEXICAL_WEIGHT = 0.08  # Reduced from 0.14
TOPIC_WEIGHT = 0.10
QUESTION_TYPE_WEIGHT = 0.05

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
    "eligibility": "eligibility",
    "eligible": "eligibility",
    "available": "available",
    "courses": "course",
    "course": "course",
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
# ENHANCED INTENT AND QUESTION TYPE DETECTION
# ============================================================

# Question type patterns - derived from actual FAQ questions
QUESTION_TYPE_PATTERNS = {
    "what": {
        "what", "which", "name", "list", "types", "kinds", 
        "description", "overview", "information", "details"
    },
    "how": {
        "how", "procedure", "process", "steps", "method", 
        "way", "apply", "register", "reset", "recover", "change"
    },
    "who": {
        "who", "person", "people", "dean", "professor", "doctor", "prof", "chairman"
    },
    "where": {
        "where", "location", "campus", "office", "place", "address", "building"
    },
    "when": {
        "when", "date", "deadline", "time", "schedule", "timing", "opening"
    },
    "why": {
        "why", "reason", "purpose", "benefit", "advantage"
    },
    "is_yes_no": {
        "is", "are", "am", "does", "do", "can", "could", "will", "would", 
        "should", "has", "have", "had"
    }
}

# Intent categories for ranking
INTENT_CATEGORIES = {
    "information": {
        "what", "which", "name", "list", "types", "kinds", 
        "description", "overview", "information", "details", "tell", "about"
    },
    "procedure": {
        "how", "procedure", "process", "steps", "method", 
        "way", "apply", "register", "reset", "recover", "change", "do"
    },
    "eligibility": {
        "eligible", "eligibility", "criteria", "requirements", "qualify", 
        "minimum", "required", "prerequisite"
    },
    "availability": {
        "available", "offer", "offered", "provide", "provided", "has", "have",
        "list", "options", "choices", "selection"
    },
    "location": {
        "where", "location", "campus", "office", "place", "address", "building",
        "located", "find", "near"
    },
    "person": {
        "who", "person", "people", "dean", "professor", "doctor", "prof", "chairman",
        "director", "head"
    },
    "date": {
        "when", "date", "deadline", "time", "schedule", "timing", "opening",
        "start", "begin", "end", "duration"
    },
    "fee": {
        "fee", "fees", "cost", "costs", "charge", "charges", "price", "tuition",
        "payment", "payments", "amount", "rate"
    },
    "problem": {
        "unable", "cannot", "cant", "working", "failed", "failure", "problem",
        "issue", "trouble", "error", "not working", "doesn't work"
    }
}


def detect_question_type(text: str) -> str:
    """Detect the primary question type (what, how, who, where, when, why, is_yes_no)."""
    normalized = normalize_text(text)
    words = normalized.split()
    
    # Check for question type indicators
    for qtype, patterns in QUESTION_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized or (len(words) > 0 and words[0] == pattern):
                return qtype
    
    # Default to "what" for general queries
    return "what"


def extract_intent(text: str) -> str:
    """
    Extract the primary intent category from a query or FAQ question.
    This is more granular than the previous intent detection.
    """
    normalized = normalize_text(text)
    keywords = extract_keywords(text)
    
    # Check for strong intent indicators
    for intent, patterns in INTENT_CATEGORIES.items():
        # Check if any pattern appears in the normalized text
        for pattern in patterns:
            if pattern in normalized:
                # For availability, make sure it's about courses/programs
                if intent == "availability" and any(w in normalized for w in ["course", "program", "class", "skill"]):
                    return intent
                elif intent == "availability":
                    # Check if it's actually about availability
                    if any(w in normalized for w in ["available", "offer", "provide", "has", "have"]):
                        return intent
                elif intent == "eligibility" and any(w in normalized for w in ["eligible", "eligibility", "criteria", "requirements"]):
                    return intent
                elif intent == "fee" and any(w in normalized for w in ["fee", "fees", "cost", "costs", "tuition"]):
                    return intent
                elif intent == "procedure" and any(w in normalized for w in ["how", "procedure", "process", "steps"]):
                    return intent
                elif intent == "problem" and any(w in normalized for w in ["unable", "cannot", "cant", "problem", "issue", "error"]):
                    return intent
                elif intent == "information":
                    # Information is the default intent
                    return intent
                elif intent in ["location", "person", "date"]:
                    return intent
    
    # If no specific intent detected, default to "information"
    return "information"


def extract_intents(text: Any) -> Set[str]:
    """
    Legacy function for backward compatibility.
    Returns a set of intent categories.
    """
    primary_intent = extract_intent(text)
    if primary_intent:
        return {primary_intent}
    return set()


def extract_topics(text: Any) -> Set[str]:
    """Detect canonical domain topics. Related words map to one topic."""
    normalized = normalize_text(text)
    keywords = extract_keywords(text)
    topics: Set[str] = set()

    # Domain-specific topic patterns
    topic_patterns = {
        "password": {"password", "reset", "forgot", "recover", "recovery", "login", "credential"},
        "lms": {"lms", "learning", "moodle"},
        "portal": {"portal", "student", "login", "account"},
        "registration": {"register", "registration", "enroll", "enrollment", "add", "drop", "course"},
        "engineering": {"engineering", "telecommunication", "electrical", "biomedical", "robotics", "aircraft", "aviation"},
        "fee": {"fee", "fees", "cost", "costs", "charge", "charges", "tuition", "price", "payment"},
        "quantum": {"quantum", "computing", "algorithm", "quantum information"},
        "complaint": {"complaint", "grievance", "complain", "issue"},
        "admission": {"admission", "admissions", "apply", "application", "enroll", "deadline"},
        "scholarship": {"scholarship", "financial", "aid", "stipend"},
        "migration": {"migration", "migrate", "transfer"},
        "hostel": {"hostel", "accommodation", "room"},
        "library": {"library", "books", "timing"},
        "support": {"support", "helpdesk", "help", "contact", "it"},
        "eligibility": {"eligible", "eligibility", "criteria", "requirements", "qualify", "prerequisite", "minimum"},
        "availability": {"available", "offer", "offered", "provide", "provided", "has", "have", "list", "options", "choices", "selection"},
        "rozgar": {"rozgar", "erozgaar", "e-rozgaar", "freelancing", "freelance", "freelancer"},
        "courses": {"course", "courses", "skill", "skills", "training", "learn", "learning", "program", "programs"},
    }

    for topic, words in topic_patterns.items():
        if keywords.intersection(words):
            topics.add(topic)

    # Special cases for e-Rozgaar - ensure both rozgar and related topics are detected
    if "rozgar" in normalized or "freelancing" in normalized or "e-rozgaar" in normalized or "erozgaar" in normalized:
        topics.add("rozgar")
        # If it mentions courses/skills/training, also add availability and courses topics
        if any(term in normalized for term in ["course", "courses", "skill", "skills", "training", "learn", "learning", "program"]):
            topics.add("availability")
            topics.add("courses")

    # Special case for course availability vs eligibility
    # If a query asks about courses AND availability, mark as availability
    if ("course" in normalized or "courses" in normalized) and "available" in normalized:
        topics.add("availability")
        topics.add("courses")
    
    # If a query asks about eligibility, mark as eligibility
    if "eligible" in normalized or "eligibility" in normalized or "criteria" in normalized or "requirements" in normalized:
        topics.add("eligibility")

    return topics


def _question_type(text: Any) -> str:
    """Legacy function for backward compatibility."""
    return detect_question_type(text)


def _intent_score(query_intents: Set[str], faq_intents: Set[str]) -> float:
    """Calculate intent similarity score."""
    if not query_intents or not faq_intents:
        return 0.0
    
    # If either has "information" and the other has a specific intent, 
    # they might still be related
    if "information" in query_intents and len(query_intents) == 1:
        # Generic information query - should match many FAQs
        return 0.5
    
    overlap = query_intents.intersection(faq_intents)
    
    if not overlap:
        # Check for related intents
        related_pairs = {
            ("information", "availability"): 0.6,
            ("information", "procedure"): 0.5,
            ("information", "eligibility"): 0.5,
            ("availability", "information"): 0.6,
            ("eligibility", "information"): 0.5,
            ("procedure", "information"): 0.5,
            ("fee", "information"): 0.4,
            ("fee", "procedure"): 0.3,
        }
        
        for intent in query_intents:
            for faq_intent in faq_intents:
                pair = (intent, faq_intent)
                if pair in related_pairs:
                    return related_pairs[pair]
        
        return 0.0
    
    # Weighted by number of matching intents
    return len(overlap) / max(1, len(query_intents))


def _type_score(query_type: str, faq_type: str) -> float:
    if query_type == faq_type:
        return 1.0

    # Some pairs are naturally related.
    related = {
        ("what", "how"): 0.4,
        ("how", "what"): 0.4,
        ("what", "is_yes_no"): 0.5,
        ("is_yes_no", "what"): 0.5,
        ("where", "what"): 0.3,
        ("what", "where"): 0.3,
        ("when", "what"): 0.3,
        ("what", "when"): 0.3,
        ("who", "what"): 0.3,
        ("what", "who"): 0.3,
        ("how", "procedure"): 0.8,
        ("procedure", "how"): 0.8,
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
        "rozgar center",
        "e rozgar",
        "freelancing courses",
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
    """
    exclusive_pairs = [
        ("lms", "portal"),
        ("engineering", "scholarship"),
        ("engineering", "hostel"),
        ("quantum", "hostel"),
        ("complaint", "scholarship"),
        ("eligibility", "availability"),  # Don't confuse eligibility with availability
        ("availability", "eligibility"),
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
    """Find the FAQ dataset safely."""
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
        # Knowledge Base articles
        # --------------------------------------------------------
        try:
            from app.core.ai_service_helper import AIServiceHelper

            self.knowledge_articles = [
                dict(row)
                for row in AIServiceHelper.getKnowledgeBaseArticles()
            ]

            # Build a searchable document from title + excerpt + content.
            self.kb_documents = [
                normalize_text(
                    f"{article.get('title') or ''} "
                    f"{article.get('excerpt') or ''} "
                    f"{article.get('content') or ''}"
                )
                for article in self.knowledge_articles
            ]

            self.kb_questions = [
                normalize_text(str(article.get("title") or ""))
                for article in self.knowledge_articles
            ]

            self.kb_keywords = [
                extract_keywords(
                    f"{article.get('title') or ''} "
                    f"{article.get('excerpt') or ''} "
                    f"{article.get('content') or ''}"
                )
                for article in self.knowledge_articles
            ]

            self.kb_topics = [
                extract_topics(
                    f"{article.get('title') or ''} "
                    f"{article.get('excerpt') or ''}"
                )
                for article in self.knowledge_articles
            ]

            self.kb_intents = [
                extract_intents(
                    f"{article.get('title') or ''} "
                    f"{article.get('excerpt') or ''}"
                )
                for article in self.knowledge_articles
            ]

            self.kb_types = [
                _question_type(str(article.get("title") or ""))
                for article in self.knowledge_articles
            ]

            # Dedicated TF-IDF for Knowledge Base articles.
            self.kb_word_vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                min_df=1,
                sublinear_tf=True,
            )

            self.kb_char_vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=1,
                sublinear_tf=True,
            )

            self.kb_word_vectors = self.kb_word_vectorizer.fit_transform(
                self.kb_documents
            )

            self.kb_char_vectors = self.kb_char_vectorizer.fit_transform(
                self.kb_documents
            )

        except Exception:
            self.knowledge_articles = []
            self.kb_documents = []
            self.kb_questions = []
            self.kb_keywords = []
            self.kb_topics = []
            self.kb_intents = []
            self.kb_types = []
            self.kb_word_vectorizer = None
            self.kb_char_vectorizer = None
            self.kb_word_vectors = None
            self.kb_char_vectors = None

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
        Main FAQ retrieval with enhanced intent-based ranking.
        """
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
        # KNOWLEDGE BASE RETRIEVAL
        # --------------------------------------------------------
        if (
            self.knowledge_articles
            and self.kb_word_vectorizer is not None
            and self.kb_char_vectorizer is not None
        ):
            kb_word_query = self.kb_word_vectorizer.transform(
                [normalized_query]
            )
            kb_char_query = self.kb_char_vectorizer.transform(
                [normalized_query]
            )

            kb_word_scores = cosine_similarity(
                kb_word_query,
                self.kb_word_vectors,
            )[0]

            kb_char_scores = cosine_similarity(
                kb_char_query,
                self.kb_char_vectors,
            )[0]

            kb_semantic_scores = (
                0.75 * kb_word_scores
                + 0.25 * kb_char_scores
            )

            best_article = None
            best_index = -1
            best_score = 0.0
            second_best_score = 0.0

            for idx, article in enumerate(self.knowledge_articles):
                title = str(article.get("title") or "")
                excerpt = str(article.get("excerpt") or "")
                content = str(article.get("content") or "")

                article_keywords = self.kb_keywords[idx]
                article_topics = self.kb_topics[idx]

                # Topic conflict check for KB
                if _topic_conflict(query_topics, article_topics):
                    continue

                semantic_score = float(
                    kb_semantic_scores[idx]
                )

                keyword_score = _keyword_score(
                    query_keywords,
                    article_keywords,
                )

                lexical_score = _lexical_similarity(
                    query_keywords,
                    extract_keywords(title),
                )

                topic_score = _topic_score(
                    query_topics,
                    article_topics,
                )

                intent_score = _intent_score(
                    query_intents,
                    self.kb_intents[idx],
                )

                question_type_score = _type_score(
                    query_type,
                    self.kb_types[idx],
                )

                normalized_title = normalize_text(title)

                exact_title_match = (
                    normalized_query == normalized_title
                )

                title_contains_query = (
                    normalized_query in normalized_title
                    if normalized_query
                    else False
                )

                combined_score = (
                    0.45 * semantic_score
                    + 0.20 * keyword_score
                    + 0.15 * lexical_score
                    + 0.10 * topic_score
                    + 0.05 * intent_score
                    + 0.05 * question_type_score
                )

                if exact_title_match:
                    combined_score += 0.50
                elif title_contains_query:
                    combined_score += 0.25

                # Domain-specific protection for KB
                if (
                    "registration" in query_topics
                    and "registration" in article_topics
                ):
                    combined_score += 0.45

                if (
                    "registration" in query_topics
                    and "password" in article_topics
                    and "registration" not in article_topics
                ):
                    combined_score -= 0.40

                if (
                    "lms" in query_topics
                    and "password" in query_topics
                ):
                    if "lms" in article_topics:
                        combined_score += 0.35
                    elif "portal" in article_topics:
                        combined_score -= 0.30

                # e-Rozgaar intent protection
                if "rozgar" in query_topics:
                    if "rozgar" in article_topics:
                        combined_score += 0.40
                    elif "eligibility" in article_topics and "availability" in query_topics:
                        combined_score -= 0.30

                combined_score = max(
                    0.0,
                    min(1.0, combined_score),
                )

                if combined_score > best_score:
                    second_best_score = best_score
                    best_score = combined_score
                    best_article = article
                    best_index = idx
                elif combined_score > second_best_score:
                    second_best_score = combined_score

            if best_article is not None:

                margin = max(
                    0.0,
                    best_score - second_best_score,
                )

                confidence_score = min(
                    1.0,
                    (
                        0.60 * best_score
                        + 0.25 * float(
                            kb_semantic_scores[best_index]
                        )
                        + 0.15 * min(
                            1.0,
                            margin * 5.0,
                        )
                    ),
                )

                strong_kb_match = (
                    (
                        best_score >= 0.50
                        and float(kb_semantic_scores[best_index]) >= 0.30
                    )
                    or (
                        best_score >= 0.42
                        and margin >= 0.08
                    )
                    or (
                        float(kb_semantic_scores[best_index]) >= 0.70
                        and margin >= 0.03
                    )
                )

                if strong_kb_match:
                    best = self.knowledge_articles[best_index]

                    return {
                        "answer": str(
                            best.get("content") or ""
                        ),
                        "question": str(
                            best.get("title") or ""
                        ),
                        "score": round(
                            best_score,
                            4,
                        ),
                        "semantic_score": round(
                            float(
                                kb_semantic_scores[
                                    best_index
                                ]
                            ),
                            4,
                        ),
                        "keyword_score": round(
                            _keyword_score(
                                query_keywords,
                                self.kb_keywords[
                                    best_index
                                ],
                            ),
                            4,
                        ),
                        "lexical_score": round(
                            _lexical_similarity(
                                query_keywords,
                                extract_keywords(
                                    str(
                                        best.get("title")
                                        or ""
                                    )
                                ),
                            ),
                            4,
                        ),
                        "topic_score": round(
                            _topic_score(
                                query_topics,
                                self.kb_topics[
                                    best_index
                                ],
                            ),
                            4,
                        ),
                        "intent_score": round(
                            _intent_score(
                                query_intents,
                                self.kb_intents[
                                    best_index
                                ],
                            ),
                            4,
                        ),
                        "question_type": self.kb_types[
                            best_index
                        ],
                        "question_type_score": round(
                            _type_score(
                                query_type,
                                self.kb_types[
                                    best_index
                                ],
                            ),
                            4,
                        ),
                        "margin": round(
                            margin,
                            4,
                        ),
                        "confidence_score": round(
                            confidence_score,
                            4,
                        ),
                        "confidence_level": _confidence_level(
                            confidence_score
                        ),
                        "source": "knowledge_base",
                    }

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

                if "admission" not in faq_topics:
                    continue

                if "date" not in faq_intents:
                    continue

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
                    0.30 * semantic_score
                    + 0.20 * intent_score
                    + 0.15 * keyword_score
                    + 0.10 * lexical_score
                    + 0.15 * topic_score
                    + 0.10 * question_type_score
                )

                direct_date_bonus = 0.0

                if asks_admission_deadline:
                    if re.search(
                        r"\b(last\s+date|application\s+deadline|deadline|closing\s+date)\b",
                        faq_question,
                    ):
                        direct_date_bonus += 0.35

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

                if "registration" not in faq_topics:
                    continue

                if "complaint" in faq_topics:
                    continue

                faq_question = normalize_text(
                    self.data.iloc[index]["question"]
                )

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

                routing_score = (
                    0.35 * semantic_score
                    + 0.20 * intent_score
                    + 0.15 * keyword_score
                    + 0.10 * lexical_score
                    + 0.15 * topic_score
                    + 0.05 * question_type_score
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
                        x["intent_score"],
                        x["keyword_score"],
                    ),
                    reverse=True,
                )

                selected = registration_candidates[0]

                selected_index = selected["index"]

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
                        selected["intent_score"],
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
        # Candidate generation
        # --------------------------------------------------------
        ranked_indexes = semantic_scores.argsort()[::-1][:TOP_K]

        candidates: List[Dict[str, Any]] = []

        # --------------------------------------------------------
        # Candidate scoring with enhanced intent weighting
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
            # Hard topic conflict - EXISTING functionality
            # --------------------------------------------
            if _topic_conflict(
                query_topics,
                faq_topics,
            ):
                continue

            # --------------------------------------------
            # Enhanced base score with intent priority
            # --------------------------------------------
            score = (
                semantic_score * SEMANTIC_WEIGHT
                + intent_score * INTENT_WEIGHT
                + keyword_score * KEYWORD_WEIGHT
                + lexical_score * LEXICAL_WEIGHT
                + topic_score * TOPIC_WEIGHT
                + question_type_score * QUESTION_TYPE_WEIGHT
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
            # Strong intent agreement - extra boost
            # --------------------------------------------
            if query_intents and intent_score >= 0.80:
                score += 0.08

            # ====================================================
            # IMPROVEMENT: Intent-Topic Pair Boosting
            # This helps distinguish between similar topics with different intents
            # ====================================================
            
            # Hostel Facilities vs Complaint distinction
            if "hostel" in query_topics:
                if "facilities" in normalized_query or "services" in normalized_query:
                    # Query wants facilities information
                    if "facilities" in faq_question or "services" in faq_question:
                        score += 0.15  # Boost for facilities FAQ
                    elif "complaint" in faq_topics or "complaint" in faq_question:
                        score -= 0.20  # Penalize complaint FAQ
                elif "complaint" in normalized_query or "issue" in normalized_query:
                    # Query wants complaint information
                    if "complaint" in faq_topics or "complaint" in faq_question:
                        score += 0.15
                    elif "facilities" in faq_question or "services" in faq_question:
                        score -= 0.10

            # Registration Deadline vs Procedure distinction
            if "registration" in query_topics:
                is_deadline_query = any(term in normalized_query for term in ["deadline", "last date", "date", "period", "closing"])
                if is_deadline_query:
                    # Query wants deadline/date information
                    if "deadline" in faq_question or "date" in faq_question or "last" in faq_question:
                        score += 0.20
                    elif "procedure" in faq_question or "steps" in faq_question or "how" in faq_question:
                        score -= 0.15
                else:
                    # Query wants procedure information
                    if "procedure" in faq_question or "steps" in faq_question:
                        score += 0.10
                    elif "deadline" in faq_question or "date" in faq_question:
                        score -= 0.10

            # Scholarship Availability distinction
            if "scholarship" in query_topics:
                if "availability" in normalized_query or "available" in normalized_query or "list" in normalized_query:
                    # Query wants list/availability of scholarships
                    if "list" in faq_question or "available" in faq_question or "types" in faq_question:
                        score += 0.15

            # ====================================================
            # e-Rozgaar / Freelancing Course Intent Protection
            # ====================================================
            is_rozgar_query = "rozgar" in query_topics or any(term in normalized_query for term in ["freelancing", "e-rozgaar", "erozgaar"])
            is_course_query = "courses" in query_topics or any(term in normalized_query for term in ["course", "courses", "skill", "skills", "training"])
            is_availability_query = "availability" in query_intents or "available" in normalized_query
            
            if is_rozgar_query:
                # Boost for FAQs that are about Rozgar/freelancing courses
                if "rozgar" in faq_topics:
                    score += 0.20
                    
                    # If the query is asking about available courses AND the FAQ is about courses
                    if is_availability_query and is_course_query:
                        # Check if the FAQ is specifically about courses available
                        if "course" in faq_question and any(term in faq_question for term in ["available", "offer", "provided"]):
                            score += 0.30
                        elif "course" in faq_question and "offer" in faq_question:
                            score += 0.25
                        elif "skill" in faq_question and any(term in faq_question for term in ["learn", "training"]):
                            score += 0.20
                        
                        # Penalize if the FAQ is about eligibility when query wants availability
                        if "eligibility" in faq_topics:
                            score -= 0.35
                    
                    # If the query is asking about eligibility
                    if "eligibility" in query_intents:
                        if "eligibility" in faq_topics:
                            score += 0.25
                        elif "availability" in faq_topics:
                            score -= 0.20

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

                if (
                    "registration" in faq_topics
                    and faq_is_course_registration
                    and not faq_is_complaint
                ):
                    score += 0.60

                if faq_is_complaint:
                    score -= 0.80

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
                item["intent_score"],  # Prioritize intent match
                item["semantic_score"],
                item["topic_score"],
                item["keyword_score"],
                item["lexical_score"],
            ),
            reverse=True,
        )

        best = candidates[0]

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
        # Confidence - now includes intent score
        # --------------------------------------------------------
        confidence_score = min(
            1.0,
            (
                0.60 * best["score"]
                + 0.20 * semantic_score
                + 0.10 * intent_score
                + 0.10 * min(1.0, margin * 5.0)
            ),
        )

        # ========================================================
        # IMPROVEMENT: Confidence boost for clear topic matches
        # ========================================================
        if topic_score >= 0.75 and intent_score >= 0.75:
            confidence_score = min(1.0, confidence_score + 0.10)

        if semantic_score >= 0.70 and topic_score >= 0.70:
            confidence_score = min(1.0, confidence_score + 0.08)

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


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("FAQ retriever loaded.")
    print("FAQ file:", faq_retriever.data_path)
    print("Rows:", len(faq_retriever.data))
    print("Word vectors:", faq_retriever.word_vectors.shape)
    print("Char vectors:", faq_retriever.char_vectors.shape)
    print("Knowledge articles:", len(faq_retriever.knowledge_articles) if hasattr(faq_retriever, 'knowledge_articles') else 0)
    
    # Test queries
    test_queries = [
        "I want to learn freelancing at e-Rozgaar. What courses are available?",
        "What is the last date to apply for admission?",
        "How do I reset my student portal password?",
        "Where is Khawaja Fareed Campus?",
        "Why can't I register for courses?",
        "What is the fee for BS Engineering?",
        "Who is the Dean of the Faculty of Computing?",
    ]
    
    print("\n" + "="*60)
    print("TESTING FAQ RETRIEVAL ENGINE")
    print("="*60)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 40)
        
        result = retrieve_faq(query)
        if result["found"]:
            print(f"Question: {result['question']}")
            print(f"Answer: {result['answer'][:200]}...")
            print(f"Confidence: {result['confidence_level']} ({result['confidence_score']})")
            print(f"Intent Score: {result['intent_score']}")
            print(f"Source: {result['source']}")
        else:
            print("No answer found.")