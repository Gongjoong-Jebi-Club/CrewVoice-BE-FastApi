"""
Pronunciation Analysis Agent
음성 파일의 발음(Pronunciation) 분석을 수행하는 에이전트
Azure Speech API를 사용합니다.
"""
import os
import json
import threading
from typing import Dict
from pathlib import Path
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

# .env 파일 로드
load_dotenv()


class PronunciationAnalyzer:
    """발음(Pronunciation) 분석기"""

    def __init__(self):
        # SPEECH_KEY 또는 AZURE_SPEECH_KEY 지원
        self.speech_key = os.getenv("SPEECH_KEY") or os.getenv("AZURE_SPEECH_KEY")
        self.speech_region = os.getenv("SPEECH_REGION") or os.getenv("AZURE_SPEECH_REGION")

        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech API Key 또는 Region이 설정되지 않았습니다.")

    def assess_pronunciation(self, audio_file: str, reference_text: str, language_code: str = "ko-KR") -> Dict:
        """
        Azure Speech API를 사용하여 발음 평가

        Args:
            audio_file: 음성 파일 경로
            reference_text: 참조 텍스트
            language_code: 언어 코드 (ko-KR 또는 en-US)

        Returns:
            발음 평가 결과 딕셔너리
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
                recognized_text_parts.append(evt.result.text)
                json_result = json.loads(evt.result.properties.get(
                    speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
                all_json_results.append(json_result)
                pron_result = speechsdk.PronunciationAssessmentResult(evt.result)
                all_pron_scores.append(pron_result)

        def session_stopped_cb(evt):
            """세션 종료"""
            done.set()

        def canceled_cb(evt):
            """취소 이벤트"""
            print(f"Error: {evt.error_details}")
            done.set()

        # 이벤트 핸들러 연결
        speech_recognizer.recognized.connect(recognized_cb)
        speech_recognizer.session_stopped.connect(session_stopped_cb)
        speech_recognizer.canceled.connect(canceled_cb)

        # 연속 인식 시작
        speech_recognizer.start_continuous_recognition_async()
        done.wait()
        speech_recognizer.stop_continuous_recognition_async()

        # 결과 처리
        if not all_pron_scores:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": ["음성을 인식할 수 없거나 처리 중 오류가 발생했습니다."],
                "status": "error"
            }

        # 전체 인식된 텍스트
        full_recognized_text = " ".join(recognized_text_parts)

        # 점수 계산 (가중 평균)
        total_duration_ticks = sum(res.get('Duration', 0) for res in all_json_results)

        if total_duration_ticks == 0:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": ["오디오 지속 시간을 계산할 수 없습니다."],
                "status": "error"
            }

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

        # 단어별 상세 평가
        word_details = []
        for i, pron_result in enumerate(all_pron_scores):
            for word in pron_result.words:
                word_details.append({
                    "word": word.word,
                    "accuracy_score": word.accuracy_score
                })

        # Azure 원본 JSON 데이터 병합 (Pause 에이전트용)
        merged_azure_data = None
        if all_json_results:
            # 첫 번째 결과를 기반으로 병합
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

        return {
            "score": round(weighted_pron_score, 2),
            "max_score": 100,
            "feedback": [
                f"종합 발음 점수: {weighted_pron_score:.2f} / 100",
                f"정확도: {weighted_accuracy_score:.2f} / 100",
                f"유창성: {weighted_fluency_score:.2f} / 100",
                f"완전성: {weighted_completeness_score:.2f} / 100"
            ],
            "status": "success",
            "recognized_text": full_recognized_text,
            "accuracy_score": round(weighted_accuracy_score, 2),
            "fluency_score": round(weighted_fluency_score, 2),
            "completeness_score": round(weighted_completeness_score, 2),
            "word_details": word_details,
            "azure_data": merged_azure_data  # Pause 에이전트용
        }

    def analyze(self, wav_path: str, reference_text: str = None, language_code: str = "ko-KR") -> Dict:
        """
        발음 분석 수행

        Args:
            wav_path: WAV 파일 경로
            reference_text: 참조 텍스트 (없으면 기본 텍스트 사용)
            language_code: 언어 코드

        Returns:
            분석 결과 딕셔너리
        """
        try:
            if not reference_text:
                reference_text = "테스트 문장입니다."  # 기본 참조 텍스트

            result = self.assess_pronunciation(wav_path, reference_text, language_code)
            return result

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": [f"분석 중 오류 발생: {str(e)}"],
                "status": "error"
            }


if __name__ == "__main__":
    # 테스트 코드
    analyzer = PronunciationAnalyzer()
    result = analyzer.analyze("test.wav", "안녕하세요 테스트입니다")
    print(json.dumps(result, ensure_ascii=False, indent=2))
