from pydantic import BaseModel
from typing import Optional

class EvaluationResponse(BaseModel):
    """
    Spring Boot 서버로 반환할 평가 결과
    DB 테이블 컬럼(score_*)과 1:1 매핑
    """
    score_pronunciation: float
    score_pause: float
    score_intonation: float
    score_tone: float
    score_speed: float
    score_accent: float
    overall_score: float
    feedback_summary: str
    
    # 선택적 메타데이터
    eval_id: Optional[str] = None
