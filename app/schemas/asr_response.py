"""
ASR Module Response Schemas
음성 분석 결과 응답 스키마
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class AgentScoreDetail(BaseModel):
    """개별 에이전트 점수 상세"""
    score: float = Field(..., description="100점 만점 점수")
    max_score: float = Field(default=100, description="최대 점수")
    feedback: List[str] = Field(default_factory=list, description="피드백 목록")
    status: str = Field(..., description="분석 상태 (success, error, warning)")


class ASRAnalysisResponse(BaseModel):
    """음성 분석 통합 응답"""
    overall_score: float = Field(..., description="전체 평균 점수 (100점 만점)")
    max_score: float = Field(default=100, description="최대 점수")
    scores: Dict[str, AgentScoreDetail] = Field(
        ...,
        description="각 에이전트별 점수 (pronunciation, accent, intonation, pause, speed, tone)"
    )
    detailed_results: Dict[str, Any] = Field(
        ...,
        description="각 에이전트의 상세 분석 결과"
    )
    analysis_summary: str = Field(..., description="분석 결과 요약")

    class Config:
        json_schema_extra = {
            "example": {
                "overall_score": 85.5,
                "max_score": 100,
                "scores": {
                    "pronunciation": {
                        "score": 88.0,
                        "max_score": 100,
                        "feedback": ["종합 발음 점수: 88.00 / 100"],
                        "status": "success"
                    },
                    "accent": {
                        "score": 82.0,
                        "max_score": 100,
                        "feedback": ["적절한 에너지 변화로 표현력이 좋습니다."],
                        "status": "success"
                    },
                    "intonation": {
                        "score": 85.0,
                        "max_score": 100,
                        "feedback": ["언어: 한국어", "억양 점수: 17.0 / 20.0점"],
                        "status": "success"
                    },
                    "pause": {
                        "score": 90.0,
                        "max_score": 100,
                        "feedback": ["유창성: 9.0/10.0점 (우수)"],
                        "status": "success"
                    },
                    "speed": {
                        "score": 87.0,
                        "max_score": 100,
                        "feedback": ["매우 좋음 - 적절한 발화 속도를 유지하고 있습니다."],
                        "status": "success"
                    },
                    "tone": {
                        "score": 81.0,
                        "max_score": 100,
                        "feedback": [],
                        "status": "success"
                    }
                },
                "detailed_results": {},
                "analysis_summary": "전체 점수: 85.50/100 | Pronunciation: 88.00/100 | Accent: 82.00/100"
            }
        }


class ASRAnalysisRequest(BaseModel):
    """음성 분석 요청 스키마"""
    reference_text: Optional[str] = Field(None, description="참조 텍스트 (선택사항)")
    language_code: str = Field(default="ko-KR", description="언어 코드 (ko-KR, en-US 등)")
    gender: str = Field(default="F", description="성별 (F, M)")

    class Config:
        json_schema_extra = {
            "example": {
                "reference_text": "안녕하세요. 승무원 음성 분석 테스트입니다.",
                "language_code": "ko-KR",
                "gender": "F"
            }
        }
