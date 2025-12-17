"""
Spring Boot 연동 API 스키마
"""
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional


class WeightsConfig(BaseModel):
    """
    평가 가중치 설정 (SpringBoot → FastAPI)

    모든 필드는 Optional (전달하지 않으면 analyzer 기본값 사용)

    제약 조건:
    - 일반 가중치: 0.0 ~ 1.0, 0.05 단위
    - Speed deviation_threshold: 5.0 ~ 10.0, 0.5 단위
    - 평가요소별 가중치 합 = 1.0
    """
    # Tone 가중치 (합 = 1.0)
    weight_clarity: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_stability: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_brightness: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_pitch_position: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Pause 가중치 (합 = 1.0)
    weight_fluency: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_position: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_length: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Accent 가중치 (합 = 1.0)
    weight_pitch: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_energy: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Intonation 가중치 (합 = 1.0)
    weight_baseline: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_iso: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Speed 편차 임계값 (5.0 ~ 10.0, 0.5 단위)
    deviation_threshold: Optional[float] = Field(None, ge=5.0, le=10.0)

    # 성별 (Tone, Intonation에서 사용)
    gender: Optional[str] = Field(None, pattern="^(M|F)$")

    @model_validator(mode='after')
    def validate_weights(self):
        """가중치 검증: 0.05 단위 + 카테고리별 합=1.0"""

        # 0.05 단위 검증 (일반 가중치)
        weight_fields = [
            ("weight_clarity", self.weight_clarity),
            ("weight_stability", self.weight_stability),
            ("weight_brightness", self.weight_brightness),
            ("weight_pitch_position", self.weight_pitch_position),
            ("weight_fluency", self.weight_fluency),
            ("weight_position", self.weight_position),
            ("weight_length", self.weight_length),
            ("weight_pitch", self.weight_pitch),
            ("weight_energy", self.weight_energy),
            ("weight_baseline", self.weight_baseline),
            ("weight_iso", self.weight_iso),
        ]

        for field_name, value in weight_fields:
            if value is not None:
                # 0.05 단위 검증 (오차 허용: 0.001)
                remainder = round((value * 100) % 5, 2)
                if remainder != 0.0:
                    raise ValueError(f"{field_name}은 0.05 단위여야 합니다 (현재: {value}, remainder: {remainder})")

        # Speed deviation_threshold 0.5 단위 검증
        if self.deviation_threshold is not None:
            remainder = round((self.deviation_threshold * 10) % 5, 2)
            if remainder != 0.0:
                raise ValueError(f"deviation_threshold는 0.5 단위여야 합니다 (현재: {self.deviation_threshold})")

        # 카테고리별 가중치 합 = 1.0 검증
        # Tone 가중치 합 검증 (4개 모두 있을 때만)
        if all([self.weight_clarity is not None,
                self.weight_stability is not None,
                self.weight_brightness is not None,
                self.weight_pitch_position is not None]):
            tone_sum = round(
                self.weight_clarity +
                self.weight_stability +
                self.weight_brightness +
                self.weight_pitch_position,
                2
            )
            if abs(tone_sum - 1.0) > 0.01:
                raise ValueError(f"Tone 가중치의 합이 1.0이 아닙니다: {tone_sum}")

        # Pause 가중치 합 검증 (3개 모두 있을 때만)
        if all([self.weight_fluency is not None,
                self.weight_position is not None,
                self.weight_length is not None]):
            pause_sum = round(
                self.weight_fluency +
                self.weight_position +
                self.weight_length,
                2
            )
            if abs(pause_sum - 1.0) > 0.01:
                raise ValueError(f"Pause 가중치의 합이 1.0이 아닙니다: {pause_sum}")

        # Accent 가중치 합 검증 (2개 모두 있을 때만)
        if all([self.weight_pitch is not None,
                self.weight_energy is not None]):
            accent_sum = round(
                self.weight_pitch +
                self.weight_energy,
                2
            )
            if abs(accent_sum - 1.0) > 0.01:
                raise ValueError(f"Accent 가중치의 합이 1.0이 아닙니다: {accent_sum}")

        # Intonation 가중치 합 검증 (2개 모두 있을 때만)
        if all([self.weight_baseline is not None,
                self.weight_iso is not None]):
            intonation_sum = round(
                self.weight_baseline +
                self.weight_iso,
                2
            )
            if abs(intonation_sum - 1.0) > 0.01:
                raise ValueError(f"Intonation 가중치의 합이 1.0이 아닙니다: {intonation_sum}")

        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "weight_clarity": 0.4,
                "weight_stability": 0.3,
                "weight_brightness": 0.2,
                "weight_pitch_position": 0.1,
                "weight_fluency": 0.7,
                "weight_position": 0.2,
                "weight_length": 0.1,
                "weight_pitch": 0.6,
                "weight_energy": 0.4,
                "weight_baseline": 0.7,
                "weight_iso": 0.3,
                "deviation_threshold": 5.0,
                "gender": "F"
            }
        }
    )


