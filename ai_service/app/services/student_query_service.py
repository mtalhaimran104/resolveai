from app.services.faq_service import (
    find_faq_answer
)

from app.services.iub_knowledge_service import (
    search_iub_programs
)


# ============================================================
# MODEL INFORMATION
# ============================================================

MODEL_NAME = "resolveai-student-query"
MODEL_VERSION = "v1"


# ============================================================
# CONTACT INFORMATION
# ============================================================

IUB_CONTACT = (
    "\n\n"
    "**IUB Information Center/Helpline:** "
    "**0346-9255555, 0347-9255555, 062-9255580**\n"
    "**Email:** **iubhelpline@iub.edu.pk**\n"
    "**Official Website:** **https://www.iub.edu.pk/**"
)


# ============================================================
# PROGRAM-SPECIFIC QUERY DETECTION
# ============================================================

def is_program_specific_query(query: str) -> bool:
    """
    Detect questions that explicitly target a degree/program.

    IMPORTANT: This must NOT trigger on queries that are better
    answered by FAQ, such as "fee for BS Engineering" or
    "eligibility for BS Computer Science".

    Examples of TRUE program-specific queries:
        - "What is the curriculum for BS Computer Science?"
        - "Tell me about the MS Data Science program"
        - "What courses are in the BS Engineering program?"

    Examples of FALSE program-specific queries (FAQ should handle):
        - "What is the fee for BS Engineering?"
        - "What is the eligibility for BS Computer Science?"
        - "How can I apply for admission in MS?"
    """

    if query is None:
        return False

    query = str(query).strip().lower()

    # ========================================================
    # Strong program-specific signals
    # ========================================================

    strong_signals = [
        "curriculum",
        "syllabus",
        "course outline",
        "program structure",
        "degree structure",
        "credit hours",
        "duration",
        "program details",
        "program overview",
    ]

    if any(
        signal in query
        for signal in strong_signals
    ):
        return True

    # ========================================================
    # Check for program mention BUT with context
    # ========================================================

    program_signal = any(
        signal in query
        for signal in [" bs ", " ms ", " mphil ", " m.phil ", " phd ", " ph.d "]
    )

    # Generic program terms that don't strongly imply a program-specific query
    generic_terms = [
        "fee",
        "fees",
        "eligibility",
        "admission",
        "apply",
        "application",
        "requirements",
        "last date",
        "deadline",
        "cost",
        "charges",
        "tuition",
        "scholarship",
    ]

    # If query has a generic term, it's likely an FAQ question
    has_generic_term = any(
        term in query
        for term in generic_terms
    )

    if program_signal and not has_generic_term:
        return True

    # ========================================================
    # Quick check for "tell me about" patterns
    # ========================================================

    if any(
        phrase in query
        for phrase in ["tell me about", "what is", "what are", "information about"]
    ):
        # Check if it's asking about a specific program
        program_terms = [
            "computer science",
            "software engineering",
            "electrical engineering",
            "data science",
            "artificial intelligence",
            "telecommunication",
            "biomedical",
        ]
        if any(term in query for term in program_terms):
            # But not if it's a generic question
            if not has_generic_term:
                return True

    return False


# ============================================================
# CATEGORY KEYWORDS
# ============================================================

PROGRAM_KEYWORDS = [
    "program",
    "programs",
    "programme",
    "programmes",
    "degree",
    "degrees",
    "course",
    "courses",
    "study",
    "studies",
    "offer",
    "offers",
    "engineering",
    "software engineering",
    "computer science",
    "electrical engineering",
    "electronic engineering",
    "telecommunication",
    "biomedical",
    "artificial intelligence",
    "data science",
    "cyber security",
    "robotics",
    "mphil",
    "ms",
    "phd",
    "bs",
    # e-Rozgaar / freelancing additions
    "e-rozgaar",
    "erozgaar",
    "rozgar",
    "freelancing",
    "freelance",
    "freelancer",
]


ADMISSION_KEYWORDS = [
    "admission",
    "admissions",
    "apply",
    "application",
    "applications",
    "eligibility",
    "eligible",
    "merit",
    "deadline",
    "last date",
    "entry test",
    "prospectus",
    "requirements",
    "qualify",
    "qualification",
]


