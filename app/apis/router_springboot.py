"""
Spring Boot 연동 API 라우터
비동기 음성 분석 및 콜백 처리
"""
import os
import httpx
import asyncio
import tempfile
import logging
import shutil
import struct
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.schemas.springboot_evaluation import (
    EvaluationRequest,
    EvaluationAcceptedResponse,
    ScoresPayload,
    CallbackSuccessPayload,
    CallbackFailurePayload
)
from app.agents.managers.analyzer_manager import SpeechAnalysisManager
from app.agents.utils.comment_generator import AICommentGenerator

# 로거 설정
logger = logging.getLogger("uvicorn")

# 라우터 생성
router = APIRouter()

# 전역 매니저 초기화 (기존 코드 재사용)
analyzer_manager = SpeechAnalysisManager()
comment_generator = AICommentGenerator()

# 🔍 디버그 모드 설정 (환경 변수)
DEBUG_SAVE_AUDIO = os.getenv("DEBUG_SAVE_AUDIO", "false").lower() == "true"
DEBUG_AUDIO_DIR = Path(__file__).parent.parent.parent / "debug_audio"

# 디버그 폴더 생성
if DEBUG_SAVE_AUDIO:
    DEBUG_AUDIO_DIR.mkdir(exist_ok=True)
    logger.info(f"🔍 디버그 모드 활성화: 오디오 파일 저장 위치 = {DEBUG_AUDIO_DIR}")


@router.post(
    "/evaluate",
    response_model=EvaluationAcceptedResponse,
    status_code=status.HTTP_200_OK,
    summary="Spring Boot 음성 평가 요청 (비동기)",
    description="""
    Spring Boot로부터 평가 요청을 받아 백그라운드 처리

    **처리 흐름:**
    1. 요청 검증 및 즉시 200 OK 응답 반환
    2. 백그라운드 작업 등록:
       - S3에서 WAV 다운로드
       - 음성 분석 실행 (6가지 지표)
       - AI 피드백 생성
       - Spring Boot 콜백 전송

    **Spring Boot 명세:**
    - 응답: HTTP 200 OK (202 아님!)
    - 처리 방식: Fire-and-Forget
    """
)
async def springboot_evaluate(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks
):
    """
    Spring Boot로부터 평가 요청 수신

    Args:
        request: Spring Boot에서 보낸 평가 요청 데이터
        background_tasks: FastAPI BackgroundTasks (자동 주입)

    Returns:
        즉시 200 OK 응답 (백그라운드 처리 계속)
    """

    # 요청 검증
    if not request.task_id:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": "필수 필드 누락: task_id"}
        )

    logger.info(f"[{request.task_id}] 평가 요청 접수")
    logger.info(f"[{request.task_id}] audio_url: {request.audio_url[:50]}...")
    logger.info(f"[{request.task_id}] language: {request.language}")

    # 백그라운드 작업 등록 (자동 실행 예약)
    background_tasks.add_task(
        process_evaluation_async,
        request=request
    )

    # 즉시 200 OK 응답 반환 (Spring Boot 명세)
    return EvaluationAcceptedResponse(
        message="Request received",
        task_id=request.task_id
    )


