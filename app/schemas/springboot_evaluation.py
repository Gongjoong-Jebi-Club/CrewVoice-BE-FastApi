"""
Spring Boot 연동 API 스키마
"""
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional


class WeightsConfig(BaseModel):
    """
    평가 요소별 가중치 설정

    SpringBoot 제약 조건:
    - 가중치 범위: 0.0 ~ 1.0, 0.05 단위 (0.0, 0.05, 0.10, ..., 0.95, 1.0)
    - 각 평가요소별 가중치 합 = 1.0
    - Speed 편차: 5.0 ~ 10.0, 0.5 단위
    """

    # === Tone (톤) 가중치 - 합 = 1.0 ===
    weight_clarity: float = Field(..., ge=0.0, le=1.0, description="명료도 (0.0~1.0, 0.05 단위)")
    weight_stability: float = Field(..., ge=0.0, le=1.0, description="안정성 (0.0~1.0, 0.05 단위)")
    weight_brightness: float = Field(..., ge=0.0, le=1.0, description="밝기 (0.0~1.0, 0.05 단위)")
    weight_pitch_position: float = Field(..., ge=0.0, le=1.0, description="음높이 위치 (0.0~1.0, 0.05 단위)")

    # === Pause (휴지) 가중치 - 합 = 1.0 ===
    weight_fluency: float = Field(..., ge=0.0, le=1.0, description="유창성 (0.0~1.0, 0.05 단위)")
    weight_position: float = Field(..., ge=0.0, le=1.0, description="Pause 위치 (0.0~1.0, 0.05 단위)")
    weight_length: float = Field(..., ge=0.0, le=1.0, description="Pause 길이 (0.0~1.0, 0.05 단위)")

    # === Accent (강조) 가중치 - 합 = 1.0 ===
    weight_pitch: float = Field(..., ge=0.0, le=1.0, description="음높이 변화 (0.0~1.0, 0.05 단위)")
    weight_energy: float = Field(..., ge=0.0, le=1.0, description="강약 변화 (0.0~1.0, 0.05 단위)")

    # === Intonation (억양) 가중치 - 합 = 1.0 ===
    weight_baseline: float = Field(..., ge=0.0, le=1.0, description="음성 억양 피치 지표 (0.0~1.0, 0.05 단위)")
    weight_iso: float = Field(..., ge=0.0, le=1.0, description="ISO 25000 점수 (0.0~1.0, 0.05 단위)")

    # === Speed (속도) 파라미터 ===
    deviation_threshold: float = Field(..., ge=5.0, le=10.0, description="편차 허용도 (5.0~10.0, 0.5 단위)")

    # === 공통 파라미터 ===
    gender: str = Field(..., pattern="^[MF]$", description="성별 (M 또는 F)")

    @model_validator(mode='after')
    def validate_weights(self):
        """가중치 합 및 단위 검증"""

        # Tone 가중치 합 검증
        tone_sum = round(
            self.weight_clarity +
            self.weight_stability +
            self.weight_brightness +
            self.weight_pitch_position,
            2
        )
        if abs(tone_sum - 1.0) > 0.01:
            raise ValueError(
                f"Tone 가중치의 합이 1.0이 아닙니다: {tone_sum} "
                f"(clarity={self.weight_clarity}, stability={self.weight_stability}, "
                f"brightness={self.weight_brightness}, pitch_position={self.weight_pitch_position})"
            )

        # Pause 가중치 합 검증
        pause_sum = round(
            self.weight_fluency +
            self.weight_position +
            self.weight_length,
            2
        )
        if abs(pause_sum - 1.0) > 0.01:
            raise ValueError(
                f"Pause 가중치의 합이 1.0이 아닙니다: {pause_sum} "
                f"(fluency={self.weight_fluency}, position={self.weight_position}, length={self.weight_length})"
            )

        # Accent 가중치 합 검증
        accent_sum = round(self.weight_pitch + self.weight_energy, 2)
        if abs(accent_sum - 1.0) > 0.01:
            raise ValueError(
                f"Accent 가중치의 합이 1.0이 아닙니다: {accent_sum} "
                f"(pitch={self.weight_pitch}, energy={self.weight_energy})"
            )

        # Intonation 가중치 합 검증
        intonation_sum = round(self.weight_baseline + self.weight_iso, 2)
        if abs(intonation_sum - 1.0) > 0.01:
            raise ValueError(
                f"Intonation 가중치의 합이 1.0이 아닙니다: {intonation_sum} "
                f"(baseline={self.weight_baseline}, iso={self.weight_iso})"
            )

        # 0.05 단위 검증 (일반 가중치)
        weight_fields = [
            ('weight_clarity', self.weight_clarity),
            ('weight_stability', self.weight_stability),
            ('weight_brightness', self.weight_brightness),
            ('weight_pitch_position', self.weight_pitch_position),
            ('weight_fluency', self.weight_fluency),
            ('weight_position', self.weight_position),
            ('weight_length', self.weight_length),
            ('weight_pitch', self.weight_pitch),
            ('weight_energy', self.weight_energy),
            ('weight_baseline', self.weight_baseline),
            ('weight_iso', self.weight_iso),
        ]

        for field_name, value in weight_fields:
            # 0.05 단위인지 확인 (부동소수점 오차 허용)
            remainder = round((value * 100) % 5, 2)
            if remainder != 0.0:
                raise ValueError(
                    f"{field_name}은 0.05 단위여야 합니다: {value} "
                    f"(가능한 값: 0.0, 0.05, 0.10, 0.15, ..., 0.95, 1.0)"
                )

        # Speed 편차 허용도 0.5 단위 검증
        deviation_remainder = round((self.deviation_threshold * 10) % 5, 2)
        if deviation_remainder != 0.0:
            raise ValueError(
                f"deviation_threshold는 0.5 단위여야 합니다: {self.deviation_threshold} "
                f"(가능한 값: 5.0, 5.5, 6.0, 6.5, ..., 9.5, 10.0)"
            )

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
                "deviation_threshold": 7.5,
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
    - weights: 평가 가중치 설정 (Optional, 없으면 기본값 사용)

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
                    "score_accent": 75.00,
                    "overall_score": 83.17
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
