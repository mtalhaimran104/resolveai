"""
ResolveAI - Student Query Service
=================================

Orchestrates FAQ retrieval, Knowledge Base retrieval, and program search
to provide accurate answers to IUB student/faculty questions.

Key improvements:
- Stricter FAQ result acceptance with configurable thresholds
- Source-aware routing that respects FAQ retriever's confidence
- Improved program-specific query detection
- Better category fallback with domain-specific responses
- Safe handling of all error cases
- No low-confidence FAQ results leaked
- No hallucination of university facts

Version: 2.0
Last Updated: 2026-09-04
"""

from typing import Any, Dict, List, Optional, Tuple

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
MODEL_VERSION = "v2"


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

IUB_IT_CONTACT = (
    "\n\n"
    "**IUB IT Help Desk:** "
    "**062-9255858, 062-9255062**\n"
    "**IUB Helpline:** "
    "**0346-9255555, 0347-9255555, 062-9255580**\n"
    "**Email:** **iubhelpline@iub.edu.pk**"
)


# ============================================================
# CONFIGURATION - ACCEPTANCE THRESHOLDS
# ============================================================

# FAQ acceptance thresholds - strict to prevent low-confidence answers
FAQ_ACCEPT_HIGH_CONFIDENCE = 0.78
FAQ_ACCEPT_MEDIUM_CONFIDENCE = 0.65
FAQ_ACCEPT_MIN_SIMILARITY_HIGH = 0.35
FAQ_ACCEPT_MIN_SIMILARITY_MEDIUM = 0.28

# Domain-specific stricter thresholds for known confusion cases
FAQ_STRICT_THRESHOLDS = {
    "hostel_facilities_vs_complaint": {
        "min_confidence": 0.75,
        "min_similarity": 0.40
    },
    "registration_deadline_vs_procedure": {
        "min_confidence": 0.75,
        "min_similarity": 0.40
    },
    "scholarship_vs_fee": {
        "min_confidence": 0.72,
        "min_similarity": 0.38
    },
    "fee_vs_program": {
        "min_confidence": 0.72,
        "min_similarity": 0.38
    },
}

# Program acceptance thresholds
PROGRAM_ACCEPT_MIN_CONFIDENCE = 0.55
PROGRAM_ACCEPT_MIN_SIMILARITY = 0.50


