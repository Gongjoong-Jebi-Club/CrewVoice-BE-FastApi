"""
Spring Boot 연동 API 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional


class EvaluationRequest(BaseModel):
    """
    Spring Boot → FastAPI 평가 요청 모델

    Spring Boot가 제공하는 필수 정보:
    - task_id: Spring Boot에서 생성한 UUID
    - audio_url: S3 Presigned URL (15분 유효)
    - script: 정답 스크립트 (사용자가 읽어야 할 텍스트)
    - language: 언어 코드 (ko-KR 또는 en-US)
    - callback_url: 결과를 받을 Spring Boot callback URL

    ⚠️ Spring Boot는 camelCase를 사용하므로 alias 설정
    """
    task_id: str = Field(..., alias="taskId")
    audio_url: str = Field(..., alias="audioUrl")
    script: str
    language: str
    callback_url: str = Field(..., alias="callbackUrl")

    class Config:
        populate_by_name = True  # snake_case와 camelCase 모두 허용
        json_schema_extra = {
            "example": {
                "taskId": "550e8400-e29b-41d4-a716-446655440000",
                "audioUrl": "https://s3.ap-northeast-2.amazonaws.com/bucket/test.wav?X-Amz-Algorithm=...",
                "script": "안녕하세요 승객 여러분, 잠시 후 이륙하겠습니다.",
                "language": "ko-KR",
                "callbackUrl": "https://server.crewvoice.cloud:8080/api/v1/evaluations/callback"
            }
        }


class EvaluationAcceptedResponse(BaseModel):
    """
    FastAPI → Spring Boot 즉시 응답 모델 (HTTP 200 OK)

    Spring Boot 명세에 따라 200 OK 반환
    """
    message: str = "Request received"
    task_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Request received",
                "task_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class ScoresPayload(BaseModel):
    """점수 객체"""
    score_pronunciation: float
    score_pause: float
    score_intonation: float
    score_tone: float
    score_speed: float
    score_accent: float
    overall_score: float


class CallbackSuccessPayload(BaseModel):
    """
    FastAPI → Spring Boot 성공 콜백 페이로드

    분석 완료 시 전송
    """
    task_id: str
    status: str = "completed"
    scores: ScoresPayload
    feedback_summary: str

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "scores": {
                    "score_pronunciation": 85.50,
                    "score_pause": 90.00,
                    "score_intonation": 78.50,
                    "score_tone": 82.00,
                    "score_speed": 88.00,
                    "score_accent": 75.00,
                    "overall_score": 83.17
                },
                "feedback_summary": "전반적으로 우수한 발음을 보였습니다. 억양 조절과 액센트 개선이 필요합니다."
            }
        }


class CallbackFailurePayload(BaseModel):
    """
    FastAPI → Spring Boot 실패 콜백 페이로드

    분석 실패 시 전송
    """
    task_id: str
    status: str = "failed"
    error_message: str

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "failed",
                "error_message": "오디오 파일 다운로드 실패 (S3 403 Forbidden)"
            }
        }
