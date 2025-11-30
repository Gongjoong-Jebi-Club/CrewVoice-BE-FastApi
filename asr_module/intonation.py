"""
Intonation Analysis Agent
음성 파일의 억양(Intonation) 분석을 수행하는 에이전트
"""
import json
import numpy as np
import librosa
from typing import Dict
from pathlib import Path


class IntonationAnalyzer:
    """억양(Intonation) 분석기"""

    def __init__(self, baseline_dir: str = "baselines"):
        self.baseline_dir = Path(baseline_dir)
        self.baseline_cache = {}

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
        """기준 JSON 기반으로 점수 산출 (언어별 가중치 적용)"""

        # 언어별 가중치 가져오기
        weights = self.get_language_specific_weights(lang)

        # 기준값 추출
        ref_values = {}
        for key in weights.keys():
            ref_values[key] = ref_feat.get(key, test_feat.get(key, 1))

        max_scores = {k: w * 20 for k, w in weights.items()}

        # 유사도 계산
        diffs = {}
        similarities = {}
        for k in weights.keys():
            if k in test_feat and ref_values[k] > 0:
                diffs[k] = abs(test_feat[k] - ref_values[k]) / (ref_values[k] + 1e-6)
                similarities[k] = max(0, 1 - diffs[k])
            else:
                similarities[k] = 0

        # 항목별 점수 계산
        item_scores = {k: round(similarities[k] * max_scores[k], 2) for k in weights.keys()}

        # 총점 계산
        total_score = round(sum(item_scores.values()), 2)

        return total_score, item_scores

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

    def analyze(self, wav_path: str, reference_text: str = None, baseline_name: str = "default", language_code: str = None) -> Dict:
        """
        억양 분석 수행

        Args:
            wav_path: WAV 파일 경로
            reference_text: 참조 텍스트 (사용 안 함)
            baseline_name: Baseline 이름
            language_code: 언어 코드 (선택적, 없으면 파일명 기반 판별)

        Returns:
            분석 결과 딕셔너리 (0-100점 환산)
        """
        try:
            # 특징 추출
            test_features = self.extract_features(wav_path)

            # 언어 감지 (language_code > 파일명 기반 판별)
            if language_code:
                lang = language_code
            else:
                # 파일명 기반 언어 판별
                audio_filename = str(wav_path).lower()
                if "ko" in audio_filename or "한글" in audio_filename or "korean" in audio_filename:
                    lang = "ko-KR"
                else:
                    lang = "en-US"

            # Baseline 비교
            baseline = self.load_baseline(baseline_name)

            if baseline and "reference_features" in baseline:
                ref_features = baseline["reference_features"]
                score_20, item_scores = self.compare_with_reference(test_features, ref_features, lang)

                # 20점 만점을 100점 만점으로 환산
                score_100 = (score_20 / 20) * 100

                feedback = [
                    f"언어: {'한국어' if lang.startswith('ko') else '영어'}",
                    f"억양 점수: {score_20:.1f} / 20.0점",
                    f"리듬 타입: {test_features['rhythm_type']}",
                    f"문장 종결 패턴: {test_features['ending_type']}"
                ]

                # 등급 판정
                if score_100 >= 90:
                    feedback.append("S등급: 표준 억양을 자연스럽고 세련되게 구사합니다.")
                elif score_100 >= 80:
                    feedback.append("A등급: 전반적으로 자연스럽게 구사합니다.")
                elif score_100 >= 70:
                    feedback.append("B등급: 대체로 무난하나 일부 억양이 반복됩니다.")
                else:
                    feedback.append("C등급: 억양 변화가 부족하여 부자연스럽습니다.")

                return {
                    "score": round(score_100, 2),
                    "max_score": 100,
                    "feedback": feedback,
                    "status": "success",
                    "language": lang,
                    "rhythm_type": test_features["rhythm_type"],
                    "ending_type": test_features["ending_type"],
                    "features": test_features
                }
            else:
                # Baseline 없으면 기본 점수 (80점)
                return {
                    "score": 80,
                    "max_score": 100,
                    "feedback": [
                        f"언어: {'한국어' if lang.startswith('ko') else '영어'}",
                        f"리듬 타입: {test_features['rhythm_type']}",
                        f"문장 종결 패턴: {test_features['ending_type']}",
                        "Baseline 없음 - 기본 점수 부여"
                    ],
                    "status": "warning",
                    "language": lang,
                    "features": test_features
                }

        except Exception as e:
            return {
                "score": 70,
                "max_score": 100,
                "feedback": [f"분석 중 오류 발생: {str(e)}", "기본 점수를 부여합니다."],
                "status": "warning"
            }


if __name__ == "__main__":
    # 테스트 코드
    analyzer = IntonationAnalyzer()
    result = analyzer.analyze("test.wav")
    print(json.dumps(result, ensure_ascii=False, indent=2))
