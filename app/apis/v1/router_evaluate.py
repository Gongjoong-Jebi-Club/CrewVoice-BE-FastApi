import os
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, Form, HTTPException, BackgroundTasks

from app.schemas.evaluation import EvaluationResponse
from app.agents.managers.analyzer_manager import SpeechAnalysisManager
from app.agents.utils.comment_generator import AICommentGenerator

router = APIRouter()

# 전역 매니저 초기화 (비용이 큰 객체 재사용)
analyzer_manager = SpeechAnalysisManager()
comment_generator = AICommentGenerator()

@router.post("/evaluate",
    response_model=EvaluationResponse,
    summary="음성 평가 API (즉시 응답)",
    description="""
    클라이언트가 직접 호출하는 음성 평가 API입니다.

    **특징**:
    - 음성 파일 업로드 → 분석 → 즉시 결과 반환 (동기 처리)
    - Spring Boot 없이 독립적으로 사용 가능
    - 프론트엔드 직접 호출, 외부 API 연동에 적합

    **반환 데이터**:
    - 6가지 평가 지표 점수 (발음, 휴지, 억양, 톤, 속도, 강조)
    - AI 생성 피드백
    """
)
async def evaluate_speech(
    audio_file: UploadFile,
    script_id: int = Form(...),
    user_id: str = Form(...),
    reference_text: str = Form(..., description="분석할 스크립트 텍스트"),
    background_tasks: BackgroundTasks = None
):
    """
    음성 파일을 분석하여 6가지 지표 점수와 피드백을 즉시 반환합니다.
    (Spring Boot 없이 독립적으로 동작하는 직접 호출용 API)
    """
    
    # 1. 파일 유효성 검사
    if not audio_file.filename.endswith(('.wav', '.mp3', '.m4a')):
        raise HTTPException(status_code=400, detail="지원하지 않는 오디오 형식입니다.")

    # 2. 임시 파일 저장
    # Windows/Linux 호환성을 위해 tempfile 사용
    suffix = Path(audio_file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(audio_file.file, tmp)
        tmp_path = tmp.name

    try:
        # 3. 음성 분석 실행 (병렬 처리)
        # analyzer_manager.analyze_parallel은 내부적으로 ThreadPoolExecutor 사용
        result = analyzer_manager.analyze_parallel(
            wav_path=tmp_path,
            reference_text=reference_text,
            language_code="ko-KR"  # 기본값 한국어
        )

        # 4. 에이전트별 점수 추출
        # analyze_parallel 결과 구조:
        # { "summary": { "individual_scores": { "accent": 80, ... } }, "detailed_results": { ... } }
        
        scores = result.get("summary", {}).get("individual_scores", {})
        detailed_results = result.get("detailed_results", {})
        
        # 5. AI 코멘트 생성
        agent_outputs = analyzer_manager.get_agent_outputs(result)
        validation_result = detailed_results.get("validate", {})
        
        ai_comment_data = comment_generator.generate_comment(agent_outputs, validation_result)
        feedback_summary = ai_comment_data.get("comment", "분석을 완료했습니다.")

        # 6. 응답 객체 매핑
        response = EvaluationResponse(
            score_pronunciation=scores.get("pronunciation", 0.0),
            score_pause=scores.get("pause", 0.0),
            score_intonation=scores.get("intonation", 0.0),
            score_tone=scores.get("tone", 0.0),
            score_speed=scores.get("speed", 0.0),
            score_accent=scores.get("accent", 0.0),
            overall_score=result.get("summary", {}).get("average_score", 0.0),
            feedback_summary=feedback_summary,
            eval_id=f"eval-{user_id}-{script_id}" # 임시 ID 생성
        )
        
        return response

    except Exception as e:
        # 로그 기록
        print(f"Analysis Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")

    finally:
        # 7. 임시 파일 삭제 (BackgroundTasks로 처리 권장하지만 여기선 finally로 즉시 처리)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
