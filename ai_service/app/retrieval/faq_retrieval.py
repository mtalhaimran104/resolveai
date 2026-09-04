"""
ResolveAI - Improved FAQ Retrieval Engine
==========================================

Enhanced with intent-based ranking to distinguish between semantically similar
but intent-different questions (e.g., "courses available" vs "eligibility").

Key improvements:
- Enhanced question-type classification with multi-word detection
- Improved intent extraction with domain-specific patterns
- Dynamic intent-topic disambiguation for common confusions
- Better short query handling with topic/entity detection
- Enhanced synonym mapping from dataset analysis
- Improved confidence calibration with domain boosts
- Synthesized answer generation from multiple relevant FAQs
- Safe fallback with clear guidance for unseen questions

Version: 2.0
Last Updated: 2026-09-04
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import Counter

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# CONFIGURATION - OPTIMIZED THRESHOLDS
# ============================================================

FAQ_THRESHOLD = 0.30
TOP_K = 50  # Increased for better candidate pool

HIGH_CONFIDENCE_THRESHOLD = 0.78
MEDIUM_CONFIDENCE_THRESHOLD = 0.58

# Final ranking weights - optimized for intent-topic separation
SEMANTIC_WEIGHT = 0.35  # Reduced to allow intent to play bigger role
INTENT_WEIGHT = 0.25    # Increased - intent is critical for disambiguation
TOPIC_WEIGHT = 0.15     # Increased for better topic matching
KEYWORD_WEIGHT = 0.10
LEXICAL_WEIGHT = 0.05
QUESTION_TYPE_WEIGHT = 0.05
ENTITY_WEIGHT = 0.05    # New: explicit entity matching weight

# Extra confidence calibration
MARGIN_WEIGHT = 0.12

# Thresholds
MIN_SEMANTIC_FOR_TOPIC_MATCH = 0.20
MIN_SEMANTIC_GENERAL = 0.32
MIN_FINAL_SCORE = 0.30

# Domain-specific minimum scores (more lenient for known domains)
DOMAIN_MIN_SCORES = {
    "rozgar": 0.25,
    "admission": 0.27,
    "hostel": 0.27,
    "scholarship": 0.27,
}


# ============================================================
# ENHANCED TEXT NORMALIZATION
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

# Enhanced synonyms from dataset analysis
SYNONYMS = {
    # Password/account
    "recover": "reset",
    "recovery": "reset",
    "forgot": "reset",
    "forgotten": "reset",
    "lost": "reset",
    "unlock": "reset",
    "locked": "reset",
    
    # Fee related
    "cost": "fee",
    "costs": "fee",
    "fees": "fee",
    "charges": "fee",
    "charge": "fee",
    "price": "fee",
    "tuition": "fee",
    "payment": "fee",
    "payments": "fee",
    "dues": "fee",
    "installment": "fee",
    
    # Programs
    "programmes": "program",
    "programs": "program",
    "programme": "program",
    "course": "course",
    "courses": "course",
    "subject": "course",
    "subjects": "course",
    
    # Problem words
    "issue": "problem",
    "issues": "problem",
    "trouble": "problem",
    "error": "problem",
    "working": "problem",
    "works": "problem",
    "failed": "problem",
    "failure": "problem",
    "unable": "problem",
    "cannot": "problem",
    "cant": "problem",
    
    # Support
    "helpdesk": "support",
    "help": "support",
    "contact": "support",
    "assistance": "support",
    
    # Complaint
    "grievance": "complaint",
    "complain": "complaint",
    
    # Eligibility
    "eligible": "eligibility",
    "qualify": "eligibility",
    "criteria": "eligibility",
    "requirements": "eligibility",
    "prerequisite": "eligibility",
    
    # Availability
    "available": "available",
    "offer": "available",
    "offered": "available",
    "provide": "available",
    "provided": "available",
    "has": "available",
    "have": "available",
    
    # Registration
    "enroll": "registration",
    "enrollment": "registration",
    "register": "registration",
    "signup": "registration",
    
    # Date/deadline
    "deadline": "date",
    "last date": "date",
    "closing": "date",
    "schedule": "date",
    "timing": "date",
    
    # Rozgar
    "erozgaar": "rozgar",
    "e-rozgaar": "rozgar",
    "e-rozgar": "rozgar",
    "freelancing": "rozgar",
    "freelance": "rozgar",
    "freelancer": "rozgar",
}

# Enhanced stopwords - remove domain-specific words from stopwords
DOMAIN_KEYWORDS = {"rozgar", "freelancing", "admission", "hostel", "scholarship", 
                   "engineering", "lms", "portal", "registration", "examination",
                   "fee", "courses", "eligibility", "available", "complaint"}

# Remove domain keywords from stopwords
STOPWORDS = STOPWORDS - DOMAIN_KEYWORDS


def normalize_text(text: Any) -> str:
    """Normalize text while preserving useful domain words."""
    if text is None:
        return ""

    text = str(text).lower().strip()

    # Common punctuation/formatting normalization
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"[^a-z0-9\u0600-\u06ff\u0750-\u077f\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Handle common typos and variations
    text = re.sub(r"e-?rozgaar", "rozgar", text)
    text = re.sub(r"erozgaar", "rozgar", text)
    text = re.sub(r"freelanc", "freelancing", text)

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

# Question type patterns - enhanced with multi-word detection
QUESTION_TYPE_PATTERNS = {
    "what": {
        "what", "which", "name", "list", "types", "kinds", 
        "description", "overview", "information", "details",
        "tell me", "explain", "define", "identify", "characteristics"
    },
    "how": {
        "how", "procedure", "process", "steps", "method", 
        "way", "apply", "register", "reset", "recover", "change",
        "do", "does", "can", "will", "would", "should", "could"
    },
    "who": {
        "who", "person", "people", "dean", "professor", "doctor", 
        "prof", "chairman", "director", "head", "officer", "incharge",
        "coordinator", "advisor", "chief", "president", "vice chancellor"
    },
    "where": {
        "where", "location", "campus", "office", "place", "address", 
        "building", "department", "center", "block", "road", "near"
    },
    "when": {
        "when", "date", "deadline", "time", "schedule", "timing", 
        "opening", "closing", "start", "begin", "end", "duration",
        "month", "year", "session", "semester"
    },
    "why": {
        "why", "reason", "purpose", "benefit", "advantage",
        "because", "since", "due to", "cause"
    },
    "yes_no": {
        "is", "are", "am", "does", "do", "can", "could", "will", 
        "would", "should", "has", "have", "had", "was", "were",
        "shall", "may", "might", "must"
    }
}

# Enhanced intent categories with better weighting
INTENT_CATEGORIES = {
    "information": {
        "patterns": {"what", "which", "name", "list", "types", "kinds", 
                    "description", "overview", "information", "details", 
                    "tell", "about", "explain", "define", "identify"},
        "weight": 1.0
    },
    "procedure": {
        "patterns": {"how", "procedure", "process", "steps", "method", 
                    "way", "apply", "register", "reset", "recover", 
                    "change", "do", "make", "create", "submit", "fill"},
        "weight": 1.0
    },
    "eligibility": {
        "patterns": {"eligible", "eligibility", "criteria", "requirements", 
                    "qualify", "minimum", "required", "prerequisite", 
                    "condition", "need", "must have", "should have"},
        "weight": 1.2  # Higher weight for clarity
    },
    "availability": {
        "patterns": {"available", "offer", "offered", "provide", "provided", 
                    "has", "have", "list", "options", "choices", "selection",
                    "includes", "contain", "consist"},
        "weight": 1.0
    },
    "location": {
        "patterns": {"where", "location", "campus", "office", "place", 
                    "address", "building", "located", "find", "near",
                    "at", "in", "on", "inside", "outside", "beside"},
        "weight": 1.0
    },
    "person": {
        "patterns": {"who", "person", "people", "dean", "professor", 
                    "doctor", "prof", "chairman", "director", "head",
                    "officer", "incharge", "coordinator", "advisor"},
        "weight": 1.0
    },
    "date": {
        "patterns": {"when", "date", "deadline", "time", "schedule", 
                    "timing", "opening", "closing", "start", "begin",
                    "end", "duration", "period", "session", "semester"},
        "weight": 1.0
    },
    "fee": {
        "patterns": {"fee", "fees", "cost", "costs", "charge", "charges", 
                    "price", "tuition", "payment", "payments", "amount",
                    "rate", "discount", "refund", "installment"},
        "weight": 1.0
    },
    "problem": {
        "patterns": {"unable", "cannot", "cant", "working", "failed", 
                    "failure", "problem", "issue", "trouble", "error",
                    "not working", "doesn't work", "wrong", "incorrect"},
        "weight": 1.0
    },
    "complaint": {
        "patterns": {"complaint", "grievance", "complain", "concern",
                    "harassment", "discrimination", "abuse", "violation",
                    "unfair", "mistreatment", "bullying"},
        "weight": 1.0
    }
}


def detect_question_type(text: str) -> str:
    """Detect the primary question type with improved detection."""
    normalized = normalize_text(text)
    words = normalized.split()
    
    # First, check for explicit question markers
    if "?" in text:
        # Question mark often indicates a direct question
        pass
    
    # Check for question type patterns with multi-word support
    for qtype, patterns in QUESTION_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in normalized:
                # For yes/no questions, check if it's actually a yes/no
                if qtype == "yes_no":
                    # Check if the question is actually asking about something else
                    # If it starts with a question word, it's not yes/no
                    question_words = {"what", "how", "who", "where", "when", "why", "which"}
                    if any(word in words[:2] for word in question_words):
                        continue
                return qtype
    
    # Check the first word as a fallback
    if words:
        first_word = words[0]
        for qtype, patterns in QUESTION_TYPE_PATTERNS.items():
            if first_word in patterns:
                return qtype
    
    # Default based on content
    if any(word in normalized for word in ["list", "types", "kinds", "name"]):
        return "what"
    elif any(word in normalized for word in ["step", "procedure", "method"]):
        return "how"
    
    return "what"


def extract_intent(text: str) -> str:
    """
    Extract the primary intent category from a query or FAQ question.
    Enhanced with better disambiguation.
    """
    normalized = normalize_text(text)
    
    # Check for strong intent indicators with priority
    intent_scores = {}
    
    for intent, data in INTENT_CATEGORIES.items():
        score = 0.0
        patterns = data.get("patterns", set())
        weight = data.get("weight", 1.0)
        
        for pattern in patterns:
            if pattern in normalized:
                # Weight matches by length for better matching
                if len(pattern.split()) > 1:  # Multi-word pattern
                    score += weight * 2.0
                else:
                    score += weight
        
        # Additional context for specific intents
        if intent == "availability" and any(w in normalized for w in ["course", "program", "skill", "training"]):
            score += 0.5
        elif intent == "eligibility" and any(w in normalized for w in ["admission", "apply", "program"]):
            score += 0.5
        elif intent == "fee" and any(w in normalized for w in ["semester", "tuition", "admission"]):
            score += 0.5
        elif intent == "procedure" and any(w in normalized for w in ["register", "apply", "submit", "complete"]):
            score += 0.5
        
        if score > 0:
            intent_scores[intent] = score
    
    if not intent_scores:
        return "information"
    
    # Return the intent with the highest score
    return max(intent_scores, key=intent_scores.get)


def extract_intents(text: Any) -> Set[str]:
    """Legacy function for backward compatibility."""
    primary_intent = extract_intent(text)
    if primary_intent:
        return {primary_intent}
    return set()


# ============================================================
# ENHANCED TOPIC EXTRACTION WITH DOMAIN PATTERNS
# ============================================================

def extract_topics(text: Any) -> Set[str]:
    """Detect canonical domain topics with enhanced patterns."""
    normalized = normalize_text(text)
    keywords = extract_keywords(text)
    topics: Set[str] = set()

    # Domain-specific topic patterns - ENHANCED from dataset analysis
    topic_patterns = {
        "password": {"password", "reset", "forgot", "recover", "recovery", "login", 
                    "credential", "change password", "forgotten", "locked", "unlock"},
        "lms": {"lms", "learning", "moodle", "canvas", "blackboard", "online learning", 
               "virtual", "lms account", "lms portal"},
        "portal": {"portal", "student portal", "login", "account", "dashboard", 
                  "eportal", "iub portal", "myiub"},
        "registration": {"register", "registration", "enroll", "enrollment", "add course", 
                        "drop course", "course registration", "semester registration"},
        "engineering": {"engineering", "telecommunication", "electrical", "biomedical", 
                       "robotics", "aircraft", "aviation", "mechanical", "civil",
                       "software engineering", "computer engineering"},
        "fee": {"fee", "fees", "cost", "costs", "charge", "charges", "tuition", "price", 
               "payment", "dues", "installment", "semester fee", "challan"},
        "quantum": {"quantum", "computing", "algorithm", "quantum information", 
                   "quantum computing", "quantum algorithm"},
        "complaint": {"complaint", "grievance", "complain", "issue", "problem", "concern",
                     "harassment", "discrimination"},
        "admission": {"admission", "admissions", "apply", "application", "enroll", 
                     "deadline", "prospectus", "entry test", "merit list", "merit"},
        "scholarship": {"scholarship", "financial aid", "stipend", "honhaar", 
                       "financial assistance", "need based", "merit scholarship"},
        "migration": {"migration", "migrate", "transfer", "change program", "noc"},
        "hostel": {"hostel", "accommodation", "room", "dormitory", "residence", 
                  "facilities", "hostel fee", "hostel admission", "warden"},
        "library": {"library", "books", "timing", "reading room", "e-library", 
                   "digital library", "borrow", "return"},
        "support": {"support", "helpdesk", "help", "contact", "it support", 
                   "technical support", "assistance"},
        "eligibility": {"eligible", "eligibility", "criteria", "requirements", "qualify", 
                       "prerequisite", "minimum", "condition"},
        "availability": {"available", "offer", "offered", "provide", "provided", "has", 
                        "have", "list", "options", "choices", "selection", "includes"},
        "rozgar": {"rozgar", "erozgaar", "e-rozgaar", "freelancing", "freelance", 
                  "freelancer", "e-rozgar", "rozgar center"},
        "courses": {"course", "courses", "skill", "skills", "training", "learn", 
                   "learning", "program", "programs", "curriculum", "subjects"},
        "examination": {"exam", "examination", "test", "quiz", "midterm", "final", 
                       "result", "grade", "gpa", "transcript", "roll number"},
        "transport": {"transport", "bus", "shuttle", "vehicle", "pickup", "drop off",
                     "road permit", "parking"},
        "facilities": {"facilities", "services", "amenities", "infrastructure", "lab", 
                      "laboratory", "cafeteria", "bank", "mosque"},
        "internship": {"internship", "intern", "training", "placement", "career", "job",
                      "career counseling", "ccpc"},
        "campus": {"campus", "abasisa", "baghdad", "khawaja", "fareed", "ryk", 
                  "bahawalnagar", "liaquatpur", "ahmadpur"},
        "professor": {"professor", "dean", "director", "chairman", "head", "incharge",
                     "vice chancellor", "registrar", "controller"},
    }

    for topic, words in topic_patterns.items():
        if keywords.intersection(words):
            topics.add(topic)

    # Special case for e-Rozgaar - comprehensive detection
    rozgar_terms = {"rozgar", "erozgaar", "e-rozgaar", "freelancing", "freelance", "e-rozgar"}
    if any(term in normalized for term in rozgar_terms):
        topics.add("rozgar")
        # Determine specific intent
        if "course" in normalized or "skill" in normalized or "training" in normalized or "learn" in normalized:
            topics.add("courses")
            topics.add("availability")
        if "eligible" in normalized or "eligibility" in normalized or "criteria" in normalized:
            topics.add("eligibility")
    
    # Special case for admission - detect date vs procedure
    if "admission" in normalized:
        topics.add("admission")
        if "date" in normalized or "deadline" in normalized or "last" in normalized or "closing" in normalized:
            topics.add("date")
        if "procedure" in normalized or "process" in normalized or "steps" in normalized or "how" in normalized:
            topics.add("procedure")
        if "eligible" in normalized or "eligibility" in normalized or "criteria" in normalized:
            topics.add("eligibility")

    # Special case for hostel - detect facilities vs complaint
    if "hostel" in normalized:
        topics.add("hostel")
        if "facility" in normalized or "service" in normalized or "available" in normalized or "provide" in normalized:
            topics.add("facilities")
        if "complaint" in normalized or "issue" in normalized or "problem" in normalized or "grievance" in normalized:
            topics.add("complaint")

    # Special case for scholarship
    if "scholarship" in normalized:
        topics.add("scholarship")
        if "available" in normalized or "list" in normalized or "types" in normalized:
            topics.add("availability")
        if "apply" in normalized or "application" in normalized or "procedure" in normalized:
            topics.add("procedure")

    # Special case for LMS
    if "lms" in normalized:
        topics.add("lms")
        if "password" in normalized or "reset" in normalized or "forgot" in normalized:
            topics.add("password")
        if "access" in normalized or "login" in normalized or "log in" in normalized:
            topics.add("portal")

    return topics


def _question_type(text: Any) -> str:
    """Legacy function for backward compatibility."""
    return detect_question_type(text)


def _intent_score(query_intents: Set[str], faq_intents: Set[str]) -> float:
    """Calculate intent similarity score with better matching."""
    if not query_intents or not faq_intents:
        return 0.0
    
    # If either has "information" and the other has a specific intent
    if "information" in query_intents and len(query_intents) == 1:
        # Generic information query - should match many FAQs
        return 0.5
    
    overlap = query_intents.intersection(faq_intents)
    
    if not overlap:
        # Check for related intents with weighted scores
        related_pairs = {
            ("information", "availability"): 0.6,
            ("information", "procedure"): 0.5,
            ("information", "eligibility"): 0.5,
            ("information", "fee"): 0.4,
            ("availability", "information"): 0.6,
            ("eligibility", "information"): 0.5,
            ("procedure", "information"): 0.5,
            ("fee", "information"): 0.4,
            ("fee", "procedure"): 0.3,
            ("availability", "eligibility"): 0.2,  # Very different - should not match well
            ("eligibility", "availability"): 0.2,
            ("complaint", "information"): 0.3,
            ("problem", "information"): 0.4,
            ("problem", "complaint"): 0.7,
            ("complaint", "problem"): 0.7,
            ("date", "information"): 0.5,
            ("date", "schedule"): 0.6,
        }
        
        for intent in query_intents:
            for faq_intent in faq_intents:
                pair = (intent, faq_intent)
                if pair in related_pairs:
                    return related_pairs[pair]
        
        return 0.0
    
    # Weighted by number of matching intents and importance
    return len(overlap) / max(1, len(query_intents))


def _type_score(query_type: str, faq_type: str) -> float:
    """Calculate question type similarity with enhanced relations."""
    if query_type == faq_type:
        return 1.0

    # Enhanced related types
    related = {
        ("what", "how"): 0.4,
        ("how", "what"): 0.4,
        ("what", "yes_no"): 0.5,
        ("yes_no", "what"): 0.5,
        ("where", "what"): 0.4,
        ("what", "where"): 0.4,
        ("when", "what"): 0.4,
        ("what", "when"): 0.4,
        ("who", "what"): 0.4,
        ("what", "who"): 0.4,
        ("how", "procedure"): 0.8,
        ("procedure", "how"): 0.8,
        ("where", "location"): 0.8,
        ("when", "date"): 0.8,
        ("who", "person"): 0.8,
        ("why", "information"): 0.5,
        ("what", "information"): 0.5,
    }

    return related.get((query_type, faq_type), 0.0)


# ============================================================
# ENHANCED SCORING HELPERS
# ============================================================

def _keyword_score(query_keywords: Set[str], faq_keywords: Set[str]) -> float:
    if not query_keywords or not faq_keywords:
        return 0.0

    overlap = query_keywords.intersection(faq_keywords)

    # Recall against query is important for short user questions
    query_recall = len(overlap) / max(1, len(query_keywords))

    # Precision prevents one common word from looking perfect
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
        # Check for related topics
        related_topics = {
            ("rozgar", "courses"): 0.6,
            ("courses", "rozgar"): 0.6,
            ("rozgar", "availability"): 0.5,
            ("availability", "rozgar"): 0.5,
            ("admission", "registration"): 0.4,
            ("registration", "admission"): 0.4,
            ("hostel", "facilities"): 0.6,
            ("facilities", "hostel"): 0.6,
            ("scholarship", "fee"): 0.3,
            ("fee", "scholarship"): 0.3,
            ("lms", "portal"): 0.4,
            ("portal", "lms"): 0.4,
            ("examination", "result"): 0.6,
            ("result", "examination"): 0.6,
        }
        for q_topic in query_topics:
            for f_topic in faq_topics:
                pair = (q_topic, f_topic)
                if pair in related_topics:
                    return related_topics[pair]
        return 0.0

    return len(overlap) / max(1, len(query_topics))


def _topic_conflict(query_topics: Set[str], faq_topics: Set[str]) -> bool:
    """
    Prevent dangerous cross-topic matches.
    Enhanced with more conflict pairs from dataset analysis.
    """
    conflict_pairs = [
        # Strong conflicts - completely different topics
        ("availability", "eligibility"),
        ("eligibility", "availability"),
        ("complaint", "facilities"),
        ("facilities", "complaint"),
        ("fee", "scholarship"),
        ("scholarship", "fee"),
        ("lms", "portal"),
        ("portal", "lms"),
        ("registration", "date"),
        ("date", "registration"),
        ("password", "registration"),
        ("registration", "password"),
        
        # Medium conflicts - context dependent
        ("hostel", "engineering"),
        ("engineering", "hostel"),
        ("quantum", "hostel"),
        ("hostel", "quantum"),
        ("examination", "hostel"),
        ("hostel", "examination"),
        ("transport", "hostel"),
        ("hostel", "transport"),
        ("library", "hostel"),
        ("hostel", "library"),
    ]

    for a, b in conflict_pairs:
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
        "vice chancellor",
        "controller of examinations",
        "quality enhancement cell",
        "qec",
        "oric",
        "career counseling",
        "enabling center",
        "accessibility center",
    ]

    for phrase in protected_phrases:
        if phrase in q and phrase in f:
            return True

    # Names: if the query contains a distinctive normalized pair
    words = q.split()
    for i in range(len(words) - 1):
        pair = f"{words[i]} {words[i + 1]}"
        if len(words[i]) >= 4 and len(words[i + 1]) >= 4 and pair in f:
            return True

    return False


# ============================================================
# DATA LOADING
# ============================================================

def _find_data_file() -> Optional[Path]:
    """Find the FAQ dataset safely."""
    env_path = os.getenv("FAQ_DATA_PATH") or os.getenv("FAQ_FILE")
    here = Path(__file__).resolve()

    # Current repository layout
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

    # First pass: exact preferred files
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

    # Final fallback: search only FAQ/knowledge/question-like filenames
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

    # Normalize column names
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

    # Remove completely empty records
    df = df[
        (df["question"].str.strip() != "")
        & (df["answer"].str.strip() != "")
    ].reset_index(drop=True)

    return df


# ============================================================
# GENERIC FALLBACK RESPONSE
# ============================================================

def get_fallback_response(query: str) -> Dict[str, Any]:
    """Generate a safe fallback response when no good FAQ match exists."""
    return {
        "found": False,
        "answer": (
            "I couldn't find a specific answer to your question in the IUB FAQ database. "
            "For accurate information, please contact the IUB Information Center at "
            "0346-9255555 or 062-9255580, or visit the official IUB website at "
            "https://www.iub.edu.pk. You can also email iubhelpline@iub.edu.pk for assistance."
        ),
        "question": query,
        "score": 0.0,
        "similarity_score": 0.0,
        "confidence_score": 0.0,
        "confidence_level": "Low",
        "source": "fallback",
        "semantic_score": 0.0,
        "keyword_score": 0.0,
        "lexical_score": 0.0,
        "topic_score": 0.0,
        "intent_score": 0.0,
        "question_type": detect_question_type(query),
        "question_type_score": 0.0,
        "margin": 0.0,
    }


# ============================================================
# FAQ RETRIEVER - MAIN CLASS
# ============================================================

class FAQRetriever:
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = None
        self.data = pd.DataFrame()
        self.normalized_questions = []
        self.word_vectorizer = None
        self.char_vectorizer = None
        self.word_vectors = None
        self.char_vectors = None
        self.question_keywords = []
        self.question_topics = []
        self.question_intents = []
        self.question_types = []
        
        # Knowledge Base
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
        
        # Load data
        self._load_data(data_path)
        
    def _load_data(self, data_path: Optional[str] = None):
        """Load FAQ data and build indexes."""
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

        # Use both word and character TF-IDF
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
            detect_question_type(x)
            for x in self.normalized_questions
        ]

        # Load Knowledge Base articles if available
        self._load_knowledge_base()
        
    def _load_knowledge_base(self):
        """Load Knowledge Base articles."""
        try:
            from app.core.ai_service_helper import AIServiceHelper

            self.knowledge_articles = [
                dict(row)
                for row in AIServiceHelper.getKnowledgeBaseArticles()
            ]

            # Build a searchable document from title + excerpt + content
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
                detect_question_type(str(article.get("title") or ""))
                for article in self.knowledge_articles
            ]

            # Dedicated TF-IDF for Knowledge Base articles
            if self.kb_documents:
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
            # Knowledge Base not available - continue with FAQ only
            pass

    # ============================================================
    # CANDIDATE GENERATION
    # ============================================================

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

    # ============================================================
    # EXACT MATCHING
    # ============================================================

    def _exact_match(
        self,
        query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
    ) -> Optional[Dict[str, Any]]:

        normalized_query = normalize_text(query)

        # Exact normalized question
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

        # Strong phrase/entity match with very high lexical overlap
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

    # ============================================================
    # SYNTHESIZED ANSWER GENERATION
    # ============================================================

    def _synthesize_answer(self, query: str, candidates: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Generate a synthesized answer from multiple relevant FAQs when appropriate.
        """
        if not candidates or len(candidates) < 2:
            return None

        # Check if candidates are from the same domain/topic
        top_candidates = candidates[:3]
        topics = [c.get("topic_score", 0) for c in top_candidates]
        intents = [c.get("intent_score", 0) for c in top_candidates]
        
        # Only synthesize if they're all from the same domain
        if not all(t >= 0.3 for t in topics):
            return None
            
        # Check if they're complementary (different aspects of same topic)
        faq_questions = []
        faq_answers = []
        combined_score = 0
        
        for c in top_candidates:
            if c.get("score", 0) > 0.4:
                idx = c["index"]
                faq_questions.append(self.data.iloc[idx]["question"])
                faq_answers.append(self.data.iloc[idx]["answer"])
                combined_score += c.get("score", 0)
        
        if len(faq_questions) < 2:
            return None
            
        combined_score = min(1.0, combined_score / len(faq_questions) + 0.1)
        
        # Check if answers are complementary (not duplicates)
        # Simple check: if answers are too similar, don't synthesize
        answer_texts = " ".join(faq_answers)
        if len(set(answer_texts.split())) < 20:
            return None
            
        # Build synthesized answer
        synthesized = "Here's what I found:\n\n"
        for i, (q, a) in enumerate(zip(faq_questions, faq_answers), 1):
            synthesized += f"{i}. {q}\n   {a.strip()}\n\n"
        
        synthesized += "For more details, please contact the IUB Information Center."
        
        return {
            "answer": synthesized,
            "question": query,
            "score": round(combined_score, 4),
            "semantic_score": round(combined_score, 4),
            "keyword_score": round(combined_score * 0.8, 4),
            "lexical_score": round(combined_score * 0.7, 4),
            "topic_score": round(max(topics), 4),
            "intent_score": round(max(intents), 4),
            "question_type": detect_question_type(query),
            "question_type_score": round(0.5, 4),
            "margin": round(0.1, 4),
            "confidence_score": round(min(1.0, combined_score + 0.1), 4),
            "confidence_level": _confidence_level(min(1.0, combined_score + 0.1)),
            "source": "synthesized_faq",
            "answer_length": len(synthesized),
            "question_length": len(query),
        }

    # ============================================================
    # MAIN RETRIEVAL
    # ============================================================

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
        query_type = detect_question_type(query)

        if not query_keywords:
            return get_fallback_response(query)

        normalized_query = normalize_text(query)

        # Detect if this is a domain-specific query that deserves more leniency
        is_domain_specific = (
            "rozgar" in query_topics
            or "rozgar" in normalized_query
            or "freelancing" in normalized_query
            or "admission" in query_topics
            or "hostel" in query_topics
            or "scholarship" in query_topics
        )

        # ========================================================
        # KNOWLEDGE BASE RETRIEVAL
        # ========================================================
        if (
            self.knowledge_articles
            and self.kb_word_vectorizer is not None
            and self.kb_char_vectorizer is not None
            and self.kb_word_vectors is not None
            and self.kb_char_vectors is not None
            and len(self.knowledge_articles) > 0
        ):
            kb_result = self._retrieve_knowledge_base(
                query, normalized_query, query_keywords, query_topics, 
                query_intents, query_type
            )
            if kb_result:
                return kb_result

        # ========================================================
        # EXACT MATCH
        # ========================================================
        exact = self._exact_match(
            query,
            query_keywords,
            query_topics,
            query_intents,
        )

        if exact is not None:
            return exact

        # ========================================================
        # SEMANTIC SCORES
        # ========================================================
        semantic_scores, word_scores, char_scores = self._semantic_scores(
            query
        )

        # ========================================================
        # DOMAIN-SPECIFIC ROUTING
        # ========================================================
        
        # Check for admission date/deadline queries
        if "admission" in query_topics and "date" in query_intents:
            result = self._route_admission_date(
                query, normalized_query, query_keywords, query_topics,
                query_intents, query_type, semantic_scores
            )
            if result:
                return result

        # Check for course registration problems
        if "registration" in query_topics and "problem" in query_intents:
            result = self._route_course_registration(
                query, normalized_query, query_keywords, query_topics,
                query_intents, query_type, semantic_scores
            )
            if result:
                return result

        # Check for e-Rozgaar/freelancing queries
        if "rozgar" in query_topics or any(term in normalized_query for term in ["rozgar", "freelancing", "e-rozgaar"]):
            result = self._route_rozgar(
                query, normalized_query, query_keywords, query_topics,
                query_intents, query_type, semantic_scores
            )
            if result:
                return result

        # Check for hostel queries (facilities vs complaint)
        if "hostel" in query_topics:
            result = self._route_hostel(
                query, normalized_query, query_keywords, query_topics,
                query_intents, query_type, semantic_scores
            )
            if result:
                return result

        # ========================================================
        # CANDIDATE GENERATION
        # ========================================================
        ranked_indexes = semantic_scores.argsort()[::-1][:TOP_K]

        candidates: List[Dict[str, Any]] = []

        for index in ranked_indexes:
            faq_question = normalize_text(
                self.data.iloc[index]["question"]
            )

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

            entity_match = _contains_strong_entity(
                query,
                self.data.iloc[index]["question"],
            )

            # Hard topic conflict check
            if _topic_conflict(query_topics, faq_topics):
                # For domain-specific queries, be more lenient
                if not is_domain_specific or topic_score < 0.1:
                    continue

            # Base score with intent priority
            score = (
                semantic_score * SEMANTIC_WEIGHT
                + intent_score * INTENT_WEIGHT
                + topic_score * TOPIC_WEIGHT
                + keyword_score * KEYWORD_WEIGHT
                + lexical_score * LEXICAL_WEIGHT
                + question_type_score * QUESTION_TYPE_WEIGHT
                + (0.15 if entity_match else 0) * ENTITY_WEIGHT
            )

            # Intent-topic pair boosting - critical for disambiguation
            score = self._apply_intent_topic_boost(
                query, normalized_query, query_topics, query_intents,
                faq_question, faq_topics, faq_intents, score
            )

            score = max(0.0, min(1.0, score))

            candidates.append({
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
            })

        if not candidates:
            return get_fallback_response(query)

        # Sort by score, with intent as tie-breaker
        candidates.sort(
            key=lambda item: (
                item["score"],
                item["intent_score"],
                item["topic_score"],
                item["semantic_score"],
            ),
            reverse=True,
        )

        # Try to synthesize answer from multiple relevant candidates
        if len(candidates) >= 2:
            synthesized = self._synthesize_answer(query, candidates)
            if synthesized:
                return synthesized

        best = candidates[0]
        index = best["index"]
        semantic_score = best["semantic_score"]
        keyword_score = best["keyword_score"]
        lexical_score = best["lexical_score"]
        topic_score = best["topic_score"]
        intent_score = best["intent_score"]
        type_score = best["question_type_score"]

        # Calculate margin
        sorted_scores = sorted([c["score"] for c in candidates], reverse=True)
        if len(sorted_scores) >= 2:
            margin = max(0.0, best["score"] - sorted_scores[1])
        else:
            margin = best["score"]

        # Final acceptance with domain-specific leniency
        min_score = DOMAIN_MIN_SCORES.get(
            next((t for t in query_topics if t in DOMAIN_MIN_SCORES), None),
            MIN_FINAL_SCORE
        )
        
        if is_domain_specific:
            min_score = min_score - 0.04

        if best["score"] < min_score:
            return get_fallback_response(query)

        # Semantic check with domain leniency
        if is_domain_specific:
            min_semantic = MIN_SEMANTIC_FOR_TOPIC_MATCH - 0.03
        else:
            min_semantic = MIN_SEMANTIC_FOR_TOPIC_MATCH

        if query_topics:
            if topic_score < 0.4 and semantic_score < min_semantic and not best.get("entity_match", False):
                return get_fallback_response(query)
        else:
            if semantic_score < MIN_SEMANTIC_GENERAL and not best.get("entity_match", False):
                return get_fallback_response(query)

        # Ambiguous match check with domain leniency
        if not is_domain_specific:
            if semantic_score < 0.42 and margin < 0.015 and topic_score < 0.75 and not best.get("entity_match", False):
                return get_fallback_response(query)
        else:
            if semantic_score < 0.38 and margin < 0.01 and topic_score < 0.65 and not best.get("entity_match", False):
                return get_fallback_response(query)

        # Confidence score
        confidence_score = min(1.0, (
            0.55 * best["score"]
            + 0.15 * semantic_score
            + 0.12 * intent_score
            + 0.10 * topic_score
            + 0.08 * min(1.0, margin * 5.0)
        ))

        # Domain-specific confidence boosts
        if "rozgar" in query_topics:
            if "rozgar" in self.question_topics[index]:
                confidence_score = min(1.0, confidence_score + 0.12)
        if "admission" in query_topics and "date" in query_intents:
            if "admission" in self.question_topics[index] and "date" in self.question_intents[index]:
                confidence_score = min(1.0, confidence_score + 0.15)
        if topic_score >= 0.75 and intent_score >= 0.75:
            confidence_score = min(1.0, confidence_score + 0.10)
        if best.get("entity_match", False):
            confidence_score = min(1.0, confidence_score + 0.10)

        confidence_level = _confidence_level(confidence_score)

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

    # ============================================================
    # DOMAIN-SPECIFIC ROUTING FUNCTIONS
    # ============================================================

    def _apply_intent_topic_boost(
        self,
        query: str,
        normalized_query: str,
        query_topics: Set[str],
        query_intents: Set[str],
        faq_question: str,
        faq_topics: Set[str],
        faq_intents: Set[str],
        score: float
    ) -> float:
        """Apply intent-topic pair boosting for disambiguation."""
        
        # Hostel Facilities vs Complaint
        if "hostel" in query_topics:
            is_facilities_query = any(term in normalized_query for term in ["facilities", "services", "available", "provide"])
            is_complaint_query = any(term in normalized_query for term in ["complaint", "issue", "problem", "grievance"])
            
            if is_facilities_query:
                if "facilities" in faq_topics or "facilities" in faq_question:
                    score += 0.15
                elif "complaint" in faq_topics or "complaint" in faq_question:
                    score -= 0.25
            elif is_complaint_query:
                if "complaint" in faq_topics or "complaint" in faq_question:
                    score += 0.15
                elif "facilities" in faq_topics or "facilities" in faq_question:
                    score -= 0.15

        # Registration Deadline vs Procedure
        if "registration" in query_topics:
            is_deadline_query = any(term in normalized_query for term in ["deadline", "last date", "date", "closing"])
            if is_deadline_query:
                if "date" in faq_topics or "deadline" in faq_question:
                    score += 0.20
                elif "procedure" in faq_intents or "steps" in faq_question:
                    score -= 0.20
            else:
                if "procedure" in faq_intents or "steps" in faq_question:
                    score += 0.10
                elif "date" in faq_topics or "deadline" in faq_question:
                    score -= 0.15

        # LMS vs Portal for password queries
        if "password" in query_topics:
            if "lms" in query_topics:
                if "lms" in faq_topics:
                    score += 0.20
                elif "portal" in faq_topics:
                    score -= 0.15
            elif "portal" in query_topics:
                if "portal" in faq_topics:
                    score += 0.18
                elif "lms" in faq_topics:
                    score -= 0.15

        # Scholarship queries
        if "scholarship" in query_topics:
            if "available" in normalized_query or "list" in normalized_query:
                if "availability" in faq_intents:
                    score += 0.15
            if "apply" in normalized_query or "application" in normalized_query:
                if "procedure" in faq_intents:
                    score += 0.10

        return score

    def _retrieve_knowledge_base(
        self,
        query: str,
        normalized_query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
        query_type: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve from Knowledge Base with article priority."""
        if not self.kb_documents:
            return None

        kb_word_query = self.kb_word_vectorizer.transform([normalized_query])
        kb_char_query = self.kb_char_vectorizer.transform([normalized_query])

        kb_word_scores = cosine_similarity(
            kb_word_query,
            self.kb_word_vectors,
        )[0]

        kb_char_scores = cosine_similarity(
            kb_char_query,
            self.kb_char_vectors,
        )[0]

        kb_semantic_scores = 0.75 * kb_word_scores + 0.25 * kb_char_scores

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

            # Topic conflict check
            if _topic_conflict(query_topics, article_topics):
                continue

            semantic_score = float(kb_semantic_scores[idx])
            keyword_score = _keyword_score(query_keywords, article_keywords)
            lexical_score = _lexical_similarity(query_keywords, extract_keywords(title))
            topic_score = _topic_score(query_topics, article_topics)
            intent_score = _intent_score(query_intents, self.kb_intents[idx])
            question_type_score = _type_score(query_type, self.kb_types[idx])

            normalized_title = normalize_text(title)
            exact_title_match = normalized_query == normalized_title
            title_contains_query = normalized_query in normalized_title if normalized_query else False

            combined_score = (
                0.40 * semantic_score
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

            # Domain-specific boosts
            if "rozgar" in query_topics and "rozgar" in article_topics:
                combined_score += 0.30
            if "admission" in query_topics and "admission" in article_topics:
                if "date" in query_intents and "date" in self.kb_intents[idx]:
                    combined_score += 0.30

            combined_score = max(0.0, min(1.0, combined_score))

            if combined_score > best_score:
                second_best_score = best_score
                best_score = combined_score
                best_article = article
                best_index = idx
            elif combined_score > second_best_score:
                second_best_score = combined_score

        if best_article is not None:
            margin = max(0.0, best_score - second_best_score)
            confidence_score = min(1.0, (
                0.60 * best_score
                + 0.25 * float(kb_semantic_scores[best_index])
                + 0.15 * min(1.0, margin * 5.0)
            ))

            strong_kb_match = (
                (best_score >= 0.50 and float(kb_semantic_scores[best_index]) >= 0.30)
                or (best_score >= 0.42 and margin >= 0.08)
                or (float(kb_semantic_scores[best_index]) >= 0.70 and margin >= 0.03)
            )

            if strong_kb_match:
                best = self.knowledge_articles[best_index]
                return {
                    "answer": str(best.get("content") or ""),
                    "question": str(best.get("title") or ""),
                    "score": round(best_score, 4),
                    "semantic_score": round(float(kb_semantic_scores[best_index]), 4),
                    "keyword_score": round(_keyword_score(query_keywords, self.kb_keywords[best_index]), 4),
                    "lexical_score": round(_lexical_similarity(query_keywords, extract_keywords(str(best.get("title") or ""))), 4),
                    "topic_score": round(_topic_score(query_topics, self.kb_topics[best_index]), 4),
                    "intent_score": round(_intent_score(query_intents, self.kb_intents[best_index]), 4),
                    "question_type": self.kb_types[best_index],
                    "question_type_score": round(_type_score(query_type, self.kb_types[best_index]), 4),
                    "margin": round(margin, 4),
                    "confidence_score": round(confidence_score, 4),
                    "confidence_level": _confidence_level(confidence_score),
                    "source": "knowledge_base",
                    "answer_length": len(str(best.get("content") or "")),
                    "question_length": len(str(best.get("title") or "")),
                }

        return None

    def _route_admission_date(
        self,
        query: str,
        normalized_query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
        query_type: str,
        semantic_scores: Any
    ) -> Optional[Dict[str, Any]]:
        """Route admission date/deadline queries."""
        admission_date_candidates = []

        asks_deadline = "deadline" in normalized_query or "last date" in normalized_query or "closing" in normalized_query
        asks_opening = "open" in normalized_query or "opening" in normalized_query

        for index in range(len(self.data)):
            faq_topics = self.question_topics[index]
            faq_intents = self.question_intents[index]

            if "admission" not in faq_topics:
                continue
            if "date" not in faq_intents:
                continue
            if "fee" in faq_topics or "hostel" in faq_topics or "scholarship" in faq_topics:
                continue

            faq_question = normalize_text(self.data.iloc[index]["question"])
            if "admission" not in faq_question:
                continue

            semantic_score = float(semantic_scores[index])
            keyword_score = _keyword_score(query_keywords, self.question_keywords[index])
            lexical_score = _lexical_similarity(query_keywords, self.question_keywords[index])
            topic_score = _topic_score(query_topics, faq_topics)
            intent_score = _intent_score(query_intents, faq_intents)
            question_type_score = _type_score(query_type, self.question_types[index])

            routing_score = (
                0.30 * semantic_score
                + 0.20 * intent_score
                + 0.15 * keyword_score
                + 0.10 * lexical_score
                + 0.15 * topic_score
                + 0.10 * question_type_score
            )

            # Date-specific bonus
            if asks_deadline and ("deadline" in faq_question or "last" in faq_question):
                routing_score += 0.30
            elif asks_opening and ("open" in faq_question or "opening" in faq_question):
                routing_score += 0.25

            admission_date_candidates.append({
                "index": int(index),
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "lexical_score": lexical_score,
                "topic_score": topic_score,
                "intent_score": intent_score,
                "question_type_score": question_type_score,
                "routing_score": routing_score,
            })

        if admission_date_candidates:
            admission_date_candidates.sort(
                key=lambda x: (x["routing_score"], x["intent_score"], x["semantic_score"]),
                reverse=True,
            )

            selected = admission_date_candidates[0]
            selected_index = selected["index"]

            margin = max(0.0, selected["routing_score"] - admission_date_candidates[1]["routing_score"]) if len(admission_date_candidates) > 1 else selected["routing_score"]

            confidence_score = min(1.0, max(
                selected["routing_score"],
                selected["intent_score"],
                selected["topic_score"],
            ))

            return self._build_result(
                index=selected_index,
                score=selected["routing_score"],
                semantic_score=selected["semantic_score"],
                keyword_score=selected["keyword_score"],
                lexical_score=selected["lexical_score"],
                topic_score=selected["topic_score"],
                intent_score=selected["intent_score"],
                question_type_score=selected["question_type_score"],
                margin=margin,
                confidence_score=confidence_score,
                confidence_level=_confidence_level(confidence_score),
                source="admission_date_routing",
                question_type=self.question_types[selected_index],
            )

        return None

    def _route_course_registration(
        self,
        query: str,
        normalized_query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
        query_type: str,
        semantic_scores: Any
    ) -> Optional[Dict[str, Any]]:
        """Route course registration problem queries."""
        registration_candidates = []

        for index in range(len(self.data)):
            faq_topics = self.question_topics[index]

            if "registration" not in faq_topics:
                continue

            faq_question = normalize_text(self.data.iloc[index]["question"])
            
            # Must be about course registration specifically
            if "course" not in faq_question or ("register" not in faq_question and "registration" not in faq_question):
                continue

            # Skip complaint FAQs for problem queries
            if "complaint" in faq_topics:
                continue

            semantic_score = float(semantic_scores[index])
            keyword_score = _keyword_score(query_keywords, self.question_keywords[index])
            lexical_score = _lexical_similarity(query_keywords, self.question_keywords[index])
            topic_score = _topic_score(query_topics, faq_topics)
            intent_score = _intent_score(query_intents, self.question_intents[index])
            question_type_score = _type_score(query_type, self.question_types[index])

            routing_score = (
                0.35 * semantic_score
                + 0.20 * intent_score
                + 0.15 * keyword_score
                + 0.10 * lexical_score
                + 0.15 * topic_score
                + 0.05 * question_type_score
            )

            registration_candidates.append({
                "index": int(index),
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "lexical_score": lexical_score,
                "topic_score": topic_score,
                "intent_score": intent_score,
                "question_type_score": question_type_score,
                "routing_score": routing_score,
            })

        if registration_candidates:
            registration_candidates.sort(
                key=lambda x: (x["routing_score"], x["semantic_score"], x["intent_score"]),
                reverse=True,
            )

            selected = registration_candidates[0]
            selected_index = selected["index"]

            margin = max(0.0, selected["routing_score"] - registration_candidates[1]["routing_score"]) if len(registration_candidates) > 1 else selected["routing_score"]

            confidence_score = min(1.0, max(
                selected["semantic_score"],
                selected["routing_score"],
                selected["intent_score"],
            ))

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
                question_type_score=selected["question_type_score"],
                margin=margin,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                source="course_registration_routing",
                question_type=self.question_types[selected_index],
            )

        return None

    def _route_rozgar(
        self,
        query: str,
        normalized_query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
        query_type: str,
        semantic_scores: Any
    ) -> Optional[Dict[str, Any]]:
        """Route e-Rozgaar/freelancing queries."""
        rozgar_candidates = []
        
        is_availability_query = any(term in normalized_query for term in ["available", "offer", "offered", "provide", "list", "types", "courses", "skills", "training"])
        is_eligibility_query = any(term in normalized_query for term in ["eligible", "eligibility", "criteria", "requirements", "qualify", "prerequisite"])

        for index in range(len(self.data)):
            faq_topics = self.question_topics[index]
            faq_question = normalize_text(self.data.iloc[index]["question"])
            
            # Must be about Rozgar or freelancing
            if "rozgar" not in faq_topics and "rozgar" not in faq_question and "freelancing" not in faq_question:
                continue

            semantic_score = float(semantic_scores[index])
            keyword_score = _keyword_score(query_keywords, self.question_keywords[index])
            lexical_score = _lexical_similarity(query_keywords, self.question_keywords[index])
            topic_score = _topic_score(query_topics, faq_topics)
            intent_score = _intent_score(query_intents, self.question_intents[index])
            question_type_score = _type_score(query_type, self.question_types[index])

            routing_score = (
                0.30 * semantic_score
                + 0.25 * intent_score
                + 0.15 * topic_score
                + 0.15 * keyword_score
                + 0.10 * lexical_score
                + 0.05 * question_type_score
            )

            # Availability vs Eligibility distinction
            if is_availability_query:
                if "course" in faq_question and ("available" in faq_question or "offer" in faq_question):
                    routing_score += 0.30
                elif "eligibility" in faq_topics:
                    routing_score -= 0.30
            elif is_eligibility_query:
                if "eligibility" in faq_topics or "eligible" in faq_question:
                    routing_score += 0.30
                elif "course" in faq_question and ("available" in faq_question or "offer" in faq_question):
                    routing_score -= 0.20

            rozgar_candidates.append({
                "index": int(index),
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "lexical_score": lexical_score,
                "topic_score": topic_score,
                "intent_score": intent_score,
                "question_type_score": question_type_score,
                "routing_score": routing_score,
            })

        if rozgar_candidates:
            rozgar_candidates.sort(
                key=lambda x: (x["routing_score"], x["intent_score"], x["topic_score"]),
                reverse=True,
            )

            selected = rozgar_candidates[0]
            selected_index = selected["index"]

            margin = max(0.0, selected["routing_score"] - rozgar_candidates[1]["routing_score"]) if len(rozgar_candidates) > 1 else selected["routing_score"]

            confidence_score = min(1.0, max(
                selected["routing_score"],
                selected["intent_score"],
                selected["topic_score"],
            ))

            # Boost confidence for strong Rozgar matches
            if "rozgar" in self.question_topics[selected_index]:
                confidence_score = min(1.0, confidence_score + 0.10)

            return self._build_result(
                index=selected_index,
                score=selected["routing_score"],
                semantic_score=selected["semantic_score"],
                keyword_score=selected["keyword_score"],
                lexical_score=selected["lexical_score"],
                topic_score=selected["topic_score"],
                intent_score=selected["intent_score"],
                question_type_score=selected["question_type_score"],
                margin=margin,
                confidence_score=confidence_score,
                confidence_level=_confidence_level(confidence_score),
                source="rozgar_routing",
                question_type=self.question_types[selected_index],
            )

        return None

    def _route_hostel(
        self,
        query: str,
        normalized_query: str,
        query_keywords: Set[str],
        query_topics: Set[str],
        query_intents: Set[str],
        query_type: str,
        semantic_scores: Any
    ) -> Optional[Dict[str, Any]]:
        """Route hostel queries (facilities vs complaint)."""
        is_facilities_query = any(term in normalized_query for term in ["facilities", "services", "available", "provide", "amenities", "offered"])
        is_complaint_query = any(term in normalized_query for term in ["complaint", "issue", "problem", "grievance", "concern"])

        hostel_candidates = []

        for index in range(len(self.data)):
            faq_topics = self.question_topics[index]
            faq_question = normalize_text(self.data.iloc[index]["question"])
            
            if "hostel" not in faq_topics and "hostel" not in faq_question:
                continue

            semantic_score = float(semantic_scores[index])
            keyword_score = _keyword_score(query_keywords, self.question_keywords[index])
            lexical_score = _lexical_similarity(query_keywords, self.question_keywords[index])
            topic_score = _topic_score(query_topics, faq_topics)
            intent_score = _intent_score(query_intents, self.question_intents[index])
            question_type_score = _type_score(query_type, self.question_types[index])

            routing_score = (
                0.30 * semantic_score
                + 0.20 * intent_score
                + 0.15 * topic_score
                + 0.15 * keyword_score
                + 0.10 * lexical_score
                + 0.10 * question_type_score
            )

            # Facilities vs Complaint distinction
            if is_facilities_query:
                if "facilities" in faq_topics or "available" in faq_question or "provide" in faq_question:
                    routing_score += 0.25
                elif "complaint" in faq_topics:
                    routing_score -= 0.30
            elif is_complaint_query:
                if "complaint" in faq_topics or "complaint" in faq_question:
                    routing_score += 0.25
                elif "facilities" in faq_topics:
                    routing_score -= 0.20

            hostel_candidates.append({
                "index": int(index),
                "semantic_score": semantic_score,
                "keyword_score": keyword_score,
                "lexical_score": lexical_score,
                "topic_score": topic_score,
                "intent_score": intent_score,
                "question_type_score": question_type_score,
                "routing_score": routing_score,
            })

        if hostel_candidates:
            hostel_candidates.sort(
                key=lambda x: (x["routing_score"], x["intent_score"], x["topic_score"]),
                reverse=True,
            )

            selected = hostel_candidates[0]
            selected_index = selected["index"]

            margin = max(0.0, selected["routing_score"] - hostel_candidates[1]["routing_score"]) if len(hostel_candidates) > 1 else selected["routing_score"]

            confidence_score = min(1.0, max(
                selected["routing_score"],
                selected["intent_score"],
                selected["topic_score"],
            ))

            return self._build_result(
                index=selected_index,
                score=selected["routing_score"],
                semantic_score=selected["semantic_score"],
                keyword_score=selected["keyword_score"],
                lexical_score=selected["lexical_score"],
                topic_score=selected["topic_score"],
                intent_score=selected["intent_score"],
                question_type_score=selected["question_type_score"],
                margin=margin,
                confidence_score=confidence_score,
                confidence_level=_confidence_level(confidence_score),
                source="hostel_routing",
                question_type=self.question_types[selected_index],
            )

        return None

    # ============================================================
    # RESULT BUILDER
    # ============================================================

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

        answer = self.data.iloc[index]["answer"]
        question = self.data.iloc[index]["question"]

        return {
            "answer": answer,
            "question": question,
            "score": round(float(score), 4),
            "semantic_score": round(float(semantic_score), 4),
            "keyword_score": round(float(keyword_score), 4),
            "lexical_score": round(float(lexical_score), 4),
            "topic_score": round(float(topic_score), 4),
            "intent_score": round(float(intent_score), 4),
            "question_type": question_type,
            "question_type_score": round(float(question_type_score), 4),
            "margin": round(float(margin), 4),
            "confidence_score": round(float(confidence_score), 4),
            "confidence_level": confidence_level,
            "source": source,
            "answer_length": len(answer),
            "question_length": len(question),
        }


# ============================================================
# SINGLETON USED BY THE EXISTING APPLICATION
# ============================================================

try:
    faq_retriever = FAQRetriever(
        os.getenv("FAQ_DATA_PATH") or os.getenv("FAQ_FILE") or _find_data_file()
    )
except Exception as e:
    print(f"Warning: FAQ retriever initialization failed: {e}")
    faq_retriever = None


# ============================================================
# SERVICE-STYLE HELPER
# ============================================================

def retrieve_faq(query: str) -> Dict[str, Any]:
    """
    Compatibility helper for code that expects a service-style response.
    """
    if faq_retriever is None:
        return get_fallback_response(query)
    
    try:
        result = faq_retriever.get_answer(query)
    except Exception:
        return get_fallback_response(query)

    if result is None:
        return get_fallback_response(query)

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
# MAIN - TESTING
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("IUB FAQ RETRIEVAL ENGINE v2.0")
    print("=" * 70)
    
    if faq_retriever:
        print(f"FAQ file: {faq_retriever.data_path}")
        print(f"Rows: {len(faq_retriever.data)}")
        print(f"Word vectors: {faq_retriever.word_vectors.shape}")
        print(f"Char vectors: {faq_retriever.char_vectors.shape}")
        print(f"Knowledge articles: {len(faq_retriever.knowledge_articles)}")
    else:
        print("FAQ retriever not initialized.")
        exit(1)
    
    # Test queries covering key scenarios
    test_queries = [
        # Exact match
        "How can I reset my student portal password?",
        
        # Paraphrase
        "I forgot my IUB portal password. How can I recover it?",
        
        # Typo
        "fees?",
        
        # Short query
        "hostel?",
        
        # e-Rozgaar availability vs eligibility
        "I want to learn freelancing at e-Rozgaar. What courses are available?",
        "What is the eligibility for e-Rozgaar?",
        
        # Admission deadline vs procedure
        "What is the last date to apply for admission?",
        "How do I apply for admission?",
        
        # Hostel facilities vs complaint
        "What are the hostel facilities?",
        "How do I report a hostel complaint?",
        
        # Registration deadline vs procedure
        "When is the registration deadline?",
        "How do I register for courses?",
        
        # LMS vs portal password
        "I can't log in to my IUB-LMS account. What should I do?",
        "I forgot my student portal password.",
        
        # Engineering fee
        "What is the fee for BS Engineering?",
        
        # Person query
        "Who is the Dean of the Faculty of Computing?",
        
        # Article title query (Knowledge Base)
        "What is the Enabling Center?",
        
        # Completely unrelated
        "What is the weather today?",
    ]
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    
    for query in test_queries:
        print(f"\nQ: {query}")
        print("-" * 50)
        
        result = retrieve_faq(query)
        
        if result["found"]:
            print(f"Found: YES")
            print(f"Question: {result['question']}")
            print(f"Answer: {result['answer'][:150]}...")
            print(f"Confidence: {result['confidence_level']} ({result['confidence_score']:.3f})")
            print(f"Intent Score: {result['intent_score']:.3f}")
            print(f"Topic Score: {result['topic_score']:.3f}")
            print(f"Source: {result['source']}")
        else:
            print("Found: NO")
            print(f"Answer: {result['answer'][:150]}...")
            print(f"Confidence: {result['confidence_level']} ({result['confidence_score']:.3f})")
            print(f"Source: {result['source']}")