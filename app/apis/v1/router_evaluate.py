from fastapi import APIRouter, UploadFile, Form
from app.schemas.evaluation import EvaluationResponse  # (코드 2)에서 정의

router = APIRouter()

@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_speech(
    # Spring Boot가 보낼 데이터 (multipart/form-data)
    audio_file: UploadFile,
    script_id: int = Form(...),
    user_id: str = Form(...)
):
    """
    [최소 기능] Spring Boot로부터 데이터를 받고, '임시(Mock)' JSON을 반환합니다.
    """
    
    # (AI 분석 로직은 아직 없음)
    print(f"FastAPI 수신 성공: User {user_id}, Script {script_id}, File: {audio_file.filename}")
    
    # Spring Boot로 보낼 '가짜' 응답 데이터
    return EvaluationResponse(
        eval_id="mock-eval-999",
        pron_accuracy=85.0,
        speed_wpm=140.0,
        feedback_summary="[Mock] FastAPI 서버 연동 테스트 성공",
        error_words=["test", "mock"]
    )