# ============================================================
# PROGRAM-SPECIFIC QUERY DETECTION - IMPROVED
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
        - "What is the structure of the BS Software Engineering program?"

    Examples of FALSE program-specific queries (FAQ should handle):
        - "What is the fee for BS Engineering?"
        - "What is the eligibility for BS Computer Science?"
        - "How can I apply for admission in MS?"
        - "What is the duration of the program?" (FAQ likely has this)
    """

    if query is None:
        return False

    query = str(query).strip().lower()

    # ========================================================
    # Strong program-specific signals - ENHANCED
    # ========================================================

    strong_signals = [
        "curriculum",
        "syllabus",
        "course outline",
        "program structure",
        "degree structure",
        "credit hours",
        "credit hour",
        "program details",
        "program overview",
        "program content",
        "subjects offered",
        "degree requirements",
        "program length",
        "semester system",
        "credit system",
        "course list",
        "list of courses",
        "course offerings",
        "core courses",
        "elective courses",
        "program outline",
        "study plan",
        "academic plan",
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
        for signal in [
            " bs ", " ms ", " mphil ", " m.phil ",
            " phd ", " ph.d ", " b.s ", " m.s ",
            " bachelor", " master", " doctoral",
            " bs in", " ms in", " mphil in", " phd in",
            " bachelor of", " master of",
        ]
    )

    # Generic terms that signal FAQ question, NOT program-specific
    generic_terms = [
        "fee", "fees", "tuition", "cost", "costs", "charges",
        "eligibility", "admission", "apply", "application",
        "requirements", "last date", "deadline", "closing",
        "scholarship", "financial aid", "stipend",
        "result", "exam", "examination", "grade",
        "password", "reset", "login", "portal", "lms",
        "hostel", "facilities", "complaint", "grievance",
        "transport", "bus", "shuttle", "library", "book",
    ]

    # If query has a generic term, it's likely an FAQ question
    has_generic_term = any(
        term in query
        for term in generic_terms
    )

    if program_signal and not has_generic_term:
        return True

    # ========================================================
    # Check for "tell me about" patterns WITH program term
    # ========================================================

    program_names = [
        "computer science",
        "software engineering",
        "electrical engineering",
        "electronic engineering",
        "data science",
        "artificial intelligence",
        "telecommunication",
        "biomedical",
        "cyber security",
        "robotics",
        "mechanical engineering",
        "civil engineering",
        "information technology",
        "information security",
        "networks and telecommunications",
        "internet of things",
        "aviation sciences",
        "aircraft maintenance",
        "quantum computing",
        "biochemistry",
        "biotechnology",
        "botany",
        "zoology",
        "chemistry",
        "physics",
        "mathematics",
        "statistics",
        "economics",
        "commerce",
        "business administration",
        "public administration",
        "psychology",
        "sociology",
        "political science",
        "international relations",
        "english literature",
        "urdu",
        "history",
        "archaeology",
        "pharmacy",
        "nursing",
        "physiotherapy",
        "public health",
        "forensic science",
    ]

    # If query mentions a specific program name without generic terms
    for program in program_names:
        if program in query:
            # Check if it's about curriculum/structure (program-specific)
            if any(
                signal in query
                for signal in ["curriculum", "syllabus", "structure", "courses", "subjects", "outline"]
            ):
                return True
            # Otherwise, it might be a FAQ (fee, eligibility, etc.)
            if not has_generic_term:
                # If it's asking about the program itself without generic terms
                return True

    # ========================================================
    # e-Rozgaar / Freelancing detection - IMPROVED
    # ========================================================
    
    if any(
        term in query
        for term in ["e-rozgaar", "erozgaar", "rozgar", "freelancing", "freelance"]
    ):
        # If asking about courses/skills/training in detail (program-specific)
        if any(
            term in query
            for term in ["course", "courses", "skill", "skills", "training", "learn", "program", "curriculum", "outline", "structure"]
        ):
            # BUT if asking about fee, eligibility, admission - FAQ should handle
            if not any(
                term in query
                for term in ["fee", "fees", "eligibility", "admission", "apply", "cost", "duration"]
            ):
                return True

    return False


# ============================================================
# CATEGORY KEYWORDS - ENHANCED
# ============================================================

PROGRAM_KEYWORDS = [
    "program", "programs", "programme", "programmes",
    "degree", "degrees", "course", "courses",
    "study", "studies", "offer", "offers",
    "engineering", "software engineering", "computer science",
    "electrical engineering", "electronic engineering",
    "telecommunication", "biomedical", "artificial intelligence",
    "data science", "cyber security", "robotics",
    "mphil", "ms", "phd", "bs", "b.s", "m.s",
    "bachelor", "master", "doctoral",
]

ADMISSION_KEYWORDS = [
    "admission", "admissions", "apply", "application",
    "applications", "eligibility", "eligible",
    "merit", "deadline", "last date", "entry test",
    "prospectus", "requirements", "qualify", "qualification",
    "admission process", "admission criteria",
]

SCHOLARSHIP_KEYWORDS = [
    "scholarship", "scholarships", "financial aid",
    "financial assistance", "honhaar", "stipend",
    "need based", "merit scholarship",
]

FEE_KEYWORDS = [
    "fee", "fees", "tuition", "finance", "financial",
    "challan", "payment", "payments", "installment",
    "installments", "dues", "refund", "accounts",
    "cost", "costs", "charges", "fee structure",
    "fee schedule", "semester fee",
]

PORTAL_KEYWORDS = [
    "portal", "student portal", "e portal", "eportal",
    "login", "password", "registration", "enrollment",
    "website", "system", "crash", "down", "not working",
    "error", "upload", "lms", "moodle", "canvas",
    "blackboard", "account", "dashboard", "myiub",
]

LOCATION_KEYWORDS = [
    "location", "where", "address", "office", "campus",
    "building", "department", "vc office", "vice chancellor",
    "information center", "helpline", "library", "hostel",
    "transport", "bus", "shuttle", "baghdad campus",
    "khawaja fareed campus", "abasisa campus", "ryk",
    "bahawalnagar", "liaquatpur", "ahmadpur",
]

EXAM_KEYWORDS = [
    "exam", "examination", "test", "quiz", "midterm",
    "final", "result", "grade", "gpa", "cgpa",
    "assessment", "recheck", "re-evaluation", "transcript",
]

HOSTEL_KEYWORDS = [
    "hostel", "accommodation", "room", "dormitory",
    "residence", "boarding", "hostel facilities",
    "hostel complaint", "hostel issue", "warden",
]

UNIFORM_KEYWORDS = [
    "uniform", "dress", "dress code", "color", "colour",
    "attire", "clothing",
]

ROZGAR_KEYWORDS = [
    "e-rozgaar", "erozgaar", "rozgar", "freelancing",
    "freelance", "freelancer", "rozgar center",
]


# ============================================================
# CATEGORY DETECTION - ENHANCED
# ============================================================

def detect_category(query: str) -> str:
    """
    Detect the primary category of a query.

    IMPORTANT: This should ONLY be used as a fallback when
    FAQ retrieval fails. The FAQ retriever should always be
    consulted first for any query that might be in the FAQ dataset.
    """
    query = query.lower().strip()

    # Check for hostel-related queries first (to distinguish facilities vs complaint)
    if "hostel" in query:
        # If it's about complaint/issue/problem
        if any(
            term in query
            for term in ["complaint", "issue", "problem", "grievance", "concern", "report", "harassment"]
        ):
            return "hostel_complaint"
        # If it's about facilities/services/available
        elif any(
            term in query
            for term in ["facilities", "services", "available", "provide", "offered", "amenities", "features"]
        ):
            return "hostel_facilities"
        # Generic hostel question
        return "hostel"

    # e-Rozgaar / Freelancing detection
    if any(
        term in query
        for term in ROZGAR_KEYWORDS
    ):
        # Check for specific sub-intents
        if "eligibility" in query or "eligible" in query or "criteria" in query:
            return "rozgar_eligibility"
        elif "course" in query or "skill" in query or "training" in query or "learn" in query:
            if "available" in query or "offer" in query or "list" in query:
                return "rozgar_courses"
            return "rozgar"
        elif "fee" in query or "cost" in query:
            return "rozgar_fee"
        else:
            return "rozgar"

    # Admission and eligibility questions
    if any(
        word in query
        for word in ADMISSION_KEYWORDS
    ):
        if "deadline" in query or "last date" in query or "closing" in query:
            return "admission_deadline"
        elif "procedure" in query or "process" in query or "steps" in query or "how" in query:
            return "admission_procedure"
        elif "eligibility" in query or "eligible" in query or "criteria" in query:
            return "admission_eligibility"
        else:
            return "admission"

    # Scholarship questions
    if any(
        word in query
        for word in SCHOLARSHIP_KEYWORDS
    ):
        if "available" in query or "list" in query:
            return "scholarship_availability"
        elif "eligible" in query or "eligibility" in query:
            return "scholarship_eligibility"
        else:
            return "scholarship"

    # Fee/finance questions
    if any(
        word in query
        for word in FEE_KEYWORDS
    ):
        if "engineering" in query:
            return "fee_engineering"
        else:
            return "finance"

    # Portal/LMS questions
    if any(
        word in query
        for word in PORTAL_KEYWORDS
    ):
        if "password" in query or "reset" in query or "forgot" in query:
            return "portal_password"
        elif "lms" in query:
            return "lms"
        else:
            return "portal"

    # Exam/result questions
    if any(
        word in query
        for word in EXAM_KEYWORDS
    ):
        return "examination"

    # Location questions
    if any(
        word in query
        for word in LOCATION_KEYWORDS
    ):
        return "location"

    # Uniform questions
    if any(
        word in query
        for word in UNIFORM_KEYWORDS
    ):
        return "uniform"

    # Program questions (only if no other category matched)
    if any(
        word in query
        for word in PROGRAM_KEYWORDS
    ):
        return "program"

    return "general"


# ============================================================
# CATEGORY FALLBACKS - ENHANCED WITH DETAILED MESSAGES
# ============================================================

def fallback_answer(category: str) -> str:
    """Return category-specific fallback responses."""

    if category == "admission" or category == "admission_deadline":
        return (
            "I could not find a sufficiently verified current "
            "admission answer in the available IUB knowledge base.\n\n"
            "For verified information about eligibility, "
            "application procedure, merit, deadlines and entry "
            "tests, please contact the **IUB Admission Cell** or "
            "the **IUB Information Center**."
            + IUB_CONTACT
        )

    if category == "admission_procedure":
        return (
            "I could not find a sufficiently verified current "
            "admission procedure in the available IUB knowledge base.\n\n"
            "For verified information about the application process, "
            "required documents, and submission steps, please contact "
            "the **IUB Admission Cell** or the **IUB Information Center**."
            + IUB_CONTACT
        )

    if category == "admission_eligibility":
        return (
            "I could not find a sufficiently verified current "
            "eligibility criteria in the available IUB knowledge base.\n\n"
            "Eligibility requirements vary by program and are updated "
            "annually. For verified and program-specific eligibility "
            "criteria, please contact the **IUB Admission Cell** or "
            "the **IUB Information Center**."
            + IUB_CONTACT
        )

    if category == "scholarship" or category == "scholarship_availability":
        return (
            "I could not find a sufficiently verified current "
            "list of IUB scholarships in the available knowledge base.\n\n"
            "Scholarship availability, eligibility, deadlines "
            "and required documents can change by scheme and "
            "academic year. Please verify the current information "
            "through official IUB channels.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline** or the "
            "**Directorate of Financial Assistance**."
            + IUB_CONTACT
        )

    if category == "scholarship_eligibility":
        return (
            "I could not find a sufficiently verified current "
            "scholarship eligibility criteria in the available knowledge base.\n\n"
            "Scholarship eligibility varies by program and scheme. "
            "Please verify the current criteria with the "
            "**Directorate of Financial Assistance**.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline**."
            + IUB_CONTACT
        )

    if category == "finance" or category == "fee_engineering":
        return (
            "I could not find a sufficiently verified current "
            "fee or financial answer for this question.\n\n"
            "I do not want to guess a fee amount, challan "
            "procedure, refund procedure or Finance/Accounts "
            "Office information that may be outdated.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline** or the "
            "**Treasurer's Office**."
            + IUB_CONTACT
        )

    if category == "portal" or category == "portal_password":
        return (
            "For an **IUB Student Portal/E-Portal** problem, "
            "first check your internet connection, refresh the "
            "page, try another browser and clear the browser "
            "cache.\n\n"
            "If you have forgotten your password, use the "
            "'Forgot Password' option on the login page.\n\n"
            "If the problem continues, please contact the "
            "**IUB Directorate of Information Technology** "
            "for official assistance."
            + IUB_IT_CONTACT
        )

    if category == "lms":
        return (
            "For an **IUB-LMS** problem:\n\n"
            "1. Verify your student ID and password are correct\n"
            "2. Try refreshing the page or using a different browser\n"
            "3. Check that your internet connection is stable\n"
            "4. Clear your browser cache and cookies\n\n"
            "If you have forgotten your LMS password, reset it "
            "through the student portal as the LMS uses the same credentials.\n\n"
            "If the problem continues, please contact the "
            "**IUB IT Help Desk**."
            + IUB_IT_CONTACT
        )

    if category == "location":
        return (
            "I could not find a sufficiently verified current "
            "location for this IUB facility or office in the "
            "available knowledge base.\n\n"
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
            "or dress code. These policies may vary by program "
            "and campus.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline** or your "
            "**department office**."
            + IUB_CONTACT
        )

    if category == "examination":
        return (
            "I could not find a sufficiently verified current "
            "answer about IUB examinations, results or grading.\n\n"
            "Examination schedules, result announcements, and "
            "grading policies are updated regularly by the "
            "**Controller of Examinations** office.\n\n"
            "For verified assistance, please contact the "
            "**IUB Information Center/Helpline** or the "
            "**Examination Division** directly."
            + IUB_CONTACT
        )

    if category == "hostel" or category == "hostel_facilities":
        return (
            "I could not find a sufficiently verified current "
            "answer about IUB hostel facilities in the available "
            "knowledge base.\n\n"
            "Hostel facilities including Wi-Fi, security, dining, "
            "and recreation vary by hostel and campus.\n\n"
            "For verified information about hostel facilities, "
            "availability, and amenities, please contact the "
            "**Directorate of Students Affairs** or your "
            "**hostel warden**."
            + IUB_CONTACT
        )

    if category == "hostel_complaint":
        return (
            "I could not find a sufficiently verified current "
            "answer about hostel complaint procedures.\n\n"
            "If you need to report a hostel issue, please:\n"
            "• Contact your hostel warden directly\n"
            "• Visit the Directorate of Students Affairs office\n"
            "• Use the GCRC complaint portal on MyIUB\n\n"
            "For verified assistance, please contact the "
            "**Directorate of Students Affairs**."
            + IUB_CONTACT
        )

    if category == "rozgar" or category == "rozgar_courses":
        return (
            "I could not find a sufficiently verified current "
            "answer about e-Rozgaar courses in the available "
            "knowledge base.\n\n"
            "For verified information about e-Rozgaar courses, "
            "skills, and training programs, please contact the "
            "**e-Rozgaar Center** at the Baghdad-ul-Jadeed Campus "
            "or the **IUB Information Center**."
            + IUB_CONTACT
        )

    if category == "rozgar_eligibility":
        return (
            "I could not find a sufficiently verified current "
            "answer about e-Rozgaar eligibility in the available "
            "knowledge base.\n\n"
            "Eligibility for e-Rozgaar programs may vary by "
            "course. For verified information, please contact "
            "the **e-Rozgaar Center** at the Baghdad-ul-Jadeed Campus "
            "or the **IUB Information Center**."
            + IUB_CONTACT
        )

    if category == "rozgar_fee":
        return (
            "I could not find a sufficiently verified current "
            "answer about e-Rozgaar fees in the available "
            "knowledge base.\n\n"
            "For verified fee information for e-Rozgaar courses, "
            "please contact the **e-Rozgaar Center** or the "
            "**IUB Information Center**."
            + IUB_CONTACT
        )

    if category == "program":
        return (
            "I could not find sufficient information about this "
            "specific program in the available knowledge base.\n\n"
            "For detailed information about program curriculum, "
            "structure, and requirements, please visit the "
            "**official IUB website** or contact the **relevant "
            "department office**."
            + IUB_CONTACT
        )

    # Enhanced general fallback with professional context
    return (
        "I am the **IUB AI Help Desk**, your virtual assistant for "
        "**The Islamia University of Bahawalpur**.\n\n"
        "I can assist with:\n"
        "• **Academic Programs** (BS, MS, MPhil, PhD)\n"
        "• **Admissions & Eligibility**\n"
        "• **Fee Structure & Scholarships**\n"
        "• **Student Portal & LMS**\n"
        "• **Examinations & Results**\n"
        "• **Hostels, Library & Transport**\n"
        "• **University Departments & Offices**\n\n"
        "I could not find a sufficiently verified answer "
        "for your specific question at this moment.\n\n"
        "For personalized assistance, please contact the "
        "**IUB Information Center/Helpline**."
        + IUB_CONTACT
    )


# ============================================================
# HELPER: SAFE FAQ RESULT
# ============================================================

def _safe_faq_result(query: str, error_msg: str = "") -> dict:
    """Return a safe empty FAQ result."""
    return {
        "found": False,
        "answer": "",
        "question": query,
        "similarity_score": 0.0,
        "confidence_score": 0.0,
        "confidence_level": "Low",
        "source": "faq_error",
        "model_name": "resolveai-faq-retriever",
        "model_version": "v1",
        "_error": error_msg,
    }


# ============================================================
# HELPER: CHECK FOR INTENT MISMATCH
# ============================================================

def _has_intent_mismatch(query: str, faq_question: str) -> bool:
    """
    Check for common intent-topic mismatches that should trigger
    stricter acceptance thresholds.
    """
    query = query.lower()
    faq = faq_question.lower()

    # Hostel Facilities vs Complaint
    if "hostel" in query:
        if "facilities" in query and ("complaint" in faq or "grievance" in faq):
            return True
        if "complaint" in query and ("facilities" in faq or "services" in faq):
            return True
        if "facilities" not in query and "complaint" not in query:
            # Generic hostel query - check if FAQ is specific
            if ("facilities" in faq or "services" in faq) and "complaint" not in faq:
                return False  # This is actually a good match
            if ("complaint" in faq or "grievance" in faq) and "facilities" not in faq:
                return False  # This is actually a good match

    # Registration Deadline vs Procedure
    if "registration" in query:
        if ("deadline" in query or "date" in query) and ("procedure" in faq or "steps" in faq):
            return True
        if ("procedure" in query or "steps" in query) and ("deadline" in faq or "date" in faq):
            return True

    # LMS vs Portal for password queries
    if "password" in query or "reset" in query or "forgot" in query:
        if "lms" in query and "portal" in faq and "lms" not in faq:
            return True
        if "portal" in query and "lms" in faq and "portal" not in faq:
            return True

    # Fee vs Program
    if "fee" in query and ("program" in query or "degree" in query or "course" in query):
        if "fee" not in faq and ("program" in faq or "degree" in faq or "course" in faq):
            return True

    # Engineering Fee vs Engineering Program
    if "engineering" in query and "fee" in query:
        if "engineering" in faq and "fee" not in faq:
            # Check if FAQ is about program structure, not fee
            if any(term in faq for term in ["curriculum", "syllabus", "structure", "courses", "subjects"]):
                return True

    # Scholarship Availability vs Specific Scholarship
    if "scholarship" in query:
        if "available" in query and "list" not in query:
            # If FAQ is about a specific scholarship, it might be a mismatch
            if "available" not in faq and "list" not in faq:
                return True

    return False


# ============================================================
# HELPER: GET STRICT THRESHOLDS
# ============================================================

def _get_strict_thresholds(query: str, faq_question: str) -> Tuple[float, float]:
    """
    Get stricter thresholds for known confusion cases.
    Returns (min_confidence, min_similarity)
    """
    query = query.lower()
    faq = faq_question.lower()

    # Hostel Facilities vs Complaint
    if "hostel" in query:
        if "facilities" in query and ("complaint" in faq or "grievance" in faq):
            return 0.75, 0.40
        if "complaint" in query and ("facilities" in faq or "services" in faq):
            return 0.75, 0.40

    # Registration Deadline vs Procedure
    if "registration" in query:
        if ("deadline" in query or "date" in query) and ("procedure" in faq or "steps" in faq):
            return 0.75, 0.40
        if ("procedure" in query or "steps" in query) and ("deadline" in faq or "date" in faq):
            return 0.75, 0.40

    # Scholarship vs Fee/Program
    if "scholarship" in query:
        if "available" in query and "list" not in query:
            if "available" not in faq and "list" not in faq:
                return 0.72, 0.38

    # Fee vs Program
    if "fee" in query and ("program" in query or "degree" in query or "course" in query):
        if "fee" not in faq and ("program" in faq or "degree" in faq or "course" in faq):
            return 0.72, 0.38

    # Engineering Fee
    if "engineering" in query and "fee" in query:
        if "engineering" in faq and "fee" not in faq:
            return 0.72, 0.38

    # LMS vs Portal
    if ("lms" in query or "portal" in query) and ("password" in query or "reset" in query):
        if "lms" in query and "portal" in faq and "lms" not in faq:
            return 0.75, 0.40
        if "portal" in query and "lms" in faq and "portal" not in faq:
            return 0.75, 0.40

    return 0.65, 0.28  # Default strict thresholds


# ============================================================
# SAFE RESULT NORMALIZATION - ENHANCED
# ============================================================

def _normalize_program_result(result: dict) -> dict:
    """Normalize program search result with safety checks."""
    
    similarity_score = result.get(
        "similarity_score",
        result.get("score", 0.0)
    )

    confidence_score = result.get(
        "confidence_score",
        0.0
    )

    confidence_level = result.get(
        "confidence_level",
        "Low"
    )

    # Ensure answer is not empty
    answer = result.get("answer", "")
    if not answer or len(answer.strip()) < 10:
        answer = (
            "I found some information about this program, "
            "but the details are not available in the current "
            "knowledge base. For complete information, please "
            "contact the relevant department or the IUB "
            "Information Center."
        )

    return {
        "answer": answer,
        "similarity_score": round(float(similarity_score), 4),
        "confidence_level": confidence_level,
        "confidence_score": round(float(confidence_score), 4),
        "model_name": result.get("model_name", "resolveai-iub-knowledge"),
        "model_version": result.get("model_version", "v1"),
        "source": result.get("source", "iub_programs"),
    }


# ============================================================
# MAIN STUDENT QUERY FUNCTION - ENHANCED
# ============================================================

def answer_student_query(query: str) -> dict:
    """
    Main entry point for answering IUB student/faculty questions.

    Priority order:
    1. FAQ/KB retrieval (with strict confidence checks)
    2. Program search (only for genuinely program-specific queries)
    3. Category-specific fallback
    4. General fallback

    NEVER returns a low-confidence FAQ answer.
    NEVER invents university facts.
    """
    
    # ============================================================
    # Step 1: Input Validation
    # ============================================================

    if query is None:
        query = ""

    if not isinstance(query, str):
        query = str(query)

    query = query.strip()

    if not query:
        return {
            "answer": (
                "Please enter a valid question. I am here to help with "
                "**IUB-related queries** about admissions, programs, "
                "fees, scholarships, portal, exams, and more.\n\n"
                "Example questions:\n"
                "• How can I reset my student portal password?\n"
                "• What is the admission deadline?\n"
                "• What is the fee for BS Engineering?\n"
                "• How do I register for courses?"
                + IUB_CONTACT
            ),
            "similarity_score": 0.0,
            "confidence_level": "Low",
            "confidence_score": 0.0,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "source": "empty_query",
        }

    # ============================================================
    # Step 2: FAQ Retrieval (ALWAYS first)
    # ============================================================

    faq_result = _safe_faq_result(query)

    try:
        faq_result = find_faq_answer(query)
    except Exception as exc:
        print(f"[STUDENT QUERY] FAQ search error: {exc}")
        faq_result = _safe_faq_result(query, str(exc))

    # Validate FAQ result structure
    if not isinstance(faq_result, dict):
        faq_result = _safe_faq_result(query, "invalid result type")

    faq_found = faq_result.get("found", False)

    # ============================================================
    # Step 3: Evaluate FAQ Result - STRICT ACCEPTANCE
    # ============================================================

    if faq_found:
        faq_confidence = float(faq_result.get("confidence_score", 0.0))
        faq_similarity = float(faq_result.get("similarity_score", 0.0))
        faq_level = faq_result.get("confidence_level", "Low")
        faq_question = faq_result.get("question", "")
        faq_answer = faq_result.get("answer", "")
        faq_source = faq_result.get("source", "faq_retrieval")

        # ========================================================
        # Step 3a: Check for intent mismatch
        # ========================================================

        has_mismatch = _has_intent_mismatch(query, faq_question)

        # ========================================================
        # Step 3b: Get appropriate thresholds
        # ========================================================

        if has_mismatch:
            min_confidence, min_similarity = _get_strict_thresholds(query, faq_question)
        else:
            # Standard thresholds
            if faq_level == "High":
                min_confidence = 0.75
                min_similarity = FAQ_ACCEPT_MIN_SIMILARITY_HIGH
            elif faq_level == "Medium":
                min_confidence = FAQ_ACCEPT_MEDIUM_CONFIDENCE
                min_similarity = FAQ_ACCEPT_MIN_SIMILARITY_MEDIUM
            else:
                # Low confidence - stricter
                min_confidence = 0.70
                min_similarity = 0.35

        # ========================================================
        # Step 3c: Determine if FAQ should be accepted
        # ========================================================

        # High confidence FAQ - always accept (if not mismatched)
        if faq_level == "High" and not has_mismatch:
            accept_faq = True
        # Medium or High with reasonable scores
        elif faq_confidence >= min_confidence and faq_similarity >= min_similarity:
            accept_faq = True
        # High confidence but mismatch - still need to pass thresholds
        elif faq_level == "High" and faq_confidence >= 0.80 and faq_similarity >= 0.35:
            accept_faq = True
        # Very high confidence overrides everything
        elif faq_confidence >= 0.85 and faq_similarity >= 0.30:
            accept_faq = True
        else:
            accept_faq = False

        # ========================================================
        # Step 3d: Return accepted FAQ result
        # ========================================================

        if accept_faq:
            # Ensure answer is complete and helpful
            answer = faq_answer
            if not answer or len(answer.strip()) < 20:
                answer = (
                    "I found this question in the IUB FAQ database, "
                    "but the answer needs additional verification.\n\n"
                    "For complete information, please contact the "
                    "IUB Information Center." + IUB_CONTACT
                )

            return {
                "answer": answer,
                "similarity_score": round(faq_similarity, 4),
                "confidence_level": faq_level,
                "confidence_score": round(faq_confidence, 4),
                "model_name": faq_result.get("model_name", "resolveai-faq-retriever"),
                "model_version": faq_result.get("model_version", "v1"),
                "source": faq_source,
            }

    # ============================================================
    # Step 4: Category Detection
    # ============================================================

    category = detect_category(query)

    # ============================================================
    # Step 5: Program-Specific Query Handling
    # ============================================================
    #
    # Only use program search if:
    # 1. The query is program-specific AND
    # 2. FAQ didn't have a confident answer
    # ============================================================

    program_result = None
    use_program_search = is_program_specific_query(query)

    if use_program_search:
        try:
            program_result = search_iub_programs(query)
        except Exception as exc:
            print(f"[STUDENT QUERY] Program search error: {exc}")
            program_result = None

        if program_result:
            normalized = _normalize_program_result(program_result)

            program_confidence = float(normalized.get("confidence_score", 0.0))
            program_similarity = float(normalized.get("similarity_score", 0.0))

            # Accept program result if confident enough
            if (
                program_confidence >= PROGRAM_ACCEPT_MIN_CONFIDENCE
                or program_similarity >= PROGRAM_ACCEPT_MIN_SIMILARITY
            ):
                return normalized

    # ============================================================
    # Step 6: Safe Final Fallback
    # ============================================================
    #
    # IMPORTANT: Never return a low-confidence FAQ answer.
    # It's better to say "I don't know" than to give wrong info.
    # ============================================================

    fallback = fallback_answer(category)

    # Ensure fallback is not empty
    if not fallback or len(fallback.strip()) < 50:
        fallback = (
            "I am the **IUB AI Help Desk**, your virtual assistant for "
            "**The Islamia University of Bahawalpur**.\n\n"
            "I could not find a sufficiently verified answer "
            "for your specific question at this moment.\n\n"
            "For personalized assistance, please contact the "
            "**IUB Information Center/Helpline**."
            + IUB_CONTACT
        )

    return {
        "answer": fallback,
        "similarity_score": round(
            float(faq_result.get("similarity_score", 0.0)),
            4
        ),
        "confidence_level": "Low",
        "confidence_score": round(
            float(faq_result.get("confidence_score", 0.0)),
            4
        ),
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "source": "safe_fallback",
        "_category": category,  # Debug info
        "_program_search_used": use_program_search,
    }


# ============================================================
# END OF FILE
# ============================================================