SCHOLARSHIP_KEYWORDS = [
    "scholarship",
    "scholarships",
    "financial aid",
    "financial assistance",
    "honhaar",
    "stipend",
]


FEE_KEYWORDS = [
    "fee",
    "fees",
    "tuition",
    "finance",
    "financial",
    "challan",
    "payment",
    "payments",
    "installment",
    "installments",
    "dues",
    "refund",
    "accounts",
    "cost",
    "costs",
    "charges",
]


PORTAL_KEYWORDS = [
    "portal",
    "student portal",
    "e portal",
    "eportal",
    "login",
    "password",
    "registration",
    "enrollment",
    "website",
    "system",
    "crash",
    "down",
    "not working",
    "error",
    "upload",
    "lms",
    "moodle",
    "canvas",
    "blackboard",
]


LOCATION_KEYWORDS = [
    "location",
    "where",
    "address",
    "office",
    "campus",
    "building",
    "department",
    "vc office",
    "vice chancellor",
    "information center",
    "helpline",
    "library",
    "hostel",
    "transport",
    "bus",
    "shuttle",
]


UNIFORM_KEYWORDS = [
    "uniform",
    "dress",
    "dress code",
    "color",
    "colour",
]


# ============================================================
# CATEGORY DETECTION
# ============================================================

def detect_category(query: str) -> str:
    """
    Detect the primary category of a query.

    IMPORTANT: This should ONLY be used as a fallback when
    FAQ retrieval fails. The FAQ retriever should always be
    consulted first for any query that might be in the FAQ dataset.
    """

    query = query.lower().strip()

    # ========================================================
    # e-Rozgaar / Freelancing detection (HIGH priority)
    # ========================================================

    if any(
        term in query
        for term in ["e-rozgaar", "erozgaar", "rozgar", "freelancing", "freelance"]
    ):
        # If it's about courses/skills/training, it's a program query
        if any(
            term in query
            for term in ["course", "courses", "skill", "skills", "training", "learn"]
        ):
            return "program"
        return "program"

    # ========================================================
    # Specific categories
    # ========================================================

    # Admission and eligibility questions
    if any(
        word in query
        for word in ADMISSION_KEYWORDS
    ):
        return "admission"

    # Scholarship questions
    if any(
        word in query
        for word in SCHOLARSHIP_KEYWORDS
    ):
        return "scholarship"

    # Fee/finance questions
    if any(
        word in query
        for word in FEE_KEYWORDS
    ):
        return "finance"

    # Portal/LMS questions
    if any(
        word in query
        for word in PORTAL_KEYWORDS
    ):
        return "portal"

    # Location questions - but be careful about "complaint" vs "facilities"
    if any(
        word in query
        for word in LOCATION_KEYWORDS
    ):
        # If "complaint" is mentioned, it's NOT a location question
        if "complaint" in query:
            return "general"
        # If "facilities" is mentioned with "hostel", it's likely a facilities question
        if "hostel" in query and "facilities" in query:
            return "general"  # Let FAQ handle it
        return "location"

    # Uniform questions
    if any(
        word in query
        for word in UNIFORM_KEYWORDS
    ):
        return "uniform"

    # Program questions
    if any(
        word in query
        for word in PROGRAM_KEYWORDS
    ):
        return "program"

    return "general"


# ============================================================
# CATEGORY FALLBACKS
# ============================================================

