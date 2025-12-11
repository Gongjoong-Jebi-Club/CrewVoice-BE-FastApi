"""
Tone Analysis Agent
음성 파일의 톤(Tone) 분석을 수행하는 에이전트
"""
import sys
import json
import librosa
import parselmouth
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path

# 기존 코드 경로 추가
BASE_DIR = Path(__file__).parent.parent.parent

# tone baseline JSON 기본 경로 (필요하면 프로젝트 구조에 맞게 수정)
DEFAULT_TONE_BASELINE_PATH = BASE_DIR / "agents" / "baselines" / "tone_default.json"

class ToneAnalyzer:
    """톤(Tone) 분석기"""

    def __init__(self):
        self._baseline: Optional[Dict[str, Any]] = None  # tone baseline 데이터 저장용

    def load_audio_from_file(self, file_path: str) -> Tuple[np.ndarray, int]:
        """파일에서 오디오 로드"""
        y, sr = librosa.load(file_path, sr=22050, mono=True)
        return y, sr

    def extract_tone_features(self, y: np.ndarray, sr: int) -> Dict:
        """톤 특징 추출"""
        # 1) Pitch (F0) 추출
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=sr
        )
        f0_values = f0[~np.isnan(f0)]

        f0_mean = float(np.mean(f0_values)) if len(f0_values) > 0 else 0.0
        f0_std = float(np.std(f0_values)) if len(f0_values) > 0 else 0.0

        # 2) Energy (RMS)
        rms = librosa.feature.rms(y=y)[0]
        rms_mean = float(np.mean(rms))
        rms_std = float(np.std(rms))

        # 3) Spectral Centroid (음색 밝기)
        spec_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spec_centroid_mean = float(np.mean(spec_centroid))

        # 4) HNR (Harmonics-to-Noise Ratio) 근사치
        snd = parselmouth.Sound(y, sampling_frequency=sr)
        harmonicity = snd.to_harmonicity()
        hnr_values = []

        for i in range(harmonicity.nx):
            t = harmonicity.x1 + i * harmonicity.dx
            hnr = harmonicity.get_value(t)
            if not np.isnan(hnr) and not np.isinf(hnr):
                hnr_values.append(hnr)

        hnr_like = float(np.mean(hnr_values)) if hnr_values else 0.0

        return {
            "f0_mean": f0_mean,
            "f0_std": f0_std,
            "rms_mean": rms_mean,
            "rms_std": rms_std,
            "spec_centroid_mean": spec_centroid_mean,
            "hnr_like": hnr_like
        }

    # ------------------------------------------------------------------
    # 여기부터 새로 추가: baseline 로딩 + z-score 기반 score 계산 로직
    # ------------------------------------------------------------------

    # 0) baseline JSON 로딩 / 언어별 feature 통계 접근
    def _ensure_baseline_loaded(
        self,
        baseline_path: Path = DEFAULT_TONE_BASELINE_PATH,
    ) -> None:
        """tone_default.json을 한 번만 로드"""
        if self._baseline is None:
            with open(baseline_path, "r", encoding="utf-8") as f:
                self._baseline = json.load(f)
    
    def _get_lang_features(
        self,
        language_code: str,
        gender: str = "F",
    ) -> Dict[str, Dict[str, float]]:
        """
        baseline에서 언어별 feature 통계를 가져오는 함수.

        기존 구조:
            baseline["languages"][language_code]["features"]

        변경된 구조(확장 대비):
            baseline["genders"][gender]["languages"][language_code]["features"]

        ⚠ 현재 baseline에는 F만 존재하므로,
          gender가 존재하지 않으면 자동으로 "F"로 fallback한다.
        """

        if self._baseline is None:
            raise RuntimeError("Baseline is not loaded. Call _ensure_baseline_loaded() first.")

        genders = self._baseline.get("genders", {})

        # 여기서 gender fallback 수행
        if gender not in genders:
            # baseline에 해당 gender 키가 없으면 F로 자동 교체
            # (현재 baseline에는 F만 존재하므로 안전하게 평가 가능)
            gender = "F"

        langs = genders[gender]["languages"]

        if language_code not in langs:
            raise ValueError(f"Language '{language_code}' not found for gender '{gender}' in tone baseline.")

        return langs[language_code]["features"]
    
    @staticmethod
    def _get_feature_stats(
        lang_features: Dict[str, Dict[str, float]],
        feature_name: str,
    ) -> Tuple[float, float]:
        '''
        각 feature에 대해 baseline에서의 평균(mean)과 표준편차(std)를 반환
        '''
        stats = lang_features[feature_name]
        return stats["mean"], stats["std"]
    
    # 1) 공통 유틸: z-score 및 점수 함수(임계값 역할 포함)

    @staticmethod
    def _z_score(value: float, mean: float, std: float) -> float:
        """z = (x - μ) / σ"""
        return (value - mean) / (std + 1e-9)

    @staticmethod
    def _clip(value: float, min_value: float = 0.0, max_value: float = 10.0) -> float:
        return max(min_value, min(max_value, value))

    @staticmethod
    def _center_optimal_score(
        z: float,
        max_score: float = 10.0,
        z_zero: float = 2.5,
        z_full: float = 0.5,
    ) -> float:
        """
        만점 범위를 추가한 center optimal score 함수

        |z| ≤ z_full → max_score (만점 범위)
        z_full < |z| < z_zero → 선형 감점
        |z| ≥ z_zero → 0점

        Args:
            z: z-score 값
            max_score: 최대 점수 (기본값: 10.0)
            z_zero: 0점이 되는 |z| 임계값 (기본값: 2.5)
            z_full: 만점이 되는 |z| 임계값 (기본값: 0.5)

        Example:
            z_full=0.5, z_zero=2.5일 때:
            - |z| ≤ 0.5 → 10점
            - |z| = 1.0 → 7.5점
            - |z| = 1.5 → 5.0점
            - |z| = 2.0 → 2.5점
            - |z| ≥ 2.5 → 0점
        """
        dz = abs(z)

        # 만점 범위
        if dz <= z_full:
            return max_score

        # 0점 범위
        if dz >= z_zero:
            return 0.0

        # z_full ~ z_zero 사이에서 선형 감점
        ratio = (dz - z_full) / (z_zero - z_full)
        score = max_score * (1.0 - ratio)
        return ToneAnalyzer._clip(score, 0.0, max_score)

    @staticmethod
    def _lower_bounded_score(
        z: float,
        max_score: float = 10.0,
        min_score: float = 0.0,
        z_full: float = 1.0,
        z_zero: float = -2.0,
    ) -> float:
        """
        clarity(HNR)처럼 'baseline보다 낮은 쪽'으로 벗어나면 안 좋은 경우에 사용.

        - z <= z_zero → min_score (임계값 이하: 거의 최악)
        - z >= z_full → max_score (충분히 좋음)
        - 그 사이: 선형 보간

        여기서 z_zero, z_full이 임계값 역할:
        - z_zero: 이 이하로 내려가면 0점
        - z_full: 이 이상이면 만점
        """
        if z <= z_zero:
            return min_score
        if z >= z_full:
            return max_score

        ratio = (z - z_zero) / (z_full - z_zero + 1e-9)  # 0~1
        score = min_score + ratio * (max_score - min_score)
        return ToneAnalyzer._clip(score, min_score, max_score)
    
    # 2) 4개 Tone 축 score 계산 (clarity, stability, brightness, pitch_position)

    def _clarity_score(
        self,
        feats: Dict[str, float],
        lang_features: Dict[str, Dict[str, float]],
    ) -> float:
        """
        clarity ← hnr_like
        - baseline보다 낮으면 탁하고 잡음이 많은 톤으로 간주 → 강한 감점
        - baseline보다 충분히 높으면(좋은 HNR) → 만점 처리
        """
        hnr_val = feats["hnr_like"]
        mean, std = self._get_feature_stats(lang_features, "hnr_like")
        z = self._z_score(hnr_val, mean, std)

        return self._lower_bounded_score(
            z,
            max_score=10.0,
            min_score=0.0,
            # z_full=1.0,    # z >= 1.0 (μ + 1σ 이상) → 만점
            # z_zero=-2.0,   # z <= -2.0 (μ - 2σ 이하) → 0점
            z_full=0.0,    # z >= 0.5 (μ + 0.5σ 이상) → 만점
            z_zero=-2.0,   # z <= -2.0 (μ - 2σ 이하) → 0점
        )

    def _stability_score(
        self,
        feats: Dict[str, float],
        lang_features: Dict[str, Dict[str, float]],
    ) -> float:
        """
        stability ← f0_std + rms_std
        - pitch/볼륨 변동폭이 baseline과 비슷할수록 좋음
        - 너무 출렁이거나 / 너무 평평해도 감점
        """
        # pitch variability
        f0_std_val = feats["f0_std"]
        mean_f0_std, std_f0_std = self._get_feature_stats(lang_features, "f0_std")
        z_f0 = self._z_score(f0_std_val, mean_f0_std, std_f0_std)
        f0_score = self._center_optimal_score(z_f0, max_score=10.0, z_zero=2.5)

        # volume variability
        rms_std_val = feats["rms_std"]
        mean_rms_std, std_rms_std = self._get_feature_stats(lang_features, "rms_std")
        z_rms = self._z_score(rms_std_val, mean_rms_std, std_rms_std)
        rms_score = self._center_optimal_score(z_rms, max_score=10.0, z_zero=2.5)

        return (f0_score + rms_score) / 2.0

    def _brightness_score(
        self,
        feats: Dict[str, float],
        lang_features: Dict[str, Dict[str, float]],
    ) -> float:
        """
        brightness ← spec_centroid_mean
        - baseline 근처가 가장 좋고,
          너무 낮으면 '어둡고 답답한' 톤,
          너무 높으면 '찌르는 듯한' 톤으로 감점
        """
        spec_val = feats["spec_centroid_mean"]
        mean, std = self._get_feature_stats(lang_features, "spec_centroid_mean")
        z = self._z_score(spec_val, mean, std)
        return self._center_optimal_score(z, max_score=10.0, z_zero=2.5)

    def _pitch_position_score(
        self,
        feats: Dict[str, float],
        lang_features: Dict[str, Dict[str, float]],
    ) -> float:
        """
        pitch_position ← f0_mean
        - baseline 여성 기준 평균 음높이 근처가 이상적
        - 너무 낮거나 너무 높으면 점점 감점
        """
        f0_mean_val = feats["f0_mean"]
        mean, std = self._get_feature_stats(lang_features, "f0_mean")
        z = self._z_score(f0_mean_val, mean, std)
        return self._center_optimal_score(z, max_score=10.0, z_zero=2.5)

    def _compute_axis_scores(
        self,
        feats: Dict[str, float],
        language_code: str,
        gender: str = "F",
    ) -> Dict[str, float]:
        """
        6개 raw feature + baseline → 4개 Tone 축 점수 계산
        """
        lang_features = self._get_lang_features(language_code, gender)

        clarity = self._clarity_score(feats, lang_features)
        stability = self._stability_score(feats, lang_features)
        brightness = self._brightness_score(feats, lang_features)
        pitch_position = self._pitch_position_score(feats, lang_features)

        return {
            "clarity": float(clarity),
            "stability": float(stability),
            "brightness": float(brightness),
            "pitch_position": float(pitch_position),
        }

    def _compute_tone_score(
        self,
        axis_scores: Dict[str, float],
        weight_clarity: float,
        weight_stability: float,
        weight_brightness: float,
        weight_pitch_position: float
    ) -> float:
        """
        최종 Tone 점수 = 4개 축 점수의 가중합

        Args:
            axis_scores: 4개 축 점수
            weight_clarity: 명료도 가중치
            weight_stability: 안정성 가중치
            weight_brightness: 밝기 가중치
            weight_pitch_position: 음높이 위치 가중치
        """
        tone_score = (
            weight_clarity * axis_scores["clarity"] +
            weight_stability * axis_scores["stability"] +
            weight_brightness * axis_scores["brightness"] +
            weight_pitch_position * axis_scores["pitch_position"]
        )
        return ToneAnalyzer._clip(tone_score, 0.0, 10.0)
    
    # 3) public API: 파일 경로 기준으로 한 번에 분석

    def analyze(
        self,
        file_path: str,
        language_code: str = "ko-KR",
        gender: str = "F",
        baseline_path: Path = DEFAULT_TONE_BASELINE_PATH,
        weight_clarity: float = 0.4,
        weight_stability: float = 0.3,
        weight_brightness: float = 0.2,
        weight_pitch_position: float = 0.1
    ) -> Dict[str, Any]:
        """
        파일 경로만 받아서 톤 분석을 수행하는 단일 엔트리 포인트.

        Args:
            file_path: 음성 파일 경로
            language_code: 언어 코드 (ko-KR, en-US)
            gender: 성별 (F, M)
            baseline_path: tone baseline JSON 파일 경로
            weight_clarity: 명료도 가중치
            weight_stability: 안정성 가중치
            weight_brightness: 밝기 가중치
            weight_pitch_position: 음높이 위치 가중치

        - 1) baseline(tone_default.json) 로드
        - 2) 오디오 파일 로드
        - 3) 6개 raw feature 추출
        - 4) 4개 Tone 축 점수 계산
        - 5) 최종 tone_score 계산 (가중치 적용)
        """
        # 1) baseline 로드
        self._ensure_baseline_loaded(baseline_path)

        # 2) 오디오 로드
        y, sr = self.load_audio_from_file(file_path)

        # 3) raw feature 추출
        feats = self.extract_tone_features(y, sr)

        # 4) 4개 축 점수 계산
        axis_scores = self._compute_axis_scores(feats, language_code, gender)

        # 5) 최종 tone 점수 계산 (0~10 스케일, 가중치 적용)
        tone_score = self._compute_tone_score(
            axis_scores,
            weight_clarity,
            weight_stability,
            weight_brightness,
            weight_pitch_position
        )

        # 6) 100점으로 normalize (상위 레이어에서 600점 환산 예정)
        normalized_score = tone_score * 10.0

        return {
            "agent": "tone",
            "language_code": language_code,
            "gender": gender,           # 요청 gender 그대로 기록
            "file_path": str(file_path),
            "features": feats,          # 6개 raw feature
            "axis_scores": axis_scores, # clarity / stability / brightness / pitch_position
            # "tone_score": tone_score,   # 0~10점 (추후 600점 환산은 상위 레이어에서)
            "score": round(normalized_score, 2),
        }