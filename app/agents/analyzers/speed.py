"""
Speed Analysis Agent
음성 파일의 속도(Speed) 분석을 수행하는 에이전트

Baseline을 파일(speed_default.json)에서 로드하여 사용합니다.
"""
import json
import parselmouth
import librosa
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from scipy.signal import find_peaks

# 기존 코드 경로 추가
BASE_DIR = Path(__file__).parent.parent

# speed baseline JSON 기본 경로
DEFAULT_SPEED_BASELINE_PATH = BASE_DIR / "baselines" / "speed_default.json"

class SpeedAnalyzer:
    """속도(Speed) 분석기"""

    def __init__(self, baseline_path: Path = DEFAULT_SPEED_BASELINE_PATH):
        """
        Args:
            baseline_path: Baseline JSON 파일 경로
        """
        self.baseline_path = baseline_path
        self._baseline: Optional[Dict] = None
        self._load_baseline()

    def _load_baseline(self):
        """Baseline JSON 파일 로드"""
        if not self.baseline_path.exists():
            raise FileNotFoundError(
                f"Speed baseline 파일을 찾을 수 없습니다: {self.baseline_path}\n"
                f"BaselineManager를 사용하여 먼저 baseline을 생성하세요."
            )

        with open(self.baseline_path, 'r', encoding='utf-8') as f:
            self._baseline = json.load(f)

        # Baseline 통계 추출
        stats = self._baseline["statistics"]
        self.OPTIMAL_MIN = stats["optimal_min"]
        self.OPTIMAL_MAX = stats["optimal_max"]
        self.SLOW_THRESHOLD = stats["slow_threshold"]
        self.FAST_THRESHOLD = stats["fast_threshold"]

    def _calculate_score(self, overall_rate: float, max_deduction: float = 5.0) -> int:
        """
        발화 속도 점수 계산 (0-100)
        
        Args:
            overall_rate: 발화 속도 (음절/초)
            max_deduction: 편차 허용도 (5~10%)
                - 5: 엄격 (중앙값 편차에 최대 5점 감점)
                - 10: 관대 (중앙값 편차에 최대 10점 감점, 감점 적음)
        """
        # max_deduction을 5~10 범위로 제한
        max_deduction = max(5.0, min(10.0, max_deduction))
        
        mean_rate = (self.OPTIMAL_MIN + self.OPTIMAL_MAX) / 2

        # 최적 범위 내에 있으면 100점
        if self.OPTIMAL_MIN <= overall_rate <= self.OPTIMAL_MAX:
            # 범위 내에서도 중앙값에 가까울수록 100점, 경계에 가까우면 감점
            distance_from_center = abs(overall_rate - mean_rate)
            optimal_range = (self.OPTIMAL_MAX - self.OPTIMAL_MIN) / 2
            # 중앙에서 멀어질수록 감점 (허용도가 높을수록 감점 적음)
            # max_deduction이 5(엄격)일 때: 최대 5점 감점
            # max_deduction이 10(관대)일 때: 최대 2.5점 감점
            deduction = int((distance_from_center / optimal_range) * (15.0 - max_deduction))
            return 100 - deduction

        # 최적 범위 밖: 거리에 비례하여 점수 감소
        if overall_rate < self.OPTIMAL_MIN:
            # 느린 경우
            distance = self.OPTIMAL_MIN - overall_rate
            # SLOW_THRESHOLD 이하면 50점 이하
            if overall_rate <= self.SLOW_THRESHOLD:
                # SLOW_THRESHOLD 기준으로 추가 감점
                extra_distance = self.SLOW_THRESHOLD - overall_rate
                base_score = max(0, 50 - int(extra_distance * 30))
            else:
                # OPTIMAL_MIN과 SLOW_THRESHOLD 사이: 95 ~ 50점
                range_size = self.OPTIMAL_MIN - self.SLOW_THRESHOLD
                base_score = 95 - int((distance / range_size) * 45)
        else:
            # 빠른 경우
            distance = overall_rate - self.OPTIMAL_MAX
            # FAST_THRESHOLD 이상이면 50점 이하
            if overall_rate >= self.FAST_THRESHOLD:
                # FAST_THRESHOLD 기준으로 추가 감점
                extra_distance = overall_rate - self.FAST_THRESHOLD
                base_score = max(0, 50 - int(extra_distance * 30))
            else:
                # OPTIMAL_MAX와 FAST_THRESHOLD 사이: 95 ~ 50점
                range_size = self.FAST_THRESHOLD - self.OPTIMAL_MAX
                base_score = 95 - int((distance / range_size) * 45)

        return max(0, min(100, base_score))

    def analyze(self, wav_path: str, max_deduction: float = 5.0) -> Dict:
        """
        속도 분석 수행

        Args:
            wav_path: WAV 파일 경로
            max_deduction: 최적 범위 내 중앙값 편차에 따른 최대 감점 (기본값: 5.0)

        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 1. 전체 음절 검출 (Parselmouth)
            sound = parselmouth.Sound(wav_path)
            intensity = sound.to_intensity()

            intensity_values = []
            time_step = intensity.time_step
            start_time = intensity.xmin
            num_frames = intensity.nx

            for i in range(num_frames):
                time = start_time + i * time_step
                value = intensity.get_value(time)
                if value is not None and not np.isnan(value):
                    intensity_values.append(value)
                else:
                    intensity_values.append(0)

            intensity_array = np.array(intensity_values)
            min_distance_samples = int(0.1 / time_step)

            peaks, _ = find_peaks(
                intensity_array,
                distance=max(1, min_distance_samples),
                prominence=2,
                height=50
            )
            total_syllables = len(peaks)

            # 2. 음성 구간 검출 (librosa)
            y, sr = librosa.load(wav_path, sr=None)
            intervals = librosa.effects.split(y, top_db=40, frame_length=2048, hop_length=512)

            time_intervals = []
            for start_sample, end_sample in intervals:
                start_t = start_sample / sr
                end_t = end_sample / sr
                duration = end_t - start_t
                if duration >= 0.1:
                    time_intervals.append((start_t, end_t))

            # 3. 가까운 구간 병합
            merged_intervals = []
            for start, end in time_intervals:
                if merged_intervals and start - merged_intervals[-1][1] < 0.5:
                    merged_intervals[-1] = (merged_intervals[-1][0], end)
                else:
                    merged_intervals.append((start, end))

            if not merged_intervals:
                total_duration = len(y) / sr
                if total_duration > 0.5:
                    merged_intervals = [(0.0, total_duration)]

            # 4. 발화 시간 계산
            total_speech_duration = sum([end - start for start, end in merged_intervals])

            # 5. 전체 속도 계산
            overall_rate = total_syllables / total_speech_duration if total_speech_duration > 0 else 0

            # 6. 점수 계산
            score = self._calculate_score(overall_rate, max_deduction)

            return {
                "score": score,
                "max_score": 100,
                "status": "success",
                "total_syllables": total_syllables,
                "total_speech_duration": round(total_speech_duration, 2),
                "overall_rate": round(overall_rate, 2),
                "optimal_range": f"{self.OPTIMAL_MIN}-{self.OPTIMAL_MAX}"
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "status": "error",
                "error_message": str(e)
            }