class EvaluationRequest(BaseModel):
    """
    Spring Boot → FastAPI 평가 요청 모델

    Spring Boot가 제공하는 필수 정보:
    - task_id: Spring Boot에서 생성한 UUID
    - audio_url: S3 Presigned URL (15분 유효)
    - script: 정답 스크립트 (사용자가 읽어야 할 텍스트)
    - language: 언어 코드 (ko-KR 또는 en-US)
    - callback_url: 결과를 받을 Spring Boot callback URL
    - weights: 평가 가중치 설정 (선택, 없으면 기본값 사용)

    ⚠️ Spring Boot는 camelCase를 사용하므로 alias 설정
    """
    task_id: str = Field(..., alias="taskId")
    audio_url: str = Field(..., alias="audioUrl")
    script: str
    language: str
    callback_url: str = Field(..., alias="callbackUrl")
    weights: Optional[WeightsConfig] = None

    model_config = ConfigDict(
        populate_by_name=True,  # snake_case와 camelCase 모두 허용
        json_schema_extra={
            "example": {
                "taskId": "550e8400-e29b-41d4-a716-446655440000",
                "audioUrl": "https://s3.ap-northeast-2.amazonaws.com/bucket/test.wav?X-Amz-Algorithm=...",
                "script": "안녕하세요 승객 여러분, 잠시 후 이륙하겠습니다.",
                "language": "ko-KR",
                "callbackUrl": "https://server.crewvoice.cloud:8080/api/v1/evaluations/callback",
                "weights": {
                    "weight_clarity": 0.4,
                    "weight_stability": 0.3,
                    "weight_brightness": 0.2,
                    "weight_pitch_position": 0.1,
                    "weight_fluency": 0.7,
                    "weight_position": 0.2,
                    "weight_length": 0.1,
                    "weight_pitch": 0.6,
                    "weight_energy": 0.4,
                    "weight_baseline": 0.7,
                    "weight_iso": 0.3,
                    "deviation_threshold": 7.5,
                    "gender": "F"
                }
            }
        }
    )


class EvaluationAcceptedResponse(BaseModel):
    """
    FastAPI → Spring Boot 즉시 응답 모델 (HTTP 200 OK)

    Spring Boot 명세에 따라 200 OK 반환
    """
    message: str = "Request received"
    task_id: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Request received",
                "task_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )


class ScoresPayload(BaseModel):
    """점수 객체"""
    score_pronunciation: float
    score_pause: float
    score_intonation: float
    score_tone: float
    score_speed: float
    score_accent: float


class CallbackSuccessPayload(BaseModel):
    """
    FastAPI → Spring Boot 성공 콜백 페이로드

    분석 완료 시 전송
    """
    task_id: str
    status: str = "completed"
    scores: ScoresPayload
    feedback_summary: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "scores": {
                    "score_pronunciation": 85.50,
                    "score_pause": 90.00,
                    "score_intonation": 78.50,
                    "score_tone": 82.00,
                    "score_speed": 88.00,
                    "score_accent": 75.00
                },
                "feedback_summary": "전반적으로 우수한 발음을 보였습니다. 억양 조절과 액센트 개선이 필요합니다."
            }
        }
    )


class CallbackFailurePayload(BaseModel):
    """
    FastAPI → Spring Boot 실패 콜백 페이로드

    분석 실패 시 전송
    """
    task_id: str
    status: str = "failed"
    error_message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "failed",
                "error_message": "오디오 파일 다운로드 실패 (S3 403 Forbidden)"
            }
        }
    )
