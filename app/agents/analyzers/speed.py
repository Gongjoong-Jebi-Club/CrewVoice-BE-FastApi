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
# __file__ is app/agents/analyzers/speed.py
# parent.parent is app/agents
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

    def detect_syllables_parselmouth(self, audio_path: str) -> Tuple[int, List[float]]:
        """Parselmouth를 사용하여 음절 검출"""
        try:
            sound = parselmouth.Sound(audio_path)
            intensity = sound.to_intensity()

            # Intensity 값을 배열로 변환
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

            # 음절 피크 검출
            min_distance_samples = int(0.1 / time_step)

            peaks, properties = find_peaks(
                intensity_array,
                distance=max(1, min_distance_samples),
                prominence=2,
                height=50
            )

            # 피크의 시간 위치 계산
            syllable_times = [start_time + i * time_step for i in peaks]

            return len(peaks), syllable_times

        except Exception as e:
            print(f"Parselmouth 음절 검출 오류: {e}")
            return self._detect_syllables_librosa(audio_path)

    def _detect_syllables_librosa(self, audio_path: str) -> Tuple[int, List[float]]:
        """Librosa를 사용한 음절 검출"""
        y, sr = librosa.load(audio_path)

        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            backtrack=True,
            units='time'
        )

        # 너무 가까운 onset 필터링
        filtered_onsets = []
        for i, onset in enumerate(onsets):
            if i == 0 or onset - filtered_onsets[-1] > 0.1:
                filtered_onsets.append(onset)

        return len(filtered_onsets), filtered_onsets

    def detect_speech_segments(self, audio_path: str, min_silence_len: float = 0.5) -> List[Tuple[float, float]]:
        """음성 구간 검출 (묵음 제거)"""
        y, sr = librosa.load(audio_path)

        intervals = librosa.effects.split(
            y,
            top_db=40,
            frame_length=2048,
            hop_length=512
        )

        # 샘플 인덱스를 시간으로 변환
        time_intervals = []
        for start_sample, end_sample in intervals:
            start_time = start_sample / sr
            end_time = end_sample / sr
            duration = end_time - start_time

            if duration >= 0.1:
                time_intervals.append((start_time, end_time))

        # 가까운 구간들 병합
        merged_intervals = []
        for start, end in time_intervals:
            if merged_intervals and start - merged_intervals[-1][1] < min_silence_len:
                merged_intervals[-1] = (merged_intervals[-1][0], end)
            else:
                merged_intervals.append((start, end))

        # 폴백: 구간이 없으면 전체 오디오를 하나의 구간으로
        if not merged_intervals:
            total_duration = len(y) / sr
            if total_duration > 0.5:
                merged_intervals = [(0.0, total_duration)]

        return merged_intervals

    def _calculate_score(self, overall_rate: float) -> int:
        """발화 속도 점수 계산 (0-100)"""
        mean_rate = (self.OPTIMAL_MIN + self.OPTIMAL_MAX) / 2

        # 최적 범위 내에 있으면 100점
        if self.OPTIMAL_MIN <= overall_rate <= self.OPTIMAL_MAX:
            # 범위 내에서도 중앙값에 가까울수록 100점, 경계에 가까우면 감점
            distance_from_center = abs(overall_rate - mean_rate)
            optimal_range = (self.OPTIMAL_MAX - self.OPTIMAL_MIN) / 2
            # 중앙에서 멀어질수록 최대 5점 감점
            deduction = int((distance_from_center / optimal_range) * 5)
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

    def _generate_evaluation(self, overall_rate: float) -> str:
        """전체 평가 생성"""
        if self.OPTIMAL_MIN <= overall_rate <= self.OPTIMAL_MAX:
            return "매우 좋음 - 적절한 발화 속도를 유지하고 있습니다."
        elif overall_rate < self.SLOW_THRESHOLD:
            return "개선 필요 - 발화 속도가 다소 느립니다."
        elif overall_rate < self.OPTIMAL_MIN:
            return "보통 - 발화 속도가 약간 느린 편입니다."
        elif overall_rate <= self.FAST_THRESHOLD:
            return "보통 - 발화 속도가 약간 빠른 편입니다."
        else:
            return "개선 필요 - 발화 속도가 너무 빠릅니다."

    def _generate_comments(self, overall_rate: float) -> List[str]:
        """상세 코멘트 생성"""
        comments = []

        comments.append(f"전체 발화 속도: {overall_rate:.2f} 음절/초")
        comments.append(f"최적 속도 범위: {self.OPTIMAL_MIN}-{self.OPTIMAL_MAX} 음절/초")

        if overall_rate < self.SLOW_THRESHOLD:
            comments.append("💡 조언: 발화 속도를 높이세요. 문장 간 불필요한 쉼을 줄이고, 더 자연스럽게 말하는 연습이 필요합니다.")
        elif overall_rate > self.FAST_THRESHOLD:
            comments.append("💡 조언: 발화 속도를 늦추세요. 청자가 내용을 이해할 수 있도록 적절한 속도로 말하는 것이 중요합니다.")

        return comments

    def analyze(self, wav_path: str) -> Dict:
        """
        속도 분석 수행

        Args:
            wav_path: WAV 파일 경로

        Returns:
            분석 결과 딕셔너리
        """
        try:
            # 1. 전체 음절 검출
            total_syllables, syllable_times = self.detect_syllables_parselmouth(wav_path)

            # 2. 음성 구간 검출
            speech_intervals = self.detect_speech_segments(wav_path)

            # 3. 전체 발화 시간 계산
            total_speech_duration = sum([end - start for start, end in speech_intervals])

            # 4. 전체 속도 계산
            overall_rate = total_syllables / total_speech_duration if total_speech_duration > 0 else 0

            # 5. 평가 및 코멘트 생성
            score = self._calculate_score(overall_rate)
            evaluation = self._generate_evaluation(overall_rate)
            comments = self._generate_comments(overall_rate)

            return {
                "score": score,
                "max_score": 100,
                "feedback": [evaluation] + comments,
                "status": "success",
                "total_syllables": total_syllables,
                "total_speech_duration": round(total_speech_duration, 2),
                "overall_rate": round(overall_rate, 2),
                "evaluation": evaluation
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": [f"분석 중 오류 발생: {str(e)}"],
                "status": "error"
            }


if __name__ == "__main__":
    # 테스트 코드
    analyzer = SpeedAnalyzer()
    result = analyzer.analyze("test.wav")
    print(json.dumps(result, ensure_ascii=False, indent=2))