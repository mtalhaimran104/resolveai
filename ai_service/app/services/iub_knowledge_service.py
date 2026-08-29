import os
import re
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ============================================================
# CONFIGURATION
# ============================================================

PROGRAM_THRESHOLD = 0.35
PROGRAM_MEDIUM_THRESHOLD = 0.50
PROGRAM_HIGH_THRESHOLD = 0.70

TOP_PROGRAMS = 5

# Minimum score required before returning a generic IUB result
GENERAL_IUB_SCORE = 0.30


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

PROGRAM_DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "iub_programs.csv"
)

POSTGRADUATE_DATASET_PATH = os.path.join(
    BASE_DIR,
    "data",
    "iub_postgraduate_programs.csv"
)


# ============================================================
# VERIFIED IUB CONTACT INFORMATION
# ============================================================

IUB_HELPLINE = (
    "**IUB Information Center/Helpline:** "
    "**0346-9255555, 0347-9255555, 062-9255580**"
)

IUB_HELPLINE_EMAIL = (
    "**Email:** **iubhelpline@iub.edu.pk**"
)

IUB_INFO_LOCATION = (
    "**Location:** **Basement of Sir Sadiq Muhammad Khan Library, "
    "Baghdad ul Jadeed Campus, Bahawalpur**"
)

IUB_WEBSITE = (
    "**Official Website:** **https://www.iub.edu.pk/**"
)


# ============================================================
# COMMON FOOTER
# ============================================================

