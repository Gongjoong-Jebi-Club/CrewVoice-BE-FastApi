"""
Baseline Management API Router
Baseline 생성 및 관리 엔드포인트
"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from app.services import BaselineManager

router = APIRouter()

# BaselineManager 인스턴스
baseline_manager = BaselineManager()


@router.post(
    "/generate",
    summary="Baseline 생성",
    description="""
    다수의 샘플 WAV 파일로부터 모든 에이전트의 baseline을 생성합니다.

    생성되는 baseline:
    - Speed: 평균 속도, 표준편차, 임계값
    - Intonation: 억양 특징 통계
    - Tone: 톤 특징 통계 (성별별, 언어별)
    - Accent: 향후 확장용

    최소 3개 이상의 샘플 파일을 업로드하는 것을 권장합니다.
    """
)
async def generate_baseline(
    files: List[UploadFile] = File(..., description="샘플 WAV 파일들 (최소 3개 권장)"),
    baseline_name: str = Form(default="default", description="Baseline 이름"),
    language_code: str = Form(default="ko-KR", description="언어 코드"),
    gender: str = Form(default="F", description="성별 (F, M)")
):
    """
    Baseline 생성

    Args:
        files: 샘플 WAV 파일 리스트
        baseline_name: Baseline 이름
        language_code: 언어 코드
        gender: 성별

    Returns:
        생성된 baseline 정보
    """
    # 파일 검증
    if len(files) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="최소 2개 이상의 WAV 파일이 필요합니다. (3개 이상 권장)"
        )

    # WAV 파일 검증
    for file in files:
        if not file.filename.lower().endswith('.wav'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"모든 파일은 WAV 형식이어야 합니다: {file.filename}"
            )

    # 임시 디렉토리 생성
    temp_dir = tempfile.mkdtemp()

    try:
        # 파일 저장
        sample_files = []
        for file in files:
            temp_file_path = os.path.join(temp_dir, file.filename)
            with open(temp_file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            sample_files.append(temp_file_path)

        # Baseline 생성
        results = baseline_manager.generate_all_baselines(
            sample_files=sample_files,
            baseline_name=baseline_name,
            language_code=language_code,
            gender=gender
        )

        # 성공 여부 확인
        success_count = sum(1 for v in results.values() if "status" not in v or v.get("status") != "failed")
        failed_count = len(results) - success_count

        return JSONResponse(
            status_code=status.HTTP_200_OK if success_count > 0 else status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": f"Baseline 생성 완료: 성공 {success_count}개, 실패 {failed_count}개",
                "baseline_name": baseline_name,
                "language_code": language_code,
                "gender": gender,
                "sample_count": len(sample_files),
                "results": results
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Baseline 생성 중 오류 발생: {str(e)}"
        )

    finally:
        # 임시 디렉토리 정리
        try:
            shutil.rmtree(temp_dir)
        except Exception as cleanup_error:
            print(f"임시 디렉토리 정리 실패: {cleanup_error}")


@router.get(
    "/list",
    summary="Baseline 목록 조회",
    description="생성된 모든 baseline의 목록을 조회합니다."
)
async def list_baselines():
    """
    Baseline 목록 조회

    Returns:
        에이전트별 baseline 이름 목록
    """
    try:
        baselines = baseline_manager.list_baselines()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "baselines": baselines,
                "total_count": sum(len(v) for v in baselines.values())
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Baseline 목록 조회 중 오류 발생: {str(e)}"
        )


@router.delete(
    "/delete",
    summary="Baseline 삭제",
    description="특정 에이전트의 baseline을 삭제합니다."
)
async def delete_baseline(
    agent: str = Form(..., description="에이전트 이름 (speed, intonation, tone, accent)"),
    baseline_name: str = Form(..., description="삭제할 baseline 이름")
):
    """
    Baseline 삭제

    Args:
        agent: 에이전트 이름
        baseline_name: Baseline 이름

    Returns:
        삭제 결과
    """
    # 에이전트 검증
    valid_agents = ["speed", "intonation", "tone", "accent"]
    if agent not in valid_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"올바른 에이전트 이름을 입력하세요: {', '.join(valid_agents)}"
        )

    try:
        success = baseline_manager.delete_baseline(agent, baseline_name)

        if success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Baseline 삭제 성공: {agent}_{baseline_name}",
                    "agent": agent,
                    "baseline_name": baseline_name
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Baseline을 찾을 수 없습니다: {agent}_{baseline_name}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Baseline 삭제 중 오류 발생: {str(e)}"
        )


@router.get(
    "/health",
    summary="Baseline 관리 헬스체크",
    description="Baseline 관리 시스템의 상태를 확인합니다."
)
async def health_check():
    """Baseline 관리 시스템 헬스체크"""
    baseline_dir = baseline_manager.baseline_dir

    return {
        "status": "ok",
        "module": "baseline_management",
        "baseline_directory": str(baseline_dir),
        "directory_exists": baseline_dir.exists(),
        "supported_agents": ["speed", "intonation", "tone", "accent"]
    }