async def process_evaluation_async(request: EvaluationRequest):
    """
    백그라운드에서 실행되는 평가 로직

    **타임아웃:**
    - 전체 프로세스: 5분
    - S3 다운로드: 30초
    - 콜백 전송: 10초

    **에러 처리:**
    - 모든 에러는 자동으로 콜백 전송
    - Spring Boot는 항상 콜백을 받음

    Args:
        request: Spring Boot 요청 데이터
    """
    tmp_path = None

    try:
        logger.info(f"[{request.task_id}] 백그라운드 처리 시작")

        # 1. S3에서 WAV 다운로드 (30초 타임아웃)
        logger.info(f"[{request.task_id}] S3 다운로드 시작")
        tmp_path = await download_from_s3(request.audio_url, request.task_id, timeout=30)
        logger.info(f"[{request.task_id}] 다운로드 완료: {tmp_path}")

        # 2. 음성 분석 실행 (5분 타임아웃)
        logger.info(f"[{request.task_id}] 음성 분석 시작...")

        # 가중치 파라미터 추출 및 kwargs 구성
        kwargs = {
            "reference_text": request.script,
            "language_code": request.language
        }

        if request.weights:
            # WeightsConfig의 모든 필드를 kwargs에 추가
            weights_dict = request.weights.model_dump(exclude_none=True)
            kwargs.update(weights_dict)
            logger.info(f"[{request.task_id}] 커스텀 가중치 적용: {list(weights_dict.keys())}")

            # 각 평가요소별 가중치 로깅 (디버깅용)
            logger.info(f"[{request.task_id}] Tone 가중치: clarity={weights_dict.get('weight_clarity')}, stability={weights_dict.get('weight_stability')}, brightness={weights_dict.get('weight_brightness')}, pitch_position={weights_dict.get('weight_pitch_position')}")
            logger.info(f"[{request.task_id}] Pause 가중치: fluency={weights_dict.get('weight_fluency')}, position={weights_dict.get('weight_position')}, length={weights_dict.get('weight_length')}")
            logger.info(f"[{request.task_id}] Accent 가중치: pitch={weights_dict.get('weight_pitch')}, energy={weights_dict.get('weight_energy')}")
            logger.info(f"[{request.task_id}] Intonation 가중치: baseline={weights_dict.get('weight_baseline')}, iso={weights_dict.get('weight_iso')}")
            logger.info(f"[{request.task_id}] Speed 파라미터: deviation_threshold={weights_dict.get('deviation_threshold')}")
            logger.info(f"[{request.task_id}] 성별: gender={weights_dict.get('gender')}")
        else:
            logger.info(f"[{request.task_id}] 기본 가중치 사용")

        # asyncio.wait_for로 타임아웃 처리
        result = await asyncio.wait_for(
            asyncio.to_thread(
                analyzer_manager.analyze_parallel,
                wav_path=tmp_path,
                **kwargs  # 가중치 파라미터 전달
            ),
            timeout=300  # 5분
        )

        logger.info(f"[{request.task_id}] 음성 분석 완료")

        # 3. 점수 추출 (기존 코드 재사용)
        scores_dict = result.get("summary", {}).get("individual_scores", {})
        overall_score = result.get("summary", {}).get("average_score", 0.0)

        # 4. AI 피드백 생성 (기존 코드 재사용)
        logger.info(f"[{request.task_id}] AI 피드백 생성 시작...")
        agent_outputs = analyzer_manager.get_agent_outputs(result)
        validation_result = result.get("detailed_results", {}).get("validate", {})

        ai_comment_data = await asyncio.to_thread(
            comment_generator.generate_comment,
            agent_outputs,
            validation_result
        )

        feedback_summary = ai_comment_data.get("comment", "분석을 완료했습니다.")
        logger.info(f"[{request.task_id}] AI 피드백 생성 완료")

        # 5. 성공 콜백 페이로드 구성
        scores_payload = ScoresPayload(
            score_pronunciation=round(scores_dict.get("pronunciation", 0.0), 2),
            score_pause=round(scores_dict.get("pause", 0.0), 2),
            score_intonation=round(scores_dict.get("intonation", 0.0), 2),
            score_tone=round(scores_dict.get("tone", 0.0), 2),
            score_speed=round(scores_dict.get("speed", 0.0), 2),
            score_accent=round(scores_dict.get("accent", 0.0), 2),
            overall_score=round(overall_score, 2)
        )

        callback_payload = CallbackSuccessPayload(
            task_id=request.task_id,
            status="completed",
            scores=scores_payload,
            feedback_summary=feedback_summary[:500]  # 최대 500자
        )

        logger.info(f"[{request.task_id}] 평가 완료 - overall_score: {overall_score:.2f}")

        # 6. 성공 콜백 전송
        await send_callback(request.callback_url, callback_payload.model_dump(), request.task_id)

    except asyncio.TimeoutError:
        # 타임아웃 발생
        logger.error(f"[{request.task_id}] 평가 시간 초과 (5분)")

        failure_payload = CallbackFailurePayload(
            task_id=request.task_id,
            status="failed",
            error_message="평가 시간 초과 (5분)"
        )

        await send_callback(request.callback_url, failure_payload.model_dump(), request.task_id)

    except httpx.HTTPStatusError as e:
        # S3 다운로드 HTTP 오류 (403, 404 등)
        error_msg = f"S3 다운로드 실패: HTTP {e.response.status_code}"
        logger.error(f"[{request.task_id}] {error_msg}")

        failure_payload = CallbackFailurePayload(
            task_id=request.task_id,
            status="failed",
            error_message=error_msg
        )

        await send_callback(request.callback_url, failure_payload.model_dump(), request.task_id)

    except Exception as e:
        # 기타 모든 오류
        error_type = type(e).__name__
        error_msg = str(e)

        # 오류 메시지 분류
        if "403" in error_msg or "Forbidden" in error_msg:
            error_message = "S3 Pre-signed URL 만료됨 (403 Forbidden)"
        elif "404" in error_msg or "Not Found" in error_msg:
            error_message = "S3 파일을 찾을 수 없음 (404 Not Found)"
        elif "timeout" in error_msg.lower():
            error_message = "S3 다운로드 실패: 네트워크 타임아웃"
        elif "wav" in error_msg.lower() or "audio" in error_msg.lower():
            error_message = f"WAV 파일 처리 실패: {error_msg}"
        else:
            error_message = f"예상치 못한 오류: {error_type} - {error_msg}"

        logger.error(f"[{request.task_id}] 평가 실패: {error_message}")

        failure_payload = CallbackFailurePayload(
            task_id=request.task_id,
            status="failed",
            error_message=error_message
        )

        await send_callback(request.callback_url, failure_payload.model_dump(), request.task_id)

    finally:
        # 임시 파일 삭제 (자동 리소스 정리)
        # 로컬 파일인 경우 삭제 안 함 (audio_url과 tmp_path가 다른 경우만 삭제)
        if tmp_path and os.path.exists(tmp_path) and tmp_path != request.audio_url:
            try:
                os.remove(tmp_path)
                logger.info(f"[{request.task_id}] 임시 파일 삭제 완료")
            except Exception as e:
                logger.warning(f"[{request.task_id}] 임시 파일 삭제 실패: {e}")


