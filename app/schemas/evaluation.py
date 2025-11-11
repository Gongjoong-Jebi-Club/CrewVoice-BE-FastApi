from pydantic import BaseModel
from typing import List, Optional

# Python이 Spring Boot로 반환할 JSON 형식
class EvaluationResponse(BaseModel):
    eval_id: str
    pron_accuracy: float
    speed_wpm: float
    feedback_summary: str
    error_words: Optional[List[str]] = None