def contact_footer(
    department="IUB Information Center/Helpline"
):
    return (
        f"For further verified assistance, please contact "
        f"**{department}**. "
        f"{IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_query(query):
    """
    Normalize a user query for matching.

    Handles:
    - lowercase
    - punctuation
    - hyphens
    - slashes
    - extra spaces
    """

    if query is None:
        return ""

    query = str(query).lower().strip()

    # Normalize common variations
    query = query.replace("&", " and ")

    # Convert separators to spaces
    query = re.sub(r"[-_/]", " ", query)

    # Remove punctuation but preserve letters/numbers
    query = re.sub(
        r"[^\w\s]",
        " ",
        query,
        flags=re.UNICODE
    )

    # Normalize whitespace
    query = re.sub(
        r"\s+",
        " ",
        query
    )

    return query.strip()


# ============================================================
# KEYWORD MATCHING
# ============================================================

def contains_keyword(query, keywords):
    """
    Safer keyword matching.

    Uses word boundaries so:
        bs
    does not accidentally match unrelated words.
    """

    q = normalize_query(query)

    for keyword in keywords:

        keyword = normalize_query(keyword)

        if not keyword:
            continue

        pattern = (
            r"(?<!\w)"
            + re.escape(keyword)
            + r"(?!\w)"
        )

        if re.search(pattern, q):
            return True

    return False


# ============================================================
# LOAD PROGRAM DATASET
# ============================================================

def load_program_dataset(path):

    if not os.path.exists(path):
        return pd.DataFrame()

    try:

        data = pd.read_csv(
            path
        )

        data = data.fillna("")

        required_columns = [
            "program_name",
            "level",
            "mode",
            "program_url"
        ]

        for column in required_columns:

            if column not in data.columns:
                data[column] = ""

            data[column] = (
                data[column]
                .astype(str)
                .str.strip()
            )

        # Remove empty program names
        data = data[
            data["program_name"] != ""
        ]

        data = data.reset_index(
            drop=True
        )

        return data

    except Exception as exc:

        print(
            f"[IUB Knowledge] Failed to load "
            f"{path}: {exc}"
        )

        return pd.DataFrame()


# ============================================================
# LOAD DATASETS
# ============================================================

programs = load_program_dataset(
    PROGRAM_DATASET_PATH
)

postgraduate_programs = load_program_dataset(
    POSTGRADUATE_DATASET_PATH
)


# ============================================================
# COMBINE DATASETS
# ============================================================

if not programs.empty and not postgraduate_programs.empty:

    all_programs = pd.concat(
        [
            programs,
            postgraduate_programs
        ],
        ignore_index=True
    )

elif not programs.empty:

    all_programs = programs.copy()

elif not postgraduate_programs.empty:

    all_programs = postgraduate_programs.copy()

else:

    all_programs = pd.DataFrame()


# ============================================================
# REMOVE DUPLICATES
# ============================================================

if not all_programs.empty:

    all_programs = (
        all_programs
        .drop_duplicates(
            subset=[
                "program_name",
                "level",
                "mode"
            ]
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# PREPARE PROGRAM SEARCH
# ============================================================

if not all_programs.empty:

    all_programs["search_text"] = (
        all_programs["program_name"]
        + " "
        + all_programs["level"]
        + " "
        + all_programs["mode"]
    )

    all_programs["normalized_name"] = (
        all_programs["program_name"]
        .apply(normalize_query)
    )

    program_vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=1
    )

    program_vectors = (
        program_vectorizer.fit_transform(
            all_programs["search_text"]
        )
    )

else:

    program_vectorizer = None
    program_vectors = None


# ============================================================
# CONFIDENCE
# ============================================================

def get_confidence(score):

    score = float(score)

    if score >= PROGRAM_HIGH_THRESHOLD:
        return "High"

    if score >= PROGRAM_MEDIUM_THRESHOLD:
        return "Medium"

    return "Low"


# ============================================================
# IUB DOMAIN KEYWORDS
# ============================================================

IUB_STRONG_KEYWORDS = [

    "iub",
    "islamia university",
    "islamia university of bahawalpur",
    "bahawalpur university",

    "student portal",
    "e portal",
    "eportal",

    "admission",
    "admissions",

    "scholarship",
    "scholarships",

    "hostel",
    "hostels",

    "university bus",
    "bus route",
    "transport",

    "date sheet",
    "roll number slip",

    "vice chancellor",
    "vc office",

    "harassment",
    "anti harassment",

    "finance office",
    "accounts office",

    "library card",

    "student registration",
    "course registration"
]


IUB_GENERAL_KEYWORDS = [

    "program",
    "programs",

    "course",
    "courses",

    "degree",
    "degrees",

    "bachelor",
    "master",

    "bs",
    "ms",
    "msc",
    "mphil",
    "m phil",
    "mba",
    "phd",

    "engineering",
    "computer science",
    "software engineering",

    "fee",
    "fees",
    "tuition",
    "challan",
    "refund",
    "payment",

    "financial aid",

    "student",
    "registration",
    "enrollment",

    "exam",
    "examination",
    "result",
    "results",

    "campus",
    "department",
    "directorate",
    "office",

    "helpline",
    "information center",
    "information centre",

    "complaint",
    "discrimination"
]


# ============================================================
# OUT OF DOMAIN KEYWORDS
# ============================================================

OUT_OF_DOMAIN_KEYWORDS = [

    "weather",
    "temperature",
    "forecast",
    "rain",
    "raining",

    "joke",
    "jokes",

    "movie",
    "movies",
    "song",
    "songs",
    "music",

    "recipe",
    "recipes",
    "pizza",
    "burger",

    "football",
    "cricket",
    "tennis",
    "basketball",

    "iphone",
    "laptop",
    "mobile phone",

    "write a poem",
    "write me a story",
    "tell me a story",

    "translate this",
    "summarize this"
]


# ============================================================
# DOMAIN DETECTION
# ============================================================

def is_iub_related(query):

    q = normalize_query(query)

    if not q:
        return False

    # --------------------------------------------------------
    # Explicit IUB mention
    # --------------------------------------------------------

    if contains_keyword(
        q,
        [
            "iub",
            "islamia university",
            "islamia university of bahawalpur",
            "bahawalpur university"
        ]
    ):
        return True

    # --------------------------------------------------------
    # Strong university-specific keywords
    # --------------------------------------------------------

    if contains_keyword(
        q,
        IUB_STRONG_KEYWORDS
    ):
        return True

    # --------------------------------------------------------
    # Explicit unrelated question
    # --------------------------------------------------------

    if contains_keyword(
        q,
        OUT_OF_DOMAIN_KEYWORDS
    ):
        return False

    # --------------------------------------------------------
    # General academic/university language
    # --------------------------------------------------------

    if contains_keyword(
        q,
        IUB_GENERAL_KEYWORDS
    ):
        return True

    return False


# ============================================================
# QUERY TYPE DETECTION
# ============================================================

def detect_query_type(query):

    q = normalize_query(query)

    # ========================================================
    # HARASSMENT
    # ========================================================

    if contains_keyword(
        q,
        [
            "harassment",
            "harass",
            "sexual harassment",
            "anti harassment",
            "discrimination"
        ]
    ):
        return "harassment"

    # ========================================================
    # VICE CHANCELLOR
    # ========================================================

    if contains_keyword(
        q,
        [
            "vc office",
            "vc location",
            "vice chancellor",
            "vice chancellor office",
            "vice chancellor location"
        ]
    ):
        return "vc"

    # ========================================================
    # PORTAL
    # ========================================================

    if contains_keyword(
        q,
        [
            "student portal",
            "student e portal",
            "e portal",
            "eportal",
            "portal",
            "portal not working",
            "portal not opening",
            "portal problem",
            "portal issue",
            "portal login",
            "login portal",
            "cannot login",
            "can not login",
            "unable to login",
            "forgot password",
            "forgot my password",
            "password reset",
            "reset password"
        ]
    ):
        return "portal"

    # ========================================================
    # ADMISSION
    # ========================================================

    if contains_keyword(
        q,
        [
            "admission",
            "admissions",
            "apply for admission",
            "how to apply",
            "application",
            "eligibility",
            "merit",
            "admission test",
            "entry test"
        ]
    ):
        return "admission"

    # ========================================================
    # SCHOLARSHIP
    # ========================================================

    if contains_keyword(
        q,
        [
            "scholarship",
            "scholarships",
            "financial aid",
            "honhaar",
            "student aid"
        ]
    ):
        return "scholarship"

    # ========================================================
    # FINANCE
    # ========================================================

    if contains_keyword(
        q,
        [
            "finance office",
            "finance",
            "fees",
            "fee",
            "challan",
            "refund",
            "accounts office",
            "accounts",
            "payment",
            "tuition fee",
            "fee structure"
        ]
    ):
        return "finance"

    # ========================================================
    # HOSTEL
    # ========================================================

    if contains_keyword(
        q,
        [
            "hostel",
            "hostels",
            "accommodation",
            "girls hostel",
            "boys hostel"
        ]
    ):
        return "hostel"

    # ========================================================
    # LIBRARY
    # ========================================================

    if contains_keyword(
        q,
        [
            "library",
            "libraries",
            "book issue",
            "library card"
        ]
    ):
        return "library"

    # ========================================================
    # TRANSPORT
    # ========================================================

    if contains_keyword(
        q,
        [
            "transport",
            "transportation",
            "bus service",
            "university bus",
            "bus route",
            "bus routes",
            "transport facility"
        ]
    ):
        return "transport"

    # ========================================================
    # EXAMINATION
    # ========================================================

    if contains_keyword(
        q,
        [
            "exam",
            "exams",
            "examination",
            "examinations",
            "date sheet",
            "result",
            "results",
            "controller examination",
            "roll number slip"
        ]
    ):
        return "examination"

    # ========================================================
    # PROGRAM
    # ========================================================

    if contains_keyword(
        q,
        [
            "course",
            "courses",
            "program",
            "programs",
            "degree",
            "degrees",
            "mphil",
            "m phil",
            "msc",
            "mba",
            "phd",
            "bachelor",
            "master",
            "bs",
            "ms",
            "engineering",
            "computer science",
            "software engineering"
        ]
    ):
        return "program"

    # ========================================================
    # LOCATION
    # ========================================================

    if contains_keyword(
        q,
        [
            "where is",
            "where are",
            "where can i find",
            "location",
            "located",
            "address",
            "office",
            "building"
        ]
    ):
        return "location"

    return "general"


# ============================================================
# DIRECT VERIFIED ANSWERS
# ============================================================

def vc_answer():

    return (
        "The **Vice Chancellor's Office of The Islamia University "
        "of Bahawalpur (IUB)** can be contacted through "
        "**062-9250231** and **062-9255860**. "
        "The official email is **vc@iub.edu.pk**. "
        "For confirmation regarding the current office location, "
        f"please contact {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def harassment_answer():

    return (
        "For harassment or discrimination-related assistance "
        "at IUB, students can contact the "
        "**IUB Anti-Harassment Committee**. "
        "Registered students can use the **Student Portal**, "
        "and complaints can also be submitted through "
        "**antiharassment@iub.edu.pk**. "
        "Complaints should follow the university's prescribed "
        "procedure. "
        f"For additional verified assistance, "
        f"{IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def portal_answer():

    return (
        "For an **IUB Student Portal/E-Portal** problem, first "
        "check your internet connection, refresh the page, "
        "try another browser and clear the browser cache. "
        "If the problem continues, contact the "
        "**Directorate of Information Technology** at "
        "**062-9255858** or **062-9255062**. "
        "For admission or portal-related assistance, "
        "**admission@iub.edu.pk** is also available. "
        f"{IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}. "
        f"{IUB_WEBSITE}"
    )


def admission_answer():

    return (
        "For **IUB admissions**, applicants should use the "
        "official IUB admission portal and follow the "
        "current application procedure. "
        "For admission-related guidance, contact the "
        "**Directorate of Academics** at **062-9255075**. "
        "For postgraduate admission matters, contact the "
        "**Directorate of Advanced Studies and Research Board** "
        "at **062-9255484** or "
        "**pg.admission@iub.edu.pk**. "
        "The **Directorate of Information Technology** can be "
        "contacted at **062-9255858** or **062-9255062** "
        "for relevant portal issues. "
        f"For additional assistance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}. "
        f"{IUB_WEBSITE}"
    )


def finance_answer():

    return (
        "For IUB matters related to **fees, challans, "
        "payments, refunds, accounts or financial issues**, "
        "please contact the relevant **Finance/Accounts Office** "
        "for the exact current procedure. "
        "I do not want to guess a fee amount, procedure or "
        "office location that may be outdated. "
        f"For verified assistance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def scholarship_answer():

    return (
        "For **IUB scholarships and financial assistance**, "
        "students should verify the current scholarship "
        "announcement, eligibility requirements, deadline "
        "and required documents through official IUB channels. "
        "Scholarship conditions can vary by scheme and "
        "academic program. "
        f"For verified guidance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def hostel_answer():

    return (
        "For **IUB hostels and accommodation**, information "
        "about availability, eligibility, fees, hostel "
        "admission and room allocation should be confirmed "
        "with the relevant university hostel administration. "
        f"For verified assistance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def library_answer():

    return (
        "The **IUB library system** provides students with "
        "academic resources and library services. "
        "For current library timings, membership, book-issue "
        "rules or a specific library location, please verify "
        "the information with the relevant IUB library. "
        f"For further assistance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def transport_answer():

    return (
        "For **IUB transport/bus services**, including routes, "
        "timings, eligibility, fees and current availability, "
        "please verify the latest schedule with the university "
        "transport administration. "
        f"For verified assistance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


def examination_answer():

    return (
        "For **IUB examination matters**, including date sheets, "
        "results, roll number slips, examination schedules or "
        "procedures, please verify the latest information "
        "through the relevant university examination office "
        "or official IUB announcements. "
        f"For verified assistance, {IUB_HELPLINE}, "
        f"{IUB_HELPLINE_EMAIL}, "
        f"{IUB_INFO_LOCATION}. "
        f"{IUB_WEBSITE}"
    )


# ============================================================
# GENERAL ANSWER
# ============================================================

def general_answer():

    return (
        "I am the **IUB AI Help Desk**. I can assist with "
        "verified information related to **The Islamia University "
        "of Bahawalpur (IUB)**, including **academic programs, "
        "admissions, fees, scholarships, examinations, student "
        "portal, registration, hostels, library, transport, "
        "offices, departments and other university services**. "
        f"{contact_footer()}"
    )


# ============================================================
# OUT-OF-DOMAIN ANSWER
# ============================================================

def out_of_domain_answer():

    return (
        "I can only assist with **The Islamia University of "
        "Bahawalpur (IUB)** and its academic, student and "
        "administrative services. "
        "I cannot reliably answer unrelated questions. "
        "Please ask an IUB-related question about programs, "
        "admissions, fees, scholarships, examinations, "
        "student portal, registration, hostels, library, "
        "transport, offices or student services."
    )


# ============================================================
# BROAD PROGRAM QUERY DETECTION
# ============================================================

def is_broad_program_query(query):

    q = normalize_query(query)

    broad_phrases = [

        "what courses",
        "which courses",
        "courses offered",
        "course offered",

        "what programs",
        "which programs",
        "programs offered",
        "program offered",

        "what degrees",
        "which degrees",
        "degrees offered",
        "degree offered",

        "what can i study",
        "what can i study at iub",

        "what programs are offered",
        "what degrees are offered",

        "list of programs",
        "list programs",

        "list of degrees",
        "list degrees"
    ]

    return any(
        phrase in q
        for phrase in broad_phrases
    )


# ============================================================
# FORMAT PROGRAM
# ============================================================

def format_program(row):

    text = f"**{row['program_name']}**"

    if row["level"]:
        text += f" ({row['level']})"

    if row["mode"]:
        text += f" — {row['mode']}"

    if row["program_url"]:
        text += (
            f" — **Official Link:** "
            f"{row['program_url']}"
        )

    return text


# ============================================================
# PROGRAM SEARCH
# ============================================================

def program_answer(query):

    if (
        all_programs.empty
        or program_vectorizer is None
        or program_vectors is None
    ):
        return None, 0.0

    query = normalize_query(query)

    if not query:
        return None, 0.0

    # ========================================================
    # BROAD QUERY
    # ========================================================

    if is_broad_program_query(query):

        # For broad queries, return programs but do not
        # falsely claim that these are the complete list.

        results = []

        limit = min(
            len(all_programs),
            TOP_PROGRAMS
        )

        for index in range(limit):

            row = all_programs.iloc[index]

            results.append(
                format_program(row)
            )

        if not results:
            return None, 0.0

        answer = (
            "The **Islamia University of Bahawalpur (IUB)** "
            "offers undergraduate, graduate and postgraduate "
            "programs across different academic disciplines. "
            "Some programs in the available IUB program "
            "records include:\n\n"
            + "\n".join(
                f"- {item}"
                for item in results
            )
            + "\n\n"
            "This is only a selection from the available "
            "records, not necessarily the complete list. "
            f"For the latest complete program list, "
            f"eligibility criteria and admission information, "
            f"please visit {IUB_WEBSITE}."
        )

        return answer, 0.90

    # ========================================================
    # SPECIFIC PROGRAM SEARCH
    # ========================================================

    query_vector = (
        program_vectorizer.transform(
            [query]
        )
    )

    similarities = cosine_similarity(
        query_vector,
        program_vectors
    )[0]

    if len(similarities) == 0:
        return None, 0.0

    ranked_indices = sorted(
        range(len(similarities)),
        key=lambda i: similarities[i],
        reverse=True
    )

    best_index = ranked_indices[0]

    best_score = float(
        similarities[best_index]
    )

    # ========================================================
    # CONFIDENCE CHECK
    # ========================================================

    if best_score < PROGRAM_THRESHOLD:

        return None, best_score

    # ========================================================
    # RETURN ONLY STRONG MATCHES
    # ========================================================

    matched_indices = [
        index
        for index in ranked_indices
        if similarities[index] >= PROGRAM_THRESHOLD
    ]

    matched_indices = matched_indices[
        :TOP_PROGRAMS
    ]

    results = []

    for index in matched_indices:

        row = all_programs.iloc[index]

        results.append(
            format_program(row)
        )

    if not results:
        return None, best_score

    answer = (
        "According to the available IUB program records, "
        "the program information most relevant to your "
        "query is:\n\n"
        + "\n".join(
            f"- {item}"
            for item in results
        )
        + "\n\n"
        "Please verify current eligibility, admission "
        "requirements, availability and deadlines through "
        f"{IUB_WEBSITE}."
    )

    return answer, best_score


# ============================================================
# MAIN FUNCTION
# ============================================================

def search_iub_programs(query: str):

    query = str(query).strip()

    # ========================================================
    # EMPTY QUERY
    # ========================================================

    if not query:

        return {
            "answer": (
                "Please enter a valid IUB-related question. "
                + contact_footer()
            ),
            "similarity_score": 0.0,
            "confidence_level": "Low",
            "query_type": "empty"
        }

    # ========================================================
    # DOMAIN CHECK
    # ========================================================

    if not is_iub_related(query):

        return {
            "answer": out_of_domain_answer(),
            "similarity_score": 0.0,
            "confidence_level": "Low",
            "query_type": "out_of_domain"
        }

    # ========================================================
    # QUERY TYPE
    # ========================================================

    query_type = detect_query_type(
        query
    )

    # ========================================================
    # DIRECT ANSWERS
    # ========================================================

    direct_answers = {

        "vc": vc_answer,

        "harassment": harassment_answer,

        "portal": portal_answer,

        "admission": admission_answer,

        "finance": finance_answer,

        "scholarship": scholarship_answer,

        "hostel": hostel_answer,

        "library": library_answer,

        "transport": transport_answer,

        "examination": examination_answer
    }

    if query_type in direct_answers:

        return {
            "answer": direct_answers[
                query_type
            ](),
            "similarity_score": 1.0,
            "confidence_level": "High",
            "query_type": query_type
        }

    # ========================================================
    # PROGRAM SEARCH
    # ========================================================

    if query_type == "program":

        answer, score = program_answer(
            query
        )

        if answer:

            return {
                "answer": answer,
                "similarity_score": round(
                    float(score),
                    4
                ),
                "confidence_level": get_confidence(
                    score
                ),
                "query_type": "program"
            }

        return {
            "answer": (
                "I could not verify the exact program "
                "information for this query from the "
                "available IUB program records. "
                "I do not want to provide an incorrect "
                "program name. "
                f"Please check the official IUB program "
                f"information at {IUB_WEBSITE}."
            ),
            "similarity_score": round(
                float(score),
                4
            ),
            "confidence_level": "Low",
            "query_type": "program"
        }

    # ========================================================
    # LOCATION
    # ========================================================

    if query_type == "location":

        return {
            "answer": (
                "I can help identify IUB offices, "
                "departments and campus locations when "
                "verified information is available. "
                "I do not want to guess a location that "
                "may be incorrect. "
                "Please provide the specific office, "
                "department or building name. "
                f"{contact_footer()}"
            ),
            "similarity_score": 1.0,
            "confidence_level": "Medium",
            "query_type": "location"
        }

    # ========================================================
    # GENERAL IUB QUERY
    # ========================================================

    return {
        "answer": general_answer(),
        "similarity_score": 0.80,
        "confidence_level": "Medium",
        "query_type": "general"
    }