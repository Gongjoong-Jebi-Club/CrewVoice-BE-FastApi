"""
음성 제출 관련 비즈니스 로직
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile, HTTPException
from app.schemas.submission import SubmissionRequest


class SubmissionService:
    """음성 제출 서비스"""

    def __init__(self, temp_dir: str = "temp"):
        """
        Args:
            temp_dir: 임시 파일 저장 디렉토리
        """
        self.temp_dir = Path(temp_dir)
        self._ensure_temp_dir()

    def _ensure_temp_dir(self) -> None:
        """임시 디렉토리가 없으면 생성"""
        if not self.temp_dir.exists():
            self.temp_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_audio_file(file: UploadFile) -> None:
        """
        오디오 파일 유효성 검증

        Args:
            file: 업로드된 파일

        Raises:
            HTTPException: 유효하지 않은 파일인 경우
        """
        # 1. MIME 타입 검증
        if not file.content_type or not file.content_type.startswith("audio/"):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": 400,
                    "message": "파일 형식 오류",
                    "detail": f"오디오 파일만 업로드 가능합니다. (현재: {file.content_type})"
                }
            )

        # 2. 파일 확장자 검증 (추가 보안)
        allowed_extensions = {".webm", ".wav", ".mp3", ".ogg", ".m4a"}
        file_extension = Path(file.filename or "").suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": 400,
                    "message": "파일 확장자 오류",
                    "detail": f"지원하는 확장자: {', '.join(allowed_extensions)}"
                }
            )

    async def save_audio_file(
        self,
        file: UploadFile,
        request: SubmissionRequest
    ) -> str:
        """
        오디오 파일을 로컬에 저장

        Args:
            file: 업로드된 파일
            request: 제출 요청 정보

        Returns:
            저장된 파일 경로
        """
        # 파일명 생성: {user_id}_{evaluation_id}_{step}_{question_index}_{timestamp}.{ext}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = Path(file.filename or "audio.webm").suffix

        filename = (
            f"{request.user_id}_"
            f"{request.evaluation_id}_"
            f"{request.step}_"
            f"Q{request.question_index}_"
            f"{timestamp}{file_extension}"
        )

        file_path = self.temp_dir / filename

        # 비동기로 파일 저장
        try:
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            print(f"[SubmissionService] 파일 저장 완료: {file_path}")
            return str(file_path)

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": 500,
                    "message": "파일 저장 실패",
                    "detail": str(e)
                }
            )

    def create_submission_record(
        self,
        request: SubmissionRequest,
        file_path: str
    ) -> int:
        """
        DB에 제출 기록 생성 (현재는 Mock)

        Args:
            request: 제출 요청 정보
            file_path: 저장된 파일 경로

        Returns:
            생성된 submission_id
        """
        # TODO: 실제 DB 연동 시 여기서 INSERT 쿼리 실행
        # 현재는 Mock ID 반환
        mock_submission_id = hash(file_path) % 10000

        print(f"[SubmissionService] DB 기록 생성 (Mock): submission_id={mock_submission_id}")
        print(f"  - user_id: {request.user_id}")
        print(f"  - evaluation_id: {request.evaluation_id}")
        print(f"  - step: {request.step}")
        print(f"  - question_index: {request.question_index}")
        print(f"  - language: {request.language}")
        print(f"  - file_path: {file_path}")

        return mock_submission_id


# ============================================================================
# 백그라운드 처리 함수
# ============================================================================

# async def run_ai_analysis(
#     submission_id: int,
#     file_path: str,
#     request: SubmissionRequest
# ) -> None:
#     """
#     AI 분석 백그라운드 작업 (현재는 Mock)

#     실제 환경에서는:
#     1. STT (Speech-to-Text) 변환
#     2. 발음 평가 (Pronunciation)
#     3. 억양 분석 (Intonation)
#     4. 속도 분석 (Speed)
#     5. 감정/톤 분석 (Tone)
#     6. 종합 피드백 생성
#     7. DB 결과 저장

#     Args:
#         submission_id: 제출 ID
#         file_path: 오디오 파일 경로
#         request: 제출 요청 정보
#     """
#     print("\n" + "="*80)
#     print(f"[BackgroundTask] AI 분석 시작")
#     print(f"  - submission_id: {submission_id}")
#     print(f"  - file_path: {file_path}")
#     print(f"  - language: {request.language}")
#     print(f"  - step: {request.step}")
#     print("="*80)

#     try:
#         # Mock: 5초간 분석 수행 (실제로는 STT, 발음 평가 등 수행)
#         print("[BackgroundTask] STT 변환 중...")
#         await asyncio.sleep(1)

#         print("[BackgroundTask] 발음 평가 중...")
#         await asyncio.sleep(1)

#         print("[BackgroundTask] 억양 분석 중...")
#         await asyncio.sleep(1)

#         print("[BackgroundTask] 속도 분석 중...")
#         await asyncio.sleep(1)

#         print("[BackgroundTask] 종합 피드백 생성 중...")
#         await asyncio.sleep(1)

#         # TODO: 실제 환경에서는 분석 결과를 DB에 저장
#         print(f"[BackgroundTask] 분석 완료! (submission_id={submission_id})")
#         print(f"[BackgroundTask] 결과를 DB에 저장해야 함 (현재는 Mock)")

#     except Exception as e:
#         print(f"[BackgroundTask] 에러 발생: {e}")
#         # TODO: 에러 로깅 및 DB 상태 업데이트
#         raise

#     finally:
#         print("="*80 + "\n")


# 싱글톤 인스턴스
submission_service = SubmissionService()