async def download_from_s3(url: str, task_id: str, timeout: int = 30) -> str:
    """
    S3 Pre-signed URL에서 WAV 파일 다운로드

    로컬 테스트: audio_url이 로컬 파일 경로인 경우 다운로드 스킵
    - 예: "C:/test/audio.wav" 또는 "/tmp/audio.wav"

    Args:
        url: S3 Pre-signed URL 또는 로컬 파일 경로
        task_id: 작업 ID (로깅용)
        timeout: 다운로드 타임아웃 (초)

    Returns:
        임시 파일 경로

    Raises:
        HTTPException: 다운로드 실패 시
    """
    # 로컬 파일 경로인 경우 다운로드 스킵
    if os.path.exists(url):
        logger.info(f"[{task_id}] 로컬 파일 사용: {url}")
        return url

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()

            # Content-Type 검증 (선택사항)
            content_type = response.headers.get("content-type", "")
            if content_type and "audio" not in content_type.lower():
                logger.warning(f"[{task_id}] WARNING: Content-Type이 audio가 아님: {content_type}")

            # 임시 파일에 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name

            # 파일 크기 검증 (10MB 제한)
            file_size = os.path.getsize(tmp_path)
            if file_size > 50 * 1024 * 1024:  # 50MB
                os.remove(tmp_path)
                raise HTTPException(
                    status_code=400,
                    detail=f"파일 크기 초과: {file_size / (1024*1024):.2f}MB (최대 50MB)"
                )

            logger.info(f"[{task_id}] 다운로드 완료: {file_size / 1024:.2f}KB")

            # 🔍 WAV 파일 검증
            wav_info = validate_wav_file(tmp_path, task_id)
            if wav_info:
                logger.info(f"[{task_id}] WAV 검증 완료: {wav_info}")

            # 🔍 디버그 모드: 파일 영구 저장
            if DEBUG_SAVE_AUDIO:
                save_debug_audio(tmp_path, task_id)

            return tmp_path

        except httpx.HTTPStatusError as e:
            # HTTP 오류 (403, 404 등)
            logger.error(f"[{task_id}] S3 다운로드 실패: HTTP {e.response.status_code}")
            raise

        except httpx.TimeoutException:
            # 타임아웃
            logger.error(f"[{task_id}] S3 다운로드 타임아웃 ({timeout}초 초과)")
            raise HTTPException(
                status_code=504,
                detail=f"S3 다운로드 타임아웃 ({timeout}초 초과)"
            )

        except Exception as e:
            # 기타 오류
            logger.error(f"[{task_id}] S3 다운로드 실패: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"S3 다운로드 실패: {str(e)}"
            )


