from fastapi import APIRouter

from app.schemas.student_query import (
    StudentQueryRequest,
    StudentQueryResponse,
)

from app.services.student_query_service import (
    answer_student_query,
)


router = APIRouter(
    prefix="/student-query",
    tags=["Student Query"],
)


@router.post(
    "/",
    response_model=StudentQueryResponse,
)
def student_query(
    request: StudentQueryRequest,
):

    result = answer_student_query(
        request.question
    )

    return StudentQueryResponse(
        question=request.question,

        answer=result.get(
            "answer",
            "",
        ),

        similarity_score=result.get(
            "similarity_score",
            0.0,
        ),

        confidence_level=result.get(
            "confidence_level",
            "Low",
        ),

        confidence_score=result.get(
            "confidence_score",
            0.0,
        ),

        model_name=result.get(
            "model_name",
            "resolveai-student-query",
        ),

        model_version=result.get(
            "model_version",
            "v1",
        ),
    )