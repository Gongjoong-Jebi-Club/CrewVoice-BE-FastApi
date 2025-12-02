"""
음성 제출 관련 Request/Response 스키마
"""
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class SubmissionRequest(BaseModel):
    """음성 제출 요청 스키마 (Form 데이터)"""
    user_id: int = Field(..., description="사용자 ID")
    evaluation_id: int = Field(..., description="평가 세션 ID")
    step: str = Field(..., description="평가 단계 (예: STEP2, STEP3)")
    question_index: int = Field(..., ge=0, description="문제 번호 (0부터 시작)")
    language: Literal["kor", "eng"] = Field(..., description="언어 코드")

    @field_validator("step")
    @classmethod
    def validate_step(cls, v: str) -> str:
        """Step 형식 검증"""
        if not v.startswith("STEP"):
            raise ValueError("step은 'STEP'으로 시작해야 합니다 (예: STEP2, STEP3)")
        return v.upper()


class SubmissionData(BaseModel):
    """제출 성공 시 반환되는 데이터"""
    submission_id: int = Field(..., description="제출 ID")


class SubmissionResponse(BaseModel):
    """API 응답 스키마"""
    code: int = Field(200, description="응답 코드")
    message: str = Field("제출 성공", description="응답 메시지")
    data: SubmissionData = Field(..., description="응답 데이터")

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": 200,
                "message": "제출 성공",
                "data": {
                    "submission_id": 105
                }
            }
        }
    }


class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    code: int = Field(..., description="에러 코드")
    message: str = Field(..., description="에러 메시지")
    detail: str | None = Field(None, description="에러 상세 정보")

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": 400,
                "message": "파일 형식 오류",
                "detail": "오디오 파일만 업로드 가능합니다"
            }
        }
    }
