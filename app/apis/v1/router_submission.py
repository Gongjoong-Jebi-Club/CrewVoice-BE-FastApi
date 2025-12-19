"""
음성 제출 API 라우터
"""
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, HTTPException
from typing import Annotated

from app.schemas.submission import (
    SubmissionRequest,
    SubmissionResponse,
    SubmissionData,
    ErrorResponse
)
from app.services.submission_service import submission_service, run_ai_analysis


router = APIRouter()


@router.post(
    "/analysis/submit/test",
    response_model=SubmissionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "파일 형식 오류"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    },
    summary="음성 평가 제출 (테스트용)",
    description="""
    음성 분석 로직을 테스트하기 위한 독립적인 API입니다.
    (Spring Boot와 연동 없이 독립적으로 동작)

    - 파일은 즉시 저장되고, 응답이 반환됩니다
    - AI 분석(STT, 발음 평가 등)은 백그라운드에서 비동기로 처리됩니다
    - 분석 결과는 별도의 조회 API를 통해 확인할 수 있습니다
    """
)
async def submit_voice_evaluation(
    background_tasks: BackgroundTasks,
    # 파일 (multipart/form-data)
    file: Annotated[UploadFile, File(description="음성 파일 (.webm, .wav 등)")],
    # Form 데이터
    user_id: Annotated[int, Form(description="사용자 ID")],
    evaluation_id: Annotated[int, Form(description="평가 세션 ID")],
    step: Annotated[str, Form(description="평가 단계 (예: STEP2, STEP3)")],
    question_index: Annotated[int, Form(ge=0, description="문제 번호 (0부터 시작)")],
    language: Annotated[str, Form(description="언어 코드 (kor 또는 eng)")],
    # TODO: Authorization 헤더에서 토큰 추출 및 검증
    # authorization: str = Header(None)
) -> SubmissionResponse:
    """
    음성 파일 제출 및 분석 요청

    **처리 흐름:**
    1. 파일 유효성 검증 (MIME 타입, 확장자)
    2. 파일을 로컬 temp/ 디렉토리에 저장
    3. DB에 제출 기록 생성 (submission_id 발급)
    4. 백그라운드 작업으로 AI 분석 등록
    5. 즉시 응답 반환 (submission_id 포함)

    **백그라운드 작업:**
    - STT (Speech-to-Text)
    - 발음 평가 (Pronunciation)
    - 억양 분석 (Intonation)
    - 속도 분석 (Speed)
    - 감정/톤 분석 (Tone)
    - 종합 피드백 생성 및 DB 저장
    """

    # TODO: Authorization 헤더 검증 (JWT 토큰)
    # if not authorization or not authorization.startswith("Bearer "):
    #     raise HTTPException(status_code=401, detail="인증 토큰이 필요합니다")
    # token = authorization.split(" ")[1]
    # decoded_user = verify_token(token)  # JWT 검증 함수 필요

    try:
        # 1. 요청 데이터 구성
        request = SubmissionRequest(
            user_id=user_id,
            evaluation_id=evaluation_id,
            step=step,
            question_index=question_index,
            language=language
        )

        print(f"\n[API] 음성 제출 요청 수신:")
        print(f"  - user_id: {request.user_id}")
        print(f"  - evaluation_id: {request.evaluation_id}")
        print(f"  - step: {request.step}")
        print(f"  - question_index: {request.question_index}")
        print(f"  - language: {request.language}")
        print(f"  - filename: {file.filename}")
        print(f"  - content_type: {file.content_type}")

        # 2. 파일 유효성 검증
        submission_service.validate_audio_file(file)

        # 3. 파일 저장
        file_path = await submission_service.save_audio_file(file, request)

        # 4. DB 기록 생성
        submission_id = submission_service.create_submission_record(request, file_path)

        # 5. 백그라운드 작업 등록 (AI 분석)
        background_tasks.add_task(
            run_ai_analysis,
            submission_id=submission_id,
            file_path=file_path,
            request=request
        )

        print(f"[API] 백그라운드 작업 등록 완료 (submission_id={submission_id})")

        # 6. 즉시 응답 반환
        return SubmissionResponse(
            code=200,
            message="제출 성공",
            data=SubmissionData(submission_id=submission_id)
        )

    except HTTPException:
        # HTTPException은 그대로 전파
        raise

    except Exception as e:
        # 예상치 못한 에러 처리
        print(f"[API] 에러 발생: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": 500,
                "message": "서버 내부 오류",
                "detail": str(e)
            }
        )


# @router.get(
#     "/analysis/status/{submission_id}",
#     summary="분석 상태 조회 (TODO)",
#     description="제출한 음성의 분석 진행 상태를 조회합니다 (미구현)"
# )
# async def get_analysis_status(submission_id: int):
#     """
#     분석 상태 조회 API (향후 구현 예정)

#     **응답 예시:**
#     ```json
#     {
#         "submission_id": 105,
#         "status": "completed",  // pending, processing, completed, failed
#         "progress": 100,
#         "result": { ... }
#     }
#     ```
#     """
#     # TODO: DB에서 submission_id로 상태 조회
#     return {
#         "submission_id": submission_id,
#         "status": "processing",
#         "progress": 50,
#         "message": "아직 구현되지 않은 API입니다"
#     }