def fallback_answer(category: str) -> str:

    if category == "admission":

        return (
            "I could not find a sufficiently verified current "
            "admission answer in the available IUB knowledge base.\n\n"
            "For verified information about eligibility, "
            "application procedure, merit, deadlines and entry "
            "tests, please contact the **IUB Information "
            "Center/Helpline**."
            + IUB_CONTACT
        )

    if category == "scholarship":

        return (
            "I could not find a sufficiently verified current "
            "list of IUB scholarships.\n\n"
            "Scholarship availability, eligibility, deadlines "
            "and required documents can change by scheme and "
            "academic year. Please verify the current information "
            "through official IUB channels.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline**."
            + IUB_CONTACT
        )

    if category == "finance":

        return (
            "I could not find a sufficiently verified current "
            "fee or financial answer for this question.\n\n"
            "I do not want to guess a fee amount, challan "
            "procedure, refund procedure or Finance/Accounts "
            "Office information that may be outdated.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline**."
            + IUB_CONTACT
        )

    if category == "portal":

        return (
            "For an **IUB Student Portal/E-Portal** problem, "
            "first check your internet connection, refresh the "
            "page, try another browser and clear the browser "
            "cache.\n\n"
            "If the problem continues, please contact the "
            "**IUB Directorate of Information Technology** "
            "for official assistance."
            + IUB_CONTACT
        )

    if category == "location":

        return (
            "I could not find a sufficiently verified current "
            "location for this IUB facility or office.\n\n"
            "I do not want to guess an office, department, "
            "library or campus location that may be outdated.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline**."
            + IUB_CONTACT
        )

    if category == "uniform":

        return (
            "I could not find a sufficiently verified current "
            "answer about the IUB uniform or dress-code "
            "requirements.\n\n"
            "I do not want to guess the required uniform color "
            "or dress code.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline**."
            + IUB_CONTACT
        )

    return (
        "I am the **IUB AI Help Desk**. I can assist with "
        "**IUB programs, admissions, fees, scholarships, "
        "examinations, student portal, registration, hostels, "
        "library, transport, departments, offices and other "
        "university services**.\n\n"
        "I could not find a sufficiently verified answer "
        "for this particular question."
    )


# ============================================================
# SAFE RESULT NORMALIZATION
# ============================================================

def _normalize_program_result(result: dict) -> dict:

    similarity_score = result.get(
        "similarity_score",
        result.get("score", 0.0),
    )

    confidence_score = result.get(
        "confidence_score",
        0.0,
    )

    confidence_level = result.get(
        "confidence_level",
        "Low",
    )

    return {
        "answer": result.get(
            "answer",
            "",
        ),

        "similarity_score": round(
            float(similarity_score),
            4,
        ),

        "confidence_level": confidence_level,

        "confidence_score": round(
            float(confidence_score),
            4,
        ),

        "model_name": result.get(
            "model_name",
            "resolveai-iub-knowledge",
        ),

        "model_version": result.get(
            "model_version",
            "v1",
        ),
    }


# ============================================================
# MAIN STUDENT QUERY FUNCTION
# ============================================================

