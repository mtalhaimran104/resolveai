from fastapi import APIRouter

from app.schemas.student_query import (
    StudentQueryRequest,
    StudentQueryResponse
)

from app.services.student_query_service import (
    answer_student_query
)


router = APIRouter(
    prefix="/student-query",
    tags=["Student Query"]
)


@router.post(
    "/",
    response_model=StudentQueryResponse
)
def student_query(
    request: StudentQueryRequest
):

    result = answer_student_query(
        request.question
    )

    return {
        "question": request.question,
        "answer": result["answer"],
        "similarity_score": result["similarity_score"],
        "confidence_level": result["confidence_level"]
    }