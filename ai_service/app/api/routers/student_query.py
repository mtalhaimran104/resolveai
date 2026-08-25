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
        answer=result["answer"],
        similarity_score=result.get(
            "similarity_score",
            0.0,
        ),
        confidence_level=result.get(
            "confidence_level",
            "Low",
        ),
        model_name="resolveai-student-query",
        model_version="v1",
        confidence_score=None,
    )