def answer_student_query(query: str) -> dict:

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if query is None:
        query = ""

    if not isinstance(query, str):
        query = str(query)

    query = query.strip()

    # --------------------------------------------------------
    # Empty question
    # --------------------------------------------------------

    if not query:
        return {
            "answer": (
                "Please enter a valid question."
                + IUB_CONTACT
            ),
            "similarity_score": 0.0,
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
        }

    # ========================================================
    # Step 1: ALWAYS try FAQ first
    # ========================================================
    #
    # The FAQ dataset has 3751 rows and covers a wide range
    # of topics. We should give it a fair chance for EVERY
    # query before falling back to other services.
    # ========================================================

    faq_result = find_faq_answer(query)

    # ========================================================
    # Step 2: Evaluate FAQ result - only accept if confident
    # ========================================================

    faq_found = faq_result.get("found", False)

    if faq_found:
        faq_confidence = float(
            faq_result.get("confidence_score", 0.0)
        )

        faq_similarity = float(
            faq_result.get("similarity_score", 0.0)
        )

        faq_level = faq_result.get(
            "confidence_level",
            "Low",
        )

        # ====================================================
        # IMPROVEMENT: Stricter FAQ acceptance criteria
        # ====================================================
        #
        # Accept FAQ only when retrieval is reliable.
        #
        # High confidence:
        # Always accept.
        #
        # Medium confidence:
        # Accept only when semantic similarity is reasonable.
        #
        # Low confidence:
        # Do NOT blindly return it.
        #
        # Also, check for intent-topic mismatch:
        # If the query and FAQ have conflicting intent/topic
        # combinations (like "facilities" vs "complaint"),
        # require higher thresholds.
        # ====================================================

        # Check for potential intent-topic mismatches
        query_text = query.lower()
        faq_question = faq_result.get("question", "").lower()

        # Hostel Facilities vs Complaint
        hostel_facilities_mismatch = (
            "hostel" in query_text and "facilities" in query_text
            and "complaint" in faq_question
        )

        # Registration Deadline vs Procedure
        deadline_procedure_mismatch = (
            "registration" in query_text and ("deadline" in query_text or "date" in query_text)
            and "procedure" in faq_question
        )

        # Scholarship generic vs specific
        scholarship_weak_match = (
            "scholarship" in query_text and "available" in query_text
            and "list" not in faq_question and "available" not in faq_question
        )

        # If there's a mismatch, require higher thresholds
        has_mismatch = (
            hostel_facilities_mismatch
            or deadline_procedure_mismatch
            or scholarship_weak_match
        )

        if has_mismatch:
            # Stricter thresholds for mismatched cases
            strong_faq_match = (
                faq_level == "High"
                and faq_confidence >= 0.75
                and faq_similarity >= 0.40
            )
        else:
            # Normal thresholds
            strong_faq_match = (
                faq_level == "High"
                or (
                    faq_level == "Medium"
                    and faq_confidence >= 0.65
                    and faq_similarity >= 0.30
                )
                or (
                    faq_confidence >= 0.80
                    and faq_similarity >= 0.55
                )
            )

        if strong_faq_match:
            return {
                "answer": faq_result.get(
                    "answer",
                    "",
                ),

                "similarity_score": round(
                    faq_similarity,
                    4,
                ),

                "confidence_level": faq_level,

                "confidence_score": round(
                    faq_confidence,
                    4,
                ),

                "model_name": faq_result.get(
                    "model_name",
                    "resolveai-faq-retriever",
                ),

                "model_version": faq_result.get(
                    "model_version",
                    "v1",
                ),
            }

    # ========================================================
    # Step 3: Category detection (for fallback)
    # ========================================================

    category = detect_category(query)

    # ========================================================
    # Step 4: Program-specific questions
    # ========================================================
    #
    # Only use program search if:
    # 1. The query is program-specific AND
    # 2. FAQ didn't have a confident answer
    # ========================================================

    if is_program_specific_query(query) or category == "program":
        try:
            result = search_iub_programs(query)
            if result:
                normalized = _normalize_program_result(result)
                # Only use if it's better than the FAQ result
                faq_similarity = faq_result.get("similarity_score", 0.0)
                if normalized.get("similarity_score", 0.0) > faq_similarity:
                    return normalized
        except Exception as exc:
            print(f"[STUDENT QUERY] Program search error: {exc}")

    # ========================================================
    # Step 5: Category fallback
    # ========================================================

    # Only use category fallback if FAQ had no result or very low confidence
    faq_score = faq_result.get("similarity_score", 0.0)
    if faq_score < 0.30:
        return {
            "answer": fallback_answer(category),
            "similarity_score": round(float(faq_score), 4),
            "confidence_level": faq_result.get("confidence_level", "Low"),
            "confidence_score": round(float(faq_result.get("confidence_score", 0.0)), 4),
            "model_name": faq_result.get("model_name", "resolveai-faq-retriever"),
            "model_version": faq_result.get("model_version", "v1"),
        }

    # ========================================================
    # Step 6: Return the best we have (FAQ result, even if low)
    # ========================================================

    return {
        "answer": faq_result.get(
            "answer",
            fallback_answer(category),
        ),

        "similarity_score": round(
            float(
                faq_result.get(
                    "similarity_score",
                    0.0,
                )
            ),
            4,
        ),

        "confidence_level": faq_result.get(
            "confidence_level",
            "Low",
        ),

        "confidence_score": round(
            float(
                faq_result.get(
                    "confidence_score",
                    0.0,
                )
            ),
            4,
        ),

        "model_name": faq_result.get(
            "model_name",
            "resolveai-faq-retriever",
        ),

        "model_version": faq_result.get(
            "model_version",
            "v1",
        ),
    }