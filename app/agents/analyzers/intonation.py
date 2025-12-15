"""
Intonation Analysis Agent
음성 파일의 억양(Intonation) 분석을 수행하는 에이전트
ISO 25000 품질 모델 + 항공기 음성인식 품질 평가 모델 논문 기반
"""
import os
import json
import numpy as np
import librosa
import azure.cognitiveservices.speech as speechsdk
from typing import Dict, Optional, List
from pathlib import Path


class IntonationAnalyzer:
    """억양(Intonation) 분석기 - ISO 25000 품질 모델 기반"""

    def __init__(self, baseline_dir: str = "baselines"):
        self.baseline_dir = Path(baseline_dir)
        self.baseline_cache = {}

        # ISO 25000 품질 특성별 가중치 (상황별로 변경 가능)
        self.default_quality_weights = {
            "functionality": 0.35,      # 기능 적합성
            "performance_efficiency": 0.15,  # 성능 효율성
            "reliability": 0.15,        # 신뢰성
            "usability": 0.25,          # 사용성
            "portability": 0.10         # 이식성
        }

    def analyze_sentence_ending(self, f0, percentage=0.2):
        """문장 마지막 부분의 억양 패턴 분석 (상승/하강/평탄)"""
        f0_valid = f0[~np.isnan(f0)]

        if len(f0_valid) < 10:
            return {"ending_slope": 0.0, "ending_type": "unknown"}

        # 마지막 20% 구간
        tail_length = int(len(f0_valid) * percentage)
        tail_f0 = f0_valid[-tail_length:]

        # 선형 회귀로 기울기 계산
        x = np.arange(len(tail_f0))
        coeffs = np.polyfit(x, tail_f0, 1)
        slope = coeffs[0]

        # 기울기로 패턴 분류
        if slope > 5:
            ending_type = "rising"
        elif slope < -5:
            ending_type = "falling"
        else:
            ending_type = "flat"

        return {
            "ending_slope": float(slope),
            "ending_type": ending_type
        }

    def detect_rhythm_type(self, energy_std, duration):
        """리듬 타입 분석 (Stress-timed vs Syllable-timed)"""
        energy_variability = energy_std / duration if duration > 0 else 0

        # 에너지 변동성 기준
        if energy_variability > 0.015:
            rhythm_type = "stress-timed"  # 영어식 강세 리듬
        else:
            rhythm_type = "syllable-timed"  # 한국어식 음절 리듬

        return {
            "rhythm_type": rhythm_type,
            "energy_variability": float(energy_variability)
        }

    def _extract_pause_features(self, y: np.ndarray, sr: int) -> Dict:
        """
        Pause 관련 특징 추출 (논문 기반)
        - pause_ratio: 전체 시간 중 침묵 비율
        - avg_pause_duration: 평균 pause 길이
        """
        # librosa.effects.split으로 음성 구간 검출
        intervals = librosa.effects.split(y, top_db=30)

        # 전체 길이
        total_duration = len(y) / sr

        # 음성 구간 길이 합
        speech_duration = sum([(end - start) / sr for start, end in intervals])

        # 침묵 구간 길이
        silence_duration = total_duration - speech_duration

        # pause_ratio 계산
        pause_ratio = silence_duration / total_duration if total_duration > 0 else 0

        # 각 pause 구간의 길이 계산
        pause_durations = []
        for i in range(len(intervals) - 1):
            pause_start = intervals[i][1] / sr
            pause_end = intervals[i + 1][0] / sr
            pause_dur = pause_end - pause_start
            if pause_dur > 0.05:  # 50ms 이상만 유효한 pause로 간주
                pause_durations.append(pause_dur)

        avg_pause_duration = np.mean(pause_durations) if pause_durations else 0

        return {
            "pause_ratio": float(pause_ratio),
            "avg_pause_duration": float(avg_pause_duration),
            "pause_count": len(pause_durations)
        }

    def extract_features(self, audio_path: str) -> Dict:
        """Pitch, Energy, Duration 등 핵심 피처 추출 (고급 분석 포함)"""
        y, sr = librosa.load(audio_path, sr=None)

        # 1. 기본 피치 추출
        f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

        f0_valid = f0[~np.isnan(f0)]
        f0_mean = np.mean(f0_valid) if len(f0_valid) > 0 else 0
        f0_std = np.std(f0_valid) if len(f0_valid) > 0 else 0

        # 2. 고급 피치 분석
        f0_range = np.max(f0_valid) - np.min(f0_valid) if len(f0_valid) > 0 else 0
        f0_median = np.median(f0_valid) if len(f0_valid) > 0 else 0

        # 피치 변화율 (1차 미분)
        f0_delta = np.diff(f0_valid)
        f0_delta_mean = np.mean(np.abs(f0_delta)) if len(f0_delta) > 0 else 0

        # 3. 문장 종결 억양 분석
        ending_info = self.analyze_sentence_ending(f0)

        # 4. 에너지 분석
        rms = librosa.feature.rms(y=y)[0]
        energy_mean = np.mean(rms)
        energy_std = np.std(rms)
        energy_max = np.max(rms)

        # 5. 리듬 타입 분석
        rhythm_info = self.detect_rhythm_type(energy_std, librosa.get_duration(y=y, sr=sr))

        # 6. 스펙트럼 특징
        spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
        spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr))

        # 7. 억양 곡선 형태 분석
        rising_ratio = np.sum(f0_delta > 0) / len(f0_delta) if len(f0_delta) > 0 else 0
        falling_ratio = np.sum(f0_delta < 0) / len(f0_delta) if len(f0_delta) > 0 else 0

        # 8. 시간 관련 특징
        duration = librosa.get_duration(y=y, sr=sr)
        zcr = np.mean(librosa.feature.zero_crossing_rate(y))

        # 9. MFCC (Mel-Frequency Cepstral Coefficients) - 음색 특징
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        mfcc_mean = np.mean(mfcc, axis=1)

        # 10. Pause 관련 특징 (신규 추가 - 논문 기반)
        pause_features = self._extract_pause_features(y, sr)

        # 11. 문장 끝 하강 정도 (한국어 전용)
        sentence_final_lowering = -ending_info["ending_slope"] if ending_info["ending_slope"] < 0 else 0

        return {
            # 기본 피치
            "f0_mean": float(f0_mean),
            "f0_std": float(f0_std),
            "f0_median": float(f0_median),
            "f0_range": float(f0_range),
            "f0_delta_mean": float(f0_delta_mean),

            # 에너지
            "energy": float(energy_mean),
            "energy_std": float(energy_std),
            "energy_max": float(energy_max),

            # 스펙트럼
            "spectral_centroid": float(spectral_centroid),
            "spectral_rolloff": float(spectral_rolloff),

            # 억양 패턴
            "rising_ratio": float(rising_ratio),
            "falling_ratio": float(falling_ratio),

            # 시간/변동성
            "duration": float(duration),
            "zero_crossing_rate": float(zcr),

            # MFCC (첫 5개만)
            "mfcc_1": float(mfcc_mean[0]),
            "mfcc_2": float(mfcc_mean[1]),
            "mfcc_3": float(mfcc_mean[2]),
            "mfcc_4": float(mfcc_mean[3]),
            "mfcc_5": float(mfcc_mean[4]),

            # 고급 분석 결과 (문장 종결 & 리듬)
            "ending_slope": ending_info["ending_slope"],
            "ending_type": ending_info["ending_type"],
            "rhythm_type": rhythm_info["rhythm_type"],
            "energy_variability": rhythm_info["energy_variability"],

            # 신규 추가 (논문 기반)
            "pause_ratio": pause_features["pause_ratio"],
            "avg_pause_duration": pause_features["avg_pause_duration"],
            "pause_count": pause_features["pause_count"],
            "sentence_final_lowering": float(sentence_final_lowering),
        }

    def get_language_specific_weights(self, lang):
        """언어별 특성을 반영한 가중치 반환

        - Korean (ko-KR): Syllable-timed, 음절 균등, 피치 평탄
        - English (en-US): Stress-timed, 강세 중심, 에너지 변동 큼
        """

        if lang.startswith("ko"):  # Seoul Korean
            return {
                # 피치 기본 특성 (32%)
                "f0_mean": 0.10,
                "f0_std": 0.08,
                "f0_range": 0.07,
                "f0_delta_mean": 0.07,

                # 억양 패턴 (35%)
                "rising_ratio": 0.18,
                "falling_ratio": 0.12,
                "spectral_centroid": 0.05,

                # 에너지 & 강세 (15%)
                "energy": 0.08,
                "energy_std": 0.07,

                # 시간 & 안정성 (13%)
                "zero_crossing_rate": 0.06,
                "duration": 0.07,

                # MFCC 음색 분석 (5%)
                "mfcc_1": 0.01,
                "mfcc_2": 0.01,
                "mfcc_3": 0.01,
                "mfcc_4": 0.01,
                "mfcc_5": 0.01,
            }
        else:  # English
            return {
                # 피치 기본 특성 (28%)
                "f0_mean": 0.08,
                "f0_std": 0.12,
                "f0_range": 0.04,
                "f0_delta_mean": 0.04,

                # 억양 패턴 (32%)
                "rising_ratio": 0.10,
                "falling_ratio": 0.17,
                "spectral_centroid": 0.05,

                # 에너지 & 강세 (25%)
                "energy": 0.10,
                "energy_std": 0.15,

                # 시간 & 안정성 (10%)
                "zero_crossing_rate": 0.04,
                "duration": 0.06,

                # MFCC 음색 분석 (5%)
                "mfcc_1": 0.01,
                "mfcc_2": 0.01,
                "mfcc_3": 0.01,
                "mfcc_4": 0.01,
                "mfcc_5": 0.01,
            }

    def compare_with_reference(self, test_feat, ref_feat, lang="en-US"):
        """기준 JSON 기반으로 점수 산출 (언어별 가중치 적용)

        새 형식(mean/std)과 기존 형식(단일 값) 모두 지원
        """

        # 언어별 가중치 가져오기
        weights = self.get_language_specific_weights(lang)

        # 기준값 추출 (새 형식: {"mean": X, "std": Y}, 기존 형식: X)
        ref_values = {}
        ref_stds = {}

        for key in weights.keys():
            ref_data = ref_feat.get(key)

            if isinstance(ref_data, dict) and "mean" in ref_data:
                # 새 형식: mean/std 사용
                ref_values[key] = ref_data["mean"]
                ref_stds[key] = ref_data.get("std", 0)
            else:
                # 기존 형식: 단일 값 사용
                ref_values[key] = ref_data if ref_data is not None else test_feat.get(key, 1)
                ref_stds[key] = 0

        max_scores = {k: w * 20 for k, w in weights.items()}

        # 유사도 계산 (표준편차 고려)
        diffs = {}
        similarities = {}

        for k in weights.keys():
            if k in test_feat and ref_values[k] > 0:
                ref_mean = ref_values[k]
                ref_std = ref_stds[k]
                test_val = test_feat[k]

                # 표준편차가 있으면 정규화된 거리 사용 (더 관대한 평가)
                if ref_std > 0:
                    # z-score 기반: |test - mean| / std
                    # std 범위 내면 similarity 높게, 벗어날수록 낮게
                    z_score = abs(test_val - ref_mean) / ref_std
                    # z_score 0 -> similarity 1, z_score 3 -> similarity 0.5, z_score 6 -> similarity 0
                    similarities[k] = max(0, 1 - z_score / 6)
                else:
                    # 표준편차 없으면 기존 방식 (상대 차이)
                    diffs[k] = abs(test_val - ref_mean) / (ref_mean + 1e-6)
                    similarities[k] = max(0, 1 - diffs[k])
            else:
                similarities[k] = 0

        # 항목별 점수 계산
        item_scores = {k: round(similarities[k] * max_scores[k], 2) for k in weights.keys()}

        # 총점 계산
        total_score = round(sum(item_scores.values()), 2)

        return total_score, item_scores

    def _get_asr_metrics(self, wav_path: str, reference_text: Optional[str], language_code: str, accent_timestamps: Optional[List[Dict]] = None) -> Dict:
        """
        ASR 보조 지표 계산 (논문 핵심 지표)
        - asr_confidence_mean: Azure STT 인식 신뢰도 평균
        - asr_confidence_std: 신뢰도 변동폭
        - asr_wer: Word Error Rate (reference_text가 있을 때만)

        Args:
            wav_path: 음성 파일 경로
            reference_text: 참조 텍스트 (WER 계산용)
            language_code: 언어 코드
            accent_timestamps: Accent 에이전트의 타임스탬프 데이터 (재사용용)
        """
        # Accent 데이터가 있으면 재사용
        print(f"[INTONATION DEBUG] accent_timestamps 수신: {accent_timestamps is not None}, 개수: {len(accent_timestamps) if accent_timestamps else 0}")

        if accent_timestamps:
            try:
                # Accent 데이터에서 Confidence 추출
                confidences = []
                words = []

                for item in accent_timestamps:
                    if 'confidence' in item:
                        confidences.append(item['confidence'])
                    if 'word' in item:
                        words.append(item['word'])

                if confidences:
                    asr_confidence_mean = float(np.mean(confidences))
                    asr_confidence_std = float(np.std(confidences))
                    recognized_text = " ".join(words)

                    print(f"[INTONATION DEBUG] Accent 데이터 재사용 성공! confidence_mean={asr_confidence_mean:.4f}")

                    # WER 계산 (reference_text가 있을 때만)
                    asr_wer = 0.0
                    if reference_text and recognized_text:
                        try:
                            from jiwer import wer
                            asr_wer = float(wer(reference_text, recognized_text))
                        except ImportError:
                            asr_wer = 0.0

                    return {
                        "asr_confidence_mean": asr_confidence_mean,
                        "asr_confidence_std": asr_confidence_std,
                        "asr_wer": asr_wer,
                        "recognized_text": recognized_text,
                        "asr_status": "reused_from_accent"
                    }
                else:
                    print(f"[INTONATION DEBUG] Accent 데이터에서 confidence를 추출하지 못함")
            except Exception as e:
                print(f"[INTONATION DEBUG] Accent 데이터 재사용 중 오류: {e}. Azure API 직접 호출로 전환합니다.")

        # Accent 데이터가 없거나 재사용 실패 시 직접 Azure API 호출
        try:
            speech_key = os.getenv("SPEECH_KEY") or os.getenv("AZURE_SPEECH_KEY")
            speech_region = os.getenv("SPEECH_REGION") or os.getenv("AZURE_SPEECH_REGION")

            if not speech_key or not speech_region:
                # Azure 없을 때 중립값 사용 (0점 패널티 방지)
                return {
                    "asr_confidence_mean": 0.7,  # 중립적 신뢰도
                    "asr_confidence_std": 0.1,   # 낮은 변동성
                    "asr_wer": 0.0,
                    "asr_status": "disabled"
                }

            # Azure STT 설정
            lang_code = language_code if language_code else "ko-KR"
            speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
            speech_config.speech_recognition_language = lang_code

            audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
            recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

            # 음성 인식 실행
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # JSON 결과 파싱
                json_result = json.loads(result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult))

                # Confidence 추출
                words = json_result.get('NBest', [{}])[0].get('Words', [])
                if words:
                    confidences = [w.get('Confidence', 0.0) for w in words]
                    asr_confidence_mean = float(np.mean(confidences))
                    asr_confidence_std = float(np.std(confidences))
                else:
                    asr_confidence_mean = 0.0
                    asr_confidence_std = 0.0

                # WER 계산 (reference_text가 있을 때만)
                asr_wer = 0.0
                if reference_text:
                    try:
                        from jiwer import wer
                        recognized_text = result.text
                        asr_wer = float(wer(reference_text, recognized_text))
                    except ImportError:
                        # jiwer 없으면 WER 계산 생략
                        asr_wer = 0.0

                return {
                    "asr_confidence_mean": asr_confidence_mean,
                    "asr_confidence_std": asr_confidence_std,
                    "asr_wer": asr_wer,
                    "recognized_text": result.text,
                    "asr_status": "success"
                }
            else:
                # Azure STT 실패 시 중립값 사용
                return {
                    "asr_confidence_mean": 0.5,  # 중립적 신뢰도
                    "asr_confidence_std": 0.15,  # 중간 변동성
                    "asr_wer": 0.0,
                    "asr_status": "failed"
                }

        except Exception as e:
            # 예외 발생 시 중립값 사용
            return {
                "asr_confidence_mean": 0.5,
                "asr_confidence_std": 0.15,
                "asr_wer": 0.0,
                "asr_status": f"error: {str(e)}"
            }

    def _compute_quality_attributes(self, metrics: Dict, lang: str, asr_metrics: Dict) -> Dict:
        """
        ISO 25000 품질 특성 계층 점수 계산
        Metric → Quality Attribute 매핑
        """
        # 1. 기능 적합성 (Functionality): 억양이 언어별 규칙에 맞는가?
        functionality_score = 0.0
        if lang.startswith("ko"):
            # 한국어: 문장 끝 하강 패턴 + 리듬 타입 + ASR 정확도
            functionality_score = (
                0.3 * (metrics.get("sentence_final_lowering", 0) / 10.0 * 100) +  # 문장 끝 하강
                0.2 * (100 if metrics.get("rhythm_type") == "syllable-timed" else 50) +  # 리듬 타입
                0.3 * (100 - asr_metrics.get("asr_wer", 0) * 100) +  # WER (낮을수록 좋음)
                0.2 * (asr_metrics.get("asr_confidence_mean", 0) * 100)  # ASR 신뢰도
            )
        else:
            # 영어: 강세 패턴 + ASR 정확도
            functionality_score = (
                0.2 * (100 if metrics.get("rhythm_type") == "stress-timed" else 50) +
                0.3 * (metrics.get("falling_ratio", 0.5) * 200) +  # 하강 억양 (핵 톤)
                0.3 * (100 - asr_metrics.get("asr_wer", 0) * 100) +
                0.2 * (asr_metrics.get("asr_confidence_mean", 0) * 100)
            )

        # 2. 성능 효율성 (Performance Efficiency): 적정 시간 내 전달
        duration = metrics.get("duration", 0)
        pause_ratio = metrics.get("pause_ratio", 0)
        performance_score = (
            0.6 * (100 if 5 <= duration <= 30 else 70) +  # 적정 길이 (5~30초)
            0.4 * (100 if 0.1 <= pause_ratio <= 0.3 else 70)  # 적정 pause 비율
        )

        # 3. 신뢰성 (Reliability): 안정적이고 일관된 억양
        reliability_score = (
            0.4 * (100 - min(metrics.get("f0_std", 0) / 100 * 100, 100)) +  # F0 변동성 (표현력 고려하여 완화)
            0.3 * (100 - min(metrics.get("energy_std", 0) / 0.4 * 100, 100)) +  # Energy 변동성 (표현력 고려하여 완화)
            0.3 * (100 - asr_metrics.get("asr_confidence_std", 0) * 200)  # ASR 신뢰도 변동 (작을수록 좋음)
        )

        # 4. 사용성 (Usability): 이해하기 쉽고 표현력 풍부
        usability_score = (
            0.3 * (metrics.get("f0_range", 0) / 200 * 100) +  # F0 범위 (표현력)
            0.3 * (metrics.get("energy_variability", 0) * 1000) +  # 에너지 변동 (강세 표현)
            0.4 * (asr_metrics.get("asr_confidence_mean", 0) * 100)  # 명료성
        )

        # 5. 이식성 (Portability): 화자/언어 적응성
        portability_score = 100.0  # 기본 점수 (개인 baseline 구축 시 활용)

        return {
            "functionality": max(0, min(100, functionality_score)),
            "performance_efficiency": max(0, min(100, performance_score)),
            "reliability": max(0, min(100, reliability_score)),
            "usability": max(0, min(100, usability_score)),
            "portability": max(0, min(100, portability_score))
        }

    def _compute_final_score_from_quality(self, quality_scores: Dict, quality_weights: Dict) -> float:
        """
        ISO 25000 품질 특성별 점수 → 최종 점수 (가중합)
        """
        final_score = sum(
            quality_scores[attr] * quality_weights[attr]
            for attr in quality_weights.keys()
        )
        return max(0, min(100, final_score))

    def get_scenario_weights(self, scenario: str = "general") -> Dict:
        """
        상황별 ISO 25000 품질 특성 가중치 설계 (논문 기반)

        Args:
            scenario: "safety_takeoff", "service_inflight", "emergency", "general" 등
        """
        if scenario == "safety_takeoff":
            # 안전 안내 (이륙 전): 기능 적합성 최우선
            return {
                "functionality": 0.50,
                "performance_efficiency": 0.10,
                "reliability": 0.20,
                "usability": 0.20,
                "portability": 0.00
            }
        elif scenario == "service_inflight":
            # 기내 서비스: 사용성 (친절함) 우선
            return {
                "functionality": 0.20,
                "performance_efficiency": 0.10,
                "reliability": 0.20,
                "usability": 0.50,
                "portability": 0.00
            }
        elif scenario == "emergency":
            # 긴급 안내: 기능 + 성능 우선
            return {
                "functionality": 0.40,
                "performance_efficiency": 0.30,
                "reliability": 0.20,
                "usability": 0.10,
                "portability": 0.00
            }
        else:
            # 일반 (기본값)
            return self.default_quality_weights

    def load_baseline(self, baseline_name: str = "default") -> Dict:
        """Baseline 로드"""
        if baseline_name in self.baseline_cache:
            return self.baseline_cache[baseline_name]

        baseline_file = self.baseline_dir / f"intonation_{baseline_name}.json"
        if not baseline_file.exists():
            return None

        with open(baseline_file, 'r', encoding='utf-8') as f:
            baseline = json.load(f)

        self.baseline_cache[baseline_name] = baseline
        return baseline

    def analyze(self, wav_path: str, gender: str = "F", reference_text: str = None, baseline_name: str = "default", language_code: str = None, scenario: str = "general", weight_baseline: float = 0.7, weight_iso: float = 0.3, accent_timestamps: list = None, **kwargs) -> Dict:
        """
        억양 분석 수행 (ISO 25000 + 논문 기반)

        Args:
            wav_path: WAV 파일 경로
            gender: 성별 (F 또는 M, 기본값: F)
            reference_text: 참조 텍스트 (WER 계산용, 선택)
            baseline_name: Baseline 이름
            language_code: 언어 코드 (선택적, 없으면 파일명 기반 판별)
            scenario: 상황별 가중치 ("safety_takeoff", "service_inflight", "emergency", "general")
            accent_timestamps: Accent 에이전트의 타임스탬프 데이터 (재사용용, 선택)

        Returns:
            분석 결과 딕셔너리 (ISO 25000 품질 특성 포함, 0-100점 환산)
        """
        try:
            # 1. 특징 추출
            test_features = self.extract_features(wav_path)

            # 2. 언어 감지
            if language_code:
                lang = language_code
            else:
                # 파일명 기반 언어 판별
                audio_filename = str(wav_path).lower()
                if "ko" in audio_filename or "한글" in audio_filename or "korean" in audio_filename:
                    lang = "ko-KR"
                else:
                    lang = "en-US"

            # 3. ASR 보조 지표 추출 (논문 핵심)
            # Accent 데이터가 있으면 재사용, 없으면 직접 Azure API 호출
            asr_metrics = self._get_asr_metrics(wav_path, reference_text, lang, accent_timestamps)

            # 4. ISO 25000 품질 특성 계산
            quality_scores = self._compute_quality_attributes(test_features, lang, asr_metrics)

            # 5. 상황별 가중치 적용
            quality_weights = self.get_scenario_weights(scenario)

            # 6. 최종 점수 계산 (ISO 25000 기반)
            final_score_iso = self._compute_final_score_from_quality(quality_scores, quality_weights)

            # 7. 기존 Baseline 비교 (Gender/Language별 지원 + 하위 호환성 유지)
            baseline = self.load_baseline(baseline_name)
            baseline_score = 0
            if baseline:
                # 새 포맷: Gender/Language별 구조
                if "genders" in baseline:
                    # Gender → Language → Features 탐색
                    if gender in baseline["genders"]:
                        if lang in baseline["genders"][gender]["languages"]:
                            ref_features = baseline["genders"][gender]["languages"][lang]["features"]
                            score_20, item_scores = self.compare_with_reference(test_features, ref_features, lang)
                            baseline_score = (score_20 / 20) * 100
                        else:
                            print(f"[INTONATION WARNING] Baseline에 언어 {lang}가 없습니다 (gender={gender})")
                    else:
                        print(f"[INTONATION WARNING] Baseline에 gender {gender}가 없습니다")

                # 기존 포맷: reference_features 직접 사용
                elif "reference_features" in baseline:
                    ref_features = baseline["reference_features"]
                    score_20, item_scores = self.compare_with_reference(test_features, ref_features, lang)
                    baseline_score = (score_20 / 20) * 100

            # 8. 최종 점수: Baseline 우선, ISO는 보조 역할
            # Baseline이 있으면 가중치 적용, 없으면 ISO 100%
            if baseline_score > 0:
                final_score = baseline_score * weight_baseline + final_score_iso * weight_iso
            else:
                final_score = final_score_iso

            # 9. 피드백 생성
            feedback = [
                f"언어: {'한국어' if lang.startswith('ko') else '영어'}",
                f"상황: {scenario}",
                f"최종 점수: {final_score:.1f}점 (ISO 25000 기반)",
                f"리듬 타입: {test_features['rhythm_type']}",
                f"문장 종결 패턴: {test_features['ending_type']}",
                "",
                "=== ISO 25000 품질 특성별 점수 ===",
                f"기능 적합성: {quality_scores['functionality']:.1f}점",
                f"성능 효율성: {quality_scores['performance_efficiency']:.1f}점",
                f"신뢰성: {quality_scores['reliability']:.1f}점",
                f"사용성: {quality_scores['usability']:.1f}점",
                f"이식성: {quality_scores['portability']:.1f}점",
                "",
                f"ASR 인식 신뢰도: {asr_metrics['asr_confidence_mean']*100:.1f}%",
            ]

            # WER 정보 추가 (reference_text가 있을 때만)
            if reference_text and asr_metrics.get('asr_wer', 0) > 0:
                feedback.append(f"ASR WER: {asr_metrics['asr_wer']*100:.1f}%")

            return {
                "score": round(final_score, 2),
                "max_score": 100,
                "feedback": feedback,
                "status": "success",
                "language": lang,
                "scenario": scenario,
                "rhythm_type": test_features["rhythm_type"],
                "ending_type": test_features["ending_type"],
                # ISO 25000 품질 특성 점수
                "quality_scores": quality_scores,
                "quality_weights": quality_weights,
                # ASR 보조 지표
                "asr_metrics": asr_metrics,
                # 원본 특징
                "features": test_features
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "status": "error",
                "error_message": str(e),
                "quality_scores": {},
                "asr_metrics": {}
            }