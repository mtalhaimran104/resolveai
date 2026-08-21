from app.services.faq_service import (
    find_faq_answer
)

from app.services.iub_knowledge_service import (
    search_iub_programs
)


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
# CATEGORY KEYWORDS
# ============================================================

PROGRAM_KEYWORDS = [

    "program",
    "programs",
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
    "bs"

]


ADMISSION_KEYWORDS = [

    "admission",
    "admissions",
    "apply",
    "application",
    "eligibility",
    "merit",
    "deadline",
    "last date",
    "entry test",
    "prospectus"

]


SCHOLARSHIP_KEYWORDS = [

    "scholarship",
    "scholarships",
    "financial aid",
    "honhaar"

]


FEE_KEYWORDS = [

    "fee",
    "fees",
    "tuition",
    "finance",
    "financial",
    "challan",
    "payment",
    "installment",
    "dues",
    "refund",
    "accounts"

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
    "upload"

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
    "transport"

]


UNIFORM_KEYWORDS = [

    "uniform",
    "dress",
    "dress code",
    "color",
    "colour"

]


# ============================================================
# CATEGORY DETECTION
# ============================================================

def detect_category(query: str) -> str:

    query = query.lower().strip()

    # Order matters.

    if any(
        word in query
        for word in PROGRAM_KEYWORDS
    ):
        return "program"

    if any(
        word in query
        for word in ADMISSION_KEYWORDS
    ):
        return "admission"

    if any(
        word in query
        for word in SCHOLARSHIP_KEYWORDS
    ):
        return "scholarship"

    if any(
        word in query
        for word in FEE_KEYWORDS
    ):
        return "finance"

    if any(
        word in query
        for word in PORTAL_KEYWORDS
    ):
        return "portal"

    if any(
        word in query
        for word in LOCATION_KEYWORDS
    ):
        return "location"

    if any(
        word in query
        for word in UNIFORM_KEYWORDS
    ):
        return "uniform"

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
            "Office location that may be outdated.\n\n"
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
# MAIN STUDENT QUERY FUNCTION
# ============================================================

def answer_student_query(query: str) -> dict:

    query = query.strip()

    # ========================================================
    # EMPTY QUESTION
    # ========================================================

    if not query:

        return {
            "answer": (
                "Please enter a valid question."
                + IUB_CONTACT
            ),
            "similarity_score": 0.0,
            "confidence_level": "Low"
        }

    # ========================================================
    # CATEGORY
    # ========================================================

    category = detect_category(
        query
    )

    # ========================================================
    # PROGRAM QUESTIONS
    # ========================================================

    if category == "program":

        try:

            result = search_iub_programs(
                query
            )

            if result:

                return {
                    "answer": result["answer"],
                    "similarity_score": result[
                        "similarity_score"
                    ],
                    "confidence_level": result[
                        "confidence_level"
                    ]
                }

        except Exception as exc:

            print(
                f"[STUDENT QUERY] "
                f"Program search error: {exc}"
            )

        # If program knowledge fails,
        # continue to FAQ search.

    # ========================================================
    # FAQ SEARCH
    # ========================================================

    faq_result = find_faq_answer(
        query
    )

    # IMPORTANT:
    #
    # find_faq_answer() returns a DICTIONARY.
    #
    # Do not unpack it like:
    #
    # faq_answer, similarity, confidence = ...
    #

    if faq_result.get("found"):

        return {
            "answer": faq_result["answer"],
            "similarity_score": faq_result[
                "similarity_score"
            ],
            "confidence_level": faq_result[
                "confidence_level"
            ]
        }

    # ========================================================
    # CATEGORY FALLBACK
    # ========================================================

    return {
        "answer": fallback_answer(
            category
        ),
        "similarity_score": faq_result.get(
            "similarity_score",
            0.0
        ),
        "confidence_level": faq_result.get(
            "confidence_level",
            "Low"
        )
    }