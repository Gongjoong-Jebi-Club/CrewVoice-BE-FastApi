"""
ASR Module API Router
음성 분석 API 엔드포인트
"""
import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Query
from fastapi.responses import JSONResponse

from app.agents import AgentManager
from app.agents.feedback_filter import FeedbackFilter
from app.schemas.asr_response import ASRAnalysisResponse

router = APIRouter()

# AgentManager 싱글톤 인스턴스
agent_manager = AgentManager()


@router.post(
    "/analyze",
    summary="음성 파일 분석",
    description="""
    WAV 파일을 업로드하여 종합 음성 분석을 수행합니다.

    6가지 분석 항목:
    - Pronunciation (발음): 정확도, 유창성, 완전성
    - Accent (강조): 에너지 및 피치 변화
    - Intonation (억양): 억양 패턴, 리듬 타입
    - Pause (휴지): 쉼의 위치 및 길이 적절성
    - Speed (속도): 발화 속도
    - Tone (톤): 음색, 안정성, 밝기

    각 항목은 100점 만점으로 평가됩니다.

    응답 형식:
    - full: 전체 상세 결과 (기본값)
    - filtered: 개선이 필요한 항목만 (80점 미만)
    - compact: 초간결 (전체 점수 + 개선 필요 항목만)
    """
)
async def analyze_speech(
    file: UploadFile = File(..., description="WAV 음성 파일"),
    reference_text: str = Form(None, description="참조 텍스트 (선택사항)"),
    language_code: str = Form(default="ko-KR", description="언어 코드 (ko-KR, en-US 등)"),
    gender: str = Form(default="F", description="성별 (F, M)"),
    response_format: str = Form(
        default="compact",
        description="응답 형식 (full: 전체, filtered: 개선필요항목, compact: 초간결)",
        regex="^(full|filtered|compact)$"
    )
):
    """
    음성 파일 업로드 및 분석

    Args:
        file: WAV 파일
        reference_text: 참조 텍스트
        language_code: 언어 코드
        gender: 성별
        response_format: 응답 형식 (full/filtered/compact)

    Returns:
        분석 결과 (형식에 따라 다름)
    """
    # 파일 형식 검증
    if not file.filename.lower().endswith('.wav'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WAV 파일만 업로드 가능합니다."
        )

    # 임시 파일로 저장
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)

    try:
        # 파일 저장
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 분석 수행
        result = await agent_manager.analyze_all(
            wav_path=temp_file_path,
            reference_text=reference_text,
            language_code=language_code,
            gender=gender
        )

        # 응답 형식에 따라 필터링
        if response_format == "compact":
            # 초간결: 전체 점수 + 개선 필요 항목만
            filtered_result = FeedbackFilter.get_compact_response(result)
        elif response_format == "filtered":
            # 필터링: 개선 필요 항목 + 전체 점수 정보
            filtered_result = FeedbackFilter.filter_response(result)
        else:  # full
            # 전체 결과 (기존)
            filtered_result = result

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=filtered_result
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"음성 분석 중 오류 발생: {str(e)}"
        )

    finally:
        # 임시 파일 정리
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except Exception as cleanup_error:
            print(f"임시 파일 정리 실패: {cleanup_error}")


@router.get(
    "/health",
    summary="ASR 모듈 헬스체크",
    description="ASR 분석 모듈의 상태를 확인합니다."
)
async def health_check():
    """ASR 모듈 헬스체크"""
    return {
        "status": "ok",
        "module": "asr_analysis",
        "agents": [
            "pronunciation",
            "accent",
            "intonation",
            "pause",
            "speed",
            "tone"
        ]
    }
