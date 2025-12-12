"""
Validate Analysis Agent
스크립트와 입력 음성의 내용 일치 검증
Azure Pronunciation Assessment를 사용하여 데이터 생성
Pronunciation과 Pause 에이전트에서 재사용 가능

검증 항목:
- Completeness: 스크립트 단어를 얼마나 말했는가 (중복 포함, 90% 이상 필요)
- Text Similarity: 스크립트와 얼마나 일치하는가 (SequenceMatcher 기반, 90% 이상 필요)
- 발음 품질은 검증하지 않음 (Pronunciation 에이전트에서 별도 평가)

Note:
- Completeness는 중복된 단어도 각각 카운트 (예: "안녕 안녕" → 2개 단어)
- Azure의 Completeness는 참고용으로만 보존 (azure_completeness_score)
"""
import os
import json
import threading
import logging
from typing import Dict, Tuple
from pathlib import Path
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
from difflib import SequenceMatcher

# .env 파일 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger("uvicorn")


class ValidateAnalyzer:
    """스크립트 검증 분석기"""

    # 검증 임계값 (내용 일치 여부만 검증, 발음은 Pronunciation 에이전트에서 평가)
    COMPLETENESS_THRESHOLD = 90.0  # 완전성 임계값 (스크립트의 90% 이상 말해야 통과)
    SIMILARITY_THRESHOLD = 0.9     # 텍스트 유사도 임계값 (90% 이상 일치해야 통과)

    def __init__(self):
        # SPEECH_KEY 또는 AZURE_SPEECH_KEY 지원
        self.speech_key = os.getenv("SPEECH_KEY") or os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = os.getenv("SPEECH_REGION") or os.getenv("AZURE_SPEECH_REGION")

        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech API Key 또는 Region이 설정되지 않았습니다.")

    def assess_pronunciation_for_validation(
        self,
        audio_file: str,
        reference_text: str,
        language_code: str = "ko-KR"
    ) -> Tuple[Dict, Dict]:
        """
        Azure Pronunciation Assessment를 사용하여 검증 데이터 생성

        Args:
            audio_file: 음성 파일 경로
            reference_text: 참조 텍스트 (스크립트)
            language_code: 언어 코드 (ko-KR 또는 en-US)

        Returns:
            (validation_result, azure_data) 튜플
            - validation_result: 검증 결과 딕셔너리
            - azure_data: Pronunciation/Pause 에이전트용 Azure 원본 데이터
        """
        # Speech-to-Text 설정
        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
        speech_config.speech_recognition_language = language_code

        # 오디오 입력 설정
        audio_config = speechsdk.audio.AudioConfig(filename=audio_file)

        # 발음 평가 설정
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
            enable_miscue="True"
        )

        # SpeechRecognizer 생성
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        # 발음 평가 설정 적용
        pronunciation_config.apply_to(speech_recognizer)

        # 연속 인식 설정
        done = threading.Event()
        all_json_results = []
        all_pron_scores = []
        recognized_text_parts = []

        def recognized_cb(evt):
            """음성이 성공적으로 인식되었을 때 호출"""
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                recognized_text = evt.result.text
                recognized_text_parts.append(recognized_text)

                # 🔍 디버깅: 전사된 텍스트 로깅
                logger.info(f"[VALIDATE] Azure STT 전사 (청크 {len(recognized_text_parts)}): '{recognized_text}'")

                json_result = json.loads(evt.result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
                all_json_results.append(json_result)
                pron_result = speechsdk.PronunciationAssessmentResult(evt.result)
                all_pron_scores.append(pron_result)

        def session_stopped_cb(evt):
            """세션 종료"""
            logger.info(f"[VALIDATE] Azure STT 세션 종료 (전체 청크 수: {len(recognized_text_parts)})")
            done.set()

        def canceled_cb(evt):
            """취소 이벤트"""
            logger.error(f"[VALIDATE] Azure STT 취소됨!")

            # 에러 상세 출력
            if hasattr(evt, 'error_details') and evt.error_details:
                logger.error(f"[VALIDATE] 에러 상세: {evt.error_details}")
            else:
                logger.error(f"[VALIDATE] 에러 상세: (없음)")

            # 취소 사유 출력 (result.reason을 통해 접근)
            if hasattr(evt, 'result') and evt.result:
                if hasattr(evt.result, 'cancellation_details'):
                    details = evt.result.cancellation_details
                    logger.error(f"[VALIDATE] 취소 사유: {details.reason}")
                    if hasattr(details, 'error_details') and details.error_details:
                        logger.error(f"[VALIDATE] 취소 에러 상세: {details.error_details}")
                    if hasattr(details, 'error_code'):
                        logger.error(f"[VALIDATE] 에러 코드: {details.error_code}")
                else:
                    logger.error(f"[VALIDATE] 취소 사유: (cancellation_details 없음)")
            else:
                logger.error(f"[VALIDATE] 취소 사유: (result 없음)")

            done.set()

        # 이벤트 핸들러 연결
        speech_recognizer.recognized.connect(recognized_cb)
        speech_recognizer.session_stopped.connect(session_stopped_cb)
        speech_recognizer.canceled.connect(canceled_cb)

        # 🔍 Azure STT 시작 로깅
        logger.info(f"[VALIDATE] Azure STT 시작 - 파일: {audio_file}, 언어: {language_code}")
        logger.info(f"[VALIDATE] 참조 텍스트: '{reference_text[:100]}...'")

        # 연속 인식 시작
        speech_recognizer.start_continuous_recognition_async()

        # ⚠️ 타임아웃 추가 (3분)
        timeout_seconds = 180
        if not done.wait(timeout=timeout_seconds):
            # 타임아웃 발생
            logger.error(f"[VALIDATE] Azure STT 타임아웃 ({timeout_seconds}초 초과)!")
            speech_recognizer.stop_continuous_recognition_async()
            return {
                "is_valid": False,
                "error": f"Azure STT 처리 시간 초과 ({timeout_seconds}초)",
                "feedback": ["음성 인식 타임아웃"],
                "status": "error"
            }, None

        speech_recognizer.stop_continuous_recognition_async()

        # ⚠️ 중요: 객체 명시적 삭제로 파일 잠금 해제 (Windows [WinError 32] 해결)
        del speech_recognizer
        del audio_config

        # 결과 처리
        if not all_pron_scores:
            logger.warning(f"[VALIDATE] Azure STT 결과 없음 (all_pron_scores 비어있음)")
            return {
                "is_valid": False,
                "error": "음성을 인식할 수 없거나 처리 중 오류가 발생했습니다.",
                "feedback": ["음성 인식 실패"],
                "status": "error"
            }, None

        # 전체 인식된 텍스트
        full_recognized_text = " ".join(recognized_text_parts)

        # 🔍 최종 전사 결과 로깅
        logger.info(f"[VALIDATE] 전체 전사 텍스트: '{full_recognized_text}'")
        logger.info(f"[VALIDATE] 참조 텍스트: '{reference_text}'")

        # 점수 계산 (가중 평균)
        total_duration_ticks = sum(res.get('Duration', 0) for res in all_json_results)

        if total_duration_ticks == 0:
            return {
                "is_valid": False,
                "error": "오디오 지속 시간을 계산할 수 없습니다.",
                "feedback": ["오디오 지속 실패"],
                "status": "error"
            }, None

        # 가중 평균 계산
        weighted_pron_score = sum(
            res.pronunciation_score * j_res.get('Duration', 0)
            for res, j_res in zip(all_pron_scores, all_json_results)
        ) / total_duration_ticks

        weighted_accuracy_score = sum(
            res.accuracy_score * j_res.get('Duration', 0)
            for res, j_res in zip(all_pron_scores, all_json_results)
        ) / total_duration_ticks

        weighted_fluency_score = sum(
            res.fluency_score * j_res.get('Duration', 0)
            for res, j_res in zip(all_pron_scores, all_json_results)
        ) / total_duration_ticks

        weighted_completeness_score = sum(
            res.completeness_score * j_res.get('Duration', 0)
            for res, j_res in zip(all_pron_scores, all_json_results)
        ) / total_duration_ticks

        # Azure 원본 JSON 데이터 병합 (Pronunciation/Pause 에이전트용)
        merged_azure_data = None
        if all_json_results:
            merged_azure_data = all_json_results[0].copy()

            # 여러 결과가 있으면 NBest의 Words 병합
            if len(all_json_results) > 1 and 'NBest' in merged_azure_data:
                all_words = []
                for result in all_json_results:
                    if 'NBest' in result and len(result['NBest']) > 0:
                        words = result['NBest'][0].get('Words', [])
                        all_words.extend(words)

                if all_words:
                    merged_azure_data['NBest'][0]['Words'] = all_words

        # 텍스트 유사도 계산
        text_similarity = self._calculate_text_similarity(reference_text, full_recognized_text)

        # 단어 기반 Completeness 재계산
        custom_completeness = self._calculate_word_completeness(reference_text, full_recognized_text)

        # 내용 검증 실시 (발음은 검증하지 않음)
        validation_result = self._validate_speech(
            reference_text=reference_text,
            recognized_text=full_recognized_text,
            completeness_score=custom_completeness,  # 우리가 계산한 completeness 사용
            text_similarity=text_similarity
        )

        # 검증 결과에 점수 정보 추가 (Pronunciation 에이전트용)
        validation_result.update({
            "recognized_text": full_recognized_text,
            "reference_text": reference_text,
            "accuracy_score": round(weighted_accuracy_score, 2),
            "fluency_score": round(weighted_fluency_score, 2),
            "completeness_score": round(custom_completeness, 2),  # 우리가 계산한 completeness
            "azure_completeness_score": round(weighted_completeness_score, 2),  # Azure 원본 보존
            "pronunciation_score": round(weighted_pron_score, 2),
            "text_similarity": round(text_similarity * 100, 2),
        })

        return validation_result, merged_azure_data

    def _normalize_text(self, text: str) -> str:
        """
        텍스트 정규화 (비교를 위해)

        Args:
            text: 원본 텍스트

        Returns:
            정규화된 텍스트
        """
        # 소문자 변환
        text = text.lower()

        # 공백 정규화 (연속된 공백을 하나로)
        text = " ".join(text.split())

        # 구두점 제거
        punctuation = '.,!?;:\'"()[]{}~-'
        for char in punctuation:
            text = text.replace(char, '')

        return text.strip()

    def _calculate_word_completeness(self, reference_text: str, recognized_text: str) -> float:
        """
        단어 매칭 기반 Completeness 계산 (중복 포함)

        Args:
            reference_text: 참조 텍스트 (스크립트)
            recognized_text: 인식된 텍스트

        Returns:
            Completeness 점수 (0.0 ~ 100.0)
        """
        # 정규화 후 단어로 분리 (리스트로 유지하여 중복 보존)
        ref_normalized = self._normalize_text(reference_text)
        rec_normalized = self._normalize_text(recognized_text)

        if not ref_normalized:
            return 0.0

        # 단어 리스트 생성 (중복 포함)
        ref_words = ref_normalized.split()
        rec_words = rec_normalized.split()

        if not ref_words:
            return 0.0

        # reference_text의 각 단어가 recognized_text에 있는지 확인
        matched_count = 0
        rec_words_remaining = rec_words.copy()  # 매칭된 단어는 제거하기 위한 복사본

        for ref_word in ref_words:
            if ref_word in rec_words_remaining:
                matched_count += 1
                rec_words_remaining.remove(ref_word)  # 한 번 매칭된 단어는 제거

        completeness = (matched_count / len(ref_words)) * 100.0

        return completeness

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """두 텍스트의 유사도 계산 (0.0 ~ 1.0)"""
        # 정규화
        text1_clean = self._normalize_text(text1)
        text2_clean = self._normalize_text(text2)

        if not text1_clean or not text2_clean:
            return 0.0

        return SequenceMatcher(None, text1_clean, text2_clean).ratio()

    def _validate_speech(
        self,
        reference_text: str,
        recognized_text: str,
        completeness_score: float,
        text_similarity: float
    ) -> Dict:
        """
        음성 내용 검증 실시 (발음은 검증하지 않음)

        적합 조건: Completeness >= 90% AND Similarity >= 90%

        Returns:
            검증 결과 딕셔너리 (is_valid, warnings, feedback)
        """
        is_valid = True
        warnings = []
        feedback = []

        # 디버깅: 실제 값 출력
        print(f"\n[VALIDATE DEBUG]")
        print(f"Reference: {reference_text[:50]}...")
        print(f"Recognized: {recognized_text[:50]}...")
        print(f"Completeness (Word-based): {completeness_score:.2f}%")
        print(f"Similarity (SequenceMatcher): {text_similarity*100:.2f}%")

        # 1. 완전성 검사 (스크립트를 얼마나 말했나)
        if completeness_score < self.COMPLETENESS_THRESHOLD:
            is_valid = False  # 임계값 미만이면 무조건 부적합
            warnings.append("completeness")

        # 2. 텍스트 유사도 검사 (스크립트와 다른 내용을 말했나)
        if text_similarity < self.SIMILARITY_THRESHOLD:
            is_valid = False  # 임계값 미만이면 무조건 부적합
            warnings.append("text_mismatch")

        # 3. 인식된 텍스트가 비어있는 경우
        if not recognized_text.strip():
            is_valid = False
            warnings.append("no_speech")
            feedback.append("음성 인식 실패")
        else:
            # 음성 인식이 성공한 경우, 항상 두 점수를 모두 표시 (적합/부적합 여부와 관계없이)
            # Completeness 피드백
            if completeness_score >= self.COMPLETENESS_THRESHOLD:
                completeness_feedback = f"문장 재현율: {completeness_score:.1f}% (기준: {self.COMPLETENESS_THRESHOLD}% 이상)"
            else:
                completeness_feedback = f"문장 재현율: {completeness_score:.1f}% (기준: {self.COMPLETENESS_THRESHOLD}% 미만)"
            feedback.append(completeness_feedback)

            # Similarity 피드백
            if text_similarity >= self.SIMILARITY_THRESHOLD:
                similarity_feedback = f"내용 일치도: {text_similarity*100:.1f}% (기준: {self.SIMILARITY_THRESHOLD*100}% 이상)"
            else:
                similarity_feedback = f"내용 일치도: {text_similarity*100:.1f}% (기준: {self.SIMILARITY_THRESHOLD*100}% 미만)"
            feedback.append(similarity_feedback)

        return {
            "is_valid": is_valid,
            "warnings": warnings,
            "feedback": feedback,
            "status": "success" if is_valid else "warning"
        }

    def analyze(
        self,
        wav_path: str,
        reference_text: str = None,
        language_code: str = "ko-KR"
    ) -> Dict:
        """
        음성 검증 분석 실시

        Args:
            wav_path: WAV 파일 경로
            reference_text: 참조 텍스트 (스크립트) - 필수
            language_code: 언어 코드

        Returns:
            검증 결과 + Azure 데이터
        """
        try:
            if not reference_text:
                return {
                    "is_valid": False,
                    "error": "참조 텍스트가 필요합니다.",
                    "feedback": ["스크립트를 입력하세요."],
                    "status": "error",
                    "azure_data": None
                }

            # Azure Pronunciation Assessment 수행 및 검증
            validation_result, azure_data = self.assess_pronunciation_for_validation(
                wav_path,
                reference_text,
                language_code
            )

            # azure_data 필드에 추가
            validation_result["azure_data"] = azure_data

            return validation_result

        except Exception as e:
            return {
                "is_valid": False,
                "error": f"검증 중 오류 발생: {str(e)}",
                "feedback": [f"시스템 오류: {str(e)}"],
                "status": "error",
                "azure_data": None
            }