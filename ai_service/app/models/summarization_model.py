
import re
from sklearn.feature_extraction.text import TfidfVectorizer


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Clean whitespace and common joined-word problems.

    Does not change the meaning of the original text.
    """

    if not isinstance(text, str):
        return ""

    text = text.strip()

    if not text:
        return ""

    # --------------------------------------------------------
    # Normalize whitespace
    # --------------------------------------------------------

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    # --------------------------------------------------------
    # Fix missing spaces after punctuation
    # --------------------------------------------------------

    text = re.sub(
        r"([,;:])([A-Za-z])",
        r"\1 \2",
        text
    )

    text = re.sub(
        r"([.!?])([A-Za-z])",
        r"\1 \2",
        text
    )

    # --------------------------------------------------------
    # Fix common joined words
    # --------------------------------------------------------

    replacements = {

        r"\bIcan\b": "I can",
        r"\bIalso\b": "I also",
        r"\bIwant\b": "I want",
        r"\bIhave\b": "I have",
        r"\bIneed\b": "I need",
        r"\bIwould\b": "I would",
        r"\bIshould\b": "I should",
        r"\bIam\b": "I am",

        r"\bmytranscript\b": "my transcript",
        r"\bacademicadvisor\b": "academic advisor",
        r"\badditionalfee\b": "additional fee",
        r"\bscholarshipcan\b": "scholarship can",
        r"\buniversityfacilities\b": "university facilities",
        r"\bstudentportal\b": "student portal",

        r"\bknowthe\b": "know the",
        r"\bhowthe\b": "how the",
        r"\bwhatthe\b": "what the",
        r"\bwhenthe\b": "when the",
        r"\bwherethe\b": "where the",
        r"\bifthe\b": "if the",
        r"\bforthe\b": "for the",
        r"\btothe\b": "to the",
        r"\bfromthe\b": "from the",
        r"\bwiththe\b": "with the",
        r"\bandthe\b": "and the",
        r"\bknowabout\b": "know about",
        r"\bwantto\b": "want to",
        r"\bneedto\b": "need to",
        r"\bhowI\b": "how I",
        r"\bwhatI\b": "what I",
        r"\bwhereI\b": "where I",
        r"\bwhenI\b": "when I",
    }

    for pattern, replacement in replacements.items():

        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE
        )

    # --------------------------------------------------------
    # Clean spaces before punctuation
    # --------------------------------------------------------

    text = re.sub(
        r"\s+([,.;:!?])",
        r"\1",
        text
    )

    # --------------------------------------------------------
    # Final whitespace cleanup
    # --------------------------------------------------------

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# ============================================================
# SENTENCE SPLITTING
# ============================================================

def split_sentences(text: str):
    """
    Split text into sentences.
    """

    text = normalize_text(text)

    if not text:
        return []

    # Protect common abbreviations before sentence splitting.
    protected = re.sub(
        r"\b(Rs|Mr|Mrs|Ms|Dr|Prof|Sr|Jr|etc|e\.g|i\.e)\.\s*",
        lambda m: m.group(1).replace(".", "<DOT>") + " ",
        text,
        flags=re.IGNORECASE,
    )

    sentences = re.split(
        r"(?<=[.!?])\s+",
        protected,
    )

    sentences = [
        s.replace("<DOT>", ".").strip()
        for s in sentences
        if s.strip()
    ]

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


# ============================================================
# IMPORTANT TOPIC KEYWORDS
# ============================================================

TOPIC_KEYWORDS = {

    "registration": {
        "registration",
        "register",
        "course",
        "courses",
        "semester",
        "schedule",
        "required",
        "elective",
        "prerequisite",
        "prerequisites",
        "add",
        "adding",
        "drop",
        "dropping",
        "withdraw",
        "withdrawing",
    },

    "portal": {
        "portal",
        "password",
        "login",
        "log",
        "error",
        "reset",
        "student",
    },

    "scholarship": {
        "scholarship",
        "scholarships",
        "financial",
        "eligibility",
        "documents",
        "application",
        "deadline",
        "deadlines",
        "assistance",
    },

    "department": {
        "department",
        "advisor",
        "office",
        "support",
        "team",
        "contact",
    },

    "finance": {
        "fee",
        "fees",
        "financial",
        "payment",
        "charged",
        "cost",
    },

    "academic_record": {
        "transcript",
        "academic",
        "record",
        "gpa",
        "grade",
        "grades",
    },

    "admission": {
        "admission",
        "admissions",
        "eligibility",
        "program",
        "programs",
        "documents",
        "application",
    },
}


# ============================================================
# GENERIC SENTENCE FILTER
# ============================================================

GENERIC_PHRASES = [

    "in our series of letters",
    "in this article",
    "in this passage",
    "the author discusses",
    "the writer discusses",
    "this article discusses",
    "this passage discusses",
    "the text discusses",
    "the text provides",
    "this text provides",
    "in conclusion",
    "overall, the text",
    "the following is a summary",
    "i have been asked to provide a summary",
]


def is_generic_sentence(sentence: str) -> bool:
    """
    Return True for generic model-style sentences
    that should never appear in our summary.
    """

    lower = sentence.lower()

    return any(
        phrase in lower
        for phrase in GENERIC_PHRASES
    )


# ============================================================
# TOPIC DETECTION
# ============================================================

def detect_topics(sentence: str):
    """
    Detect which university-help topics a sentence contains.
    """

    words = set(
        re.findall(
            r"\b[a-zA-Z][a-zA-Z0-9'-]*\b",
            sentence.lower()
        )
    )

    detected = set()

    for topic, keywords in TOPIC_KEYWORDS.items():

        if words.intersection(keywords):

            detected.add(
                topic
            )

    return detected


# ============================================================
# TF-IDF SENTENCE SCORES
# ============================================================

def get_tfidf_scores(sentences):
    """
    Calculate TF-IDF importance for each sentence.
    """

    if not sentences:
        return []

    try:

        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2)
        )

        matrix = vectorizer.fit_transform(
            sentences
        )

        return matrix.sum(
            axis=1
        ).A1

    except Exception:

        return [
            float(
                len(sentence.split())
            )
            for sentence in sentences
        ]


# ============================================================
# SENTENCE SCORING
# ============================================================

def score_sentences(sentences):
    """
    Calculate importance score for every sentence.
    """

    tfidf_scores = get_tfidf_scores(
        sentences
    )

    results = []

    for index, sentence in enumerate(sentences):

        score = float(
            tfidf_scores[index]
        )

        topics = detect_topics(
            sentence
        )

        # Topic coverage bonus
        score += len(topics) * 0.8

        word_count = len(
            sentence.split()
        )

        # Prefer useful complete sentences
        if 10 <= word_count <= 45:
            score += 0.3

        # Avoid extremely short sentences
        if word_count < 6:
            score -= 0.5

        # Generic sentences should never be selected
        if is_generic_sentence(sentence):
            score = -1000

        results.append({
            "index": index,
            "score": score,
            "topics": topics,
            "sentence": sentence,
        })

    return results


# ============================================================
# TOPIC-COVERAGE SELECTION
# ============================================================

def select_summary_sentences(
    sentences,
    max_sentences=4,
    max_words=100
):
    """
    Select important sentences while trying to cover
    different topics.

    Only original sentences are returned.
    """

    if not sentences:
        return []

    # --------------------------------------------------------
    # Short input
    # --------------------------------------------------------

    if len(sentences) <= 2:

        return list(
            range(len(sentences))
        )

    # --------------------------------------------------------
    # Score sentences
    # --------------------------------------------------------

    scored = score_sentences(
        sentences
    )

    # --------------------------------------------------------
    # Sort by importance
    # --------------------------------------------------------

    ranked = sorted(
        scored,
        key=lambda item: item["score"],
        reverse=True
    )

    selected = []

    covered_topics = set()

    total_words = 0

    # --------------------------------------------------------
    # Pass 1:
    # Select sentences that introduce new topics.
    # --------------------------------------------------------

    for item in ranked:

        if len(selected) >= max_sentences:
            break

        if item["score"] <= -100:
            continue

        sentence = item["sentence"]

        topics = item["topics"]

        word_count = len(
            sentence.split()
        )

        new_topics = topics - covered_topics

        if not selected:

            selected.append(
                item["index"]
            )

            covered_topics.update(
                topics
            )

            total_words += word_count

            continue

        if (
            new_topics
            and total_words + word_count <= max_words
        ):

            selected.append(
                item["index"]
            )

            covered_topics.update(
                topics
            )

            total_words += word_count

    # --------------------------------------------------------
    # Pass 2:
    # Fill remaining slots by importance.
    # --------------------------------------------------------

    for item in ranked:

        if len(selected) >= max_sentences:
            break

        index = item["index"]

        if index in selected:
            continue

        if item["score"] <= -100:
            continue

        word_count = len(
            item["sentence"].split()
        )

        if (
            total_words + word_count
            <= max_words
        ):

            selected.append(
                index
            )

            total_words += word_count

    # --------------------------------------------------------
    # Safety fallback
    # --------------------------------------------------------

    if not selected:

        selected = [0]

    # --------------------------------------------------------
    # Restore original order
    # --------------------------------------------------------

    selected.sort()

    return selected


# ============================================================
# CLEAN SENTENCE
# ============================================================

def clean_sentence(sentence: str) -> str:
    """
    Final sentence cleanup.
    """

    sentence = normalize_text(
        sentence
    )

    if not sentence:
        return ""

    # Do not modify sentence content.
    # Only ensure natural ending.
    if sentence[-1] not in ".!?":
        sentence += "."

    return sentence


# ============================================================
# MAIN SUMMARIZATION FUNCTION
# ============================================================

def summarize_text(
    text: str,
    max_sentences: int = 2,
    max_words: int = 55
) -> str:
    """
    Fast extractive summarization.

    Rules:
    - No transformer model.
    - No hallucination.
    - No new information.
    - Uses original sentences only.
    - Short queries remain unchanged.
    - Long queries are shortened.
    - Important topics are preserved where possible.
    """

    if not isinstance(text, str):
        return ""

    # --------------------------------------------------------
    # Normalize input
    # --------------------------------------------------------

    text = normalize_text(
        text
    )

    if not text:
        return ""

    # --------------------------------------------------------
    # Split into sentences
    # --------------------------------------------------------

    sentences = split_sentences(
        text
    )

    if not sentences:
        return text

    # --------------------------------------------------------
    # One sentence
    # --------------------------------------------------------

    if len(sentences) == 1:

        return clean_sentence(
            sentences[0]
        )

    # --------------------------------------------------------
    # Two sentences
    # --------------------------------------------------------

    if len(sentences) == 2:

        # Keep both sentences for genuinely short tickets.
        if len(text.split()) <= 28:
            return " ".join(
                clean_sentence(sentence)
                for sentence in sentences
            )

        # For longer two-sentence tickets, keep the more informative
        # sentence using the same scoring system used elsewhere.
        scored = score_sentences(sentences)

        best = max(
            scored,
            key=lambda item: item["score"]
        )

        return clean_sentence(best["sentence"])

    # --------------------------------------------------------
    # Long input
    # --------------------------------------------------------

    selected_indexes = select_summary_sentences(
        sentences,
        max_sentences=max_sentences,
        max_words=max_words
    )

    # --------------------------------------------------------
    # Build summary
    # --------------------------------------------------------

    summary_sentences = [
        sentences[index]
        for index in selected_indexes
    ]

    summary = " ".join(
        clean_sentence(sentence)
        for sentence in summary_sentences
    )

    # --------------------------------------------------------
    # Final cleanup
    # --------------------------------------------------------

    summary = normalize_text(
        summary
    )

    # --------------------------------------------------------
    # Safety fallback
    # --------------------------------------------------------

    if not summary:
        return text

    return summary


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    test_text = (
        "I am a student at The Islamia University of Bahawalpur "
        "and I need help with my studies. "
        "I want to know about course registration for the upcoming "
        "semester and I am not sure about the registration date "
        "or schedule. "
        "I also want to know how to select required and elective "
        "courses and whether courses have prerequisites. "
        "If a required course is unavailable, I want to know what "
        "steps I should take and whether I need approval from my "
        "department or academic advisor. "
        "I have also forgotten my student portal password and "
        "sometimes receive an error when trying to log in. "
        "Finally, I want information about scholarships, eligibility "
        "requirements, required documents, application procedures, "
        "and deadlines."
    )

    print("SUMMARY:")
    print(
        summarize_text(
            test_text
        )
    )