def validate_wav_file(file_path: str, task_id: str) -> dict:
    """
    WAV 파일 헤더 검증 및 정보 추출

    Args:
        file_path: WAV 파일 경로
        task_id: 작업 ID (로깅용)

    Returns:
        WAV 파일 정보 dict (채널, 샘플레이트, 비트레이트, 재생시간)
        검증 실패 시 None
    """
    try:
        with open(file_path, 'rb') as f:
            # RIFF 헤더 읽기
            riff = f.read(4)
            if riff != b'RIFF':
                logger.warning(f"[{task_id}] WAV 검증 실패: RIFF 헤더 없음")
                return None

            # 파일 크기
            file_size = struct.unpack('<I', f.read(4))[0]

            # WAVE 포맷
            wave = f.read(4)
            if wave != b'WAVE':
                logger.warning(f"[{task_id}] WAV 검증 실패: WAVE 포맷 아님")
                return None

            # fmt 청크 찾기
            while True:
                chunk_id = f.read(4)
                if not chunk_id:
                    break

                chunk_size = struct.unpack('<I', f.read(4))[0]

                if chunk_id == b'fmt ':
                    # fmt 청크 데이터 읽기
                    audio_format = struct.unpack('<H', f.read(2))[0]
                    num_channels = struct.unpack('<H', f.read(2))[0]
                    sample_rate = struct.unpack('<I', f.read(4))[0]
                    byte_rate = struct.unpack('<I', f.read(4))[0]
                    block_align = struct.unpack('<H', f.read(2))[0]
                    bits_per_sample = struct.unpack('<H', f.read(2))[0]

                    # 재생 시간 계산 (초)
                    duration = file_size / byte_rate if byte_rate > 0 else 0

                    return {
                        "channels": num_channels,
                        "sample_rate": sample_rate,
                        "bits_per_sample": bits_per_sample,
                        "duration": f"{duration:.2f}초",
                        "format": "PCM" if audio_format == 1 else f"포맷 {audio_format}"
                    }
                else:
                    # 다른 청크는 스킵
                    f.seek(chunk_size, 1)

        logger.warning(f"[{task_id}] WAV 검증 실패: fmt 청크 없음")
        return None

    except Exception as e:
        logger.warning(f"[{task_id}] WAV 검증 오류: {str(e)}")
        return None


def save_debug_audio(file_path: str, task_id: str):
    """
    디버그용 오디오 파일 영구 저장

    Args:
        file_path: 원본 임시 파일 경로
        task_id: 작업 ID
    """
    try:
        # 타임스탬프 포함 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_filename = f"{task_id}_{timestamp}.wav"
        debug_path = DEBUG_AUDIO_DIR / debug_filename

        # 파일 복사
        shutil.copy2(file_path, debug_path)

        file_size = os.path.getsize(debug_path)
        logger.info(
            f"[{task_id}] 🔍 디버그 파일 저장 완료: {debug_path} ({file_size / 1024:.2f}KB)"
        )

    except Exception as e:
        logger.error(f"[{task_id}] 디버그 파일 저장 실패: {str(e)}")


async def send_callback(callback_url: str, payload: dict, task_id: str):
    """
    Spring Boot로 콜백 전송

    Args:
        callback_url: Spring Boot 콜백 URL
        payload: 전송할 데이터 (성공 또는 실패 페이로드)
        task_id: 작업 ID (로깅용)

    Note:
        - 타임아웃: 10초
        - 재시도: 없음 (한 번만 전송)
        - 실패 시: 로그만 기록
        - 인증: X-API-Key 헤더 포함
    """
    # 환경 변수에서 API Key 읽기
    api_key = os.getenv("CALLBACK_API_KEY", "")

    # 요청 헤더 설정
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            logger.info(f"[{task_id}] 콜백 전송 시작: {callback_url}")

            response = await client.post(callback_url, json=payload, headers=headers)
            response.raise_for_status()

            logger.info(f"[{task_id}] 콜백 전송 완료: HTTP {response.status_code}")

        except httpx.HTTPStatusError as e:
            # Spring Boot가 4xx/5xx 응답을 반환한 경우
            logger.error(f"[{task_id}] 콜백 전송 실패 (HTTP {e.response.status_code}): {e.response.text}")

        except httpx.TimeoutException:
            # 타임아웃 (10초)
            logger.error(f"[{task_id}] 콜백 전송 타임아웃 (10초 초과)")

        except Exception as e:
            # 기타 오류
            logger.error(f"[{task_id}] 콜백 전송 오류: {str(e)}")
