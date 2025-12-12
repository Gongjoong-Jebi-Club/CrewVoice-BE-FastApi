"""
Pause Analysis Agent
음성 파일의 휴지(Pause) 분석을 수행하는 에이전트
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

# Azure는 pronunciation 에이전트에서 이미 호출되므로 여기서는 직접 분석

# 기존 코드 경로 추가
BASE_DIR = Path(__file__).parent.parent

# pause baseline JSON 기본 경로
DEFAULT_PAUSE_BASELINE_PATH = BASE_DIR / "baselines" / "pause_default.json"


class PauseAnalyzer:
    """휴지(Pause) 분석기"""

    # Pause 임계값 기본값 (baseline이 없을 때 사용)
    DEFAULT_MIN_PAUSE_THRESHOLD = 0.15

    def __init__(self):
        self._baseline: Optional[Dict[str, Any]] = None  # pause baseline 데이터 저장용

    def extract_punctuation_positions(self, script_text: str) -> Dict[str, List[int]]:
        """정답 스크립트에서 문장부호 위치 추출"""
        words = script_text.split()

        positions = {
            'period': [],
            'comma': [],
            'question': [],
            'exclamation': []
        }

        for i, word in enumerate(words):
            if '.' in word or '。' in word:
                positions['period'].append(i)
            elif '?' in word or '？' in word:  # U+003F (반각), U+FF1F (전각)
                positions['question'].append(i)
            elif '!' in word or '！' in word:  # U+0021 (반각), U+FF01 (전각)
                positions['exclamation'].append(i)
            elif ',' in word or '、' in word:  # U+002C (반각), U+3001 (전각)
                positions['comma'].append(i)

        return positions

    def classify_pause_context(self, word_index: int, punctuation_positions: Dict[str, List[int]]) -> str:
        """Pause 발생 위치의 문맥 분류"""
        if word_index in punctuation_positions['period']:
            return 'after_period'
        elif word_index in punctuation_positions['comma']:
            return 'after_comma'
        elif word_index in punctuation_positions['question']:
            return 'after_question'
        elif word_index in punctuation_positions['exclamation']:
            return 'after_exclamation'
        else:
            return 'mid_phrase'

    def is_good_pause(self, context: str) -> bool:
        """Good Pause 여부 판단"""
        return context in ['after_period', 'after_comma', 'after_question', 'after_exclamation', 'mid_phrase_breath']

    # ------------------------------------------------------------------
    # Baseline 로딩 및 통계 접근 로직
    # ------------------------------------------------------------------

    def _ensure_baseline_loaded(
        self,
        baseline_path: Path = DEFAULT_PAUSE_BASELINE_PATH,
    ) -> None:
        """pause_default.json을 한 번만 로드"""
        if self._baseline is None:
            with open(baseline_path, "r", encoding="utf-8") as f:
                self._baseline = json.load(f)

    def _get_context_features(
        self,
        language_code: str,
        context: str,
    ) -> Dict[str, Dict[str, float]]:
        """
        baseline에서 context별 feature 통계를 가져오는 함수.

        구조:
            baseline["languages"][language_code]["contexts"][context]["features"]

        Returns:
            {
                "pause_sec": {"mean": 0.75, "std": 0.22},
                "prev_phrase_duration_sec": {"mean": 4.2, "std": 1.1},
                "words_since_last_pause": {"mean": 12.5, "std": 3.2}
            }
        """
        if self._baseline is None:
            raise RuntimeError("Baseline is not loaded. Call _ensure_baseline_loaded() first.")

        langs = self._baseline.get("languages", {})
        if language_code not in langs:
            raise ValueError(f"Language '{language_code}' not found in pause baseline.")

        contexts = langs[language_code].get("contexts", {})
        if context not in contexts:
            raise ValueError(f"Context '{context}' not found for language '{language_code}' in pause baseline.")

        return contexts[context]["features"]

    @staticmethod
    def _get_feature_stats(
        context_features: Dict[str, Dict[str, float]],
        feature_name: str,
    ) -> Tuple[float, float]:
        """각 feature에 대해 baseline에서의 평균(mean)과 표준편차(std)를 반환"""
        stats = context_features[feature_name]
        return stats["mean"], stats["std"]

    def _get_min_pause_threshold(self, language_code: str) -> float:
        """
        Baseline에서 언어별 최소 pause 임계값 가져오기

        Args:
            language_code: 언어 코드 (예: ko-KR)

        Returns:
            최소 pause 임계값 (초)
        """
        if self._baseline is None:
            raise RuntimeError("Baseline is not loaded. Call _ensure_baseline_loaded() first.")

        threshold = self._baseline["languages"][language_code]["min_pause_threshold"]
        return float(threshold)

    def _get_mid_phrase_breath_criteria(self, language_code: str) -> Tuple[Optional[float], Optional[int]]:
        """
        Baseline에서 언어별 mid_phrase_breath 판단 기준 가져오기

        Args:
            language_code: 언어 코드 (예: ko-KR)

        Returns:
            (min_prev_phrase_duration_sec, min_words_since_last_pause) 튜플
            값이 없으면 None 반환
        """
        if self._baseline is None:
            raise RuntimeError("Baseline is not loaded. Call _ensure_baseline_loaded() first.")

        criteria = self._baseline["languages"][language_code].get("mid_phrase_breath_criteria")
        if not criteria:
            return None, None

        min_duration = criteria.get("min_prev_phrase_duration_sec")
        min_words = criteria.get("min_words_since_last_pause")

        return (
            float(min_duration) if min_duration is not None else None,
            int(min_words) if min_words is not None else None
        )

    def _get_good_pause_ratio_stats(self, language_code: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Baseline에서 언어별 good_pause_ratio 통계 가져오기

        Args:
            language_code: 언어 코드 (예: ko-KR)

        Returns:
            (mean, std) 튜플
            값이 없으면 (None, None) 반환
        """
        if self._baseline is None:
            raise RuntimeError("Baseline is not loaded. Call _ensure_baseline_loaded() first.")

        stats = self._baseline["languages"][language_code].get("good_pause_ratio")
        if not stats:
            return None, None

        mean = stats.get("mean")
        std = stats.get("std")

        return (
            float(mean) if mean is not None else None,
            float(std) if std is not None else None
        )

    # ------------------------------------------------------------------
    # Z-score 계산 및 점수 변환 함수
    # ------------------------------------------------------------------

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
        return PauseAnalyzer._clip(score, 0.0, max_score)

    @staticmethod
    def _higher_is_better_score(
        z: float,
        max_score: float = 10.0,
        z_zero: float = -2.5,
        z_full: float = 0.5,
    ) -> float:
        """
        높을수록 좋은 지표를 위한 점수 함수

        z ≥ z_full → max_score (만점)
        z_zero < z < z_full → 선형 증가
        z ≤ z_zero → 0점
        """
        # 만점 범위 (평균 이상)
        if z >= z_full:
            return max_score

        # 0점 범위 (너무 낮음)
        if z <= z_zero:
            return 0.0

        # z_zero ~ z_full 사이에서 선형 증가
        ratio = (z - z_zero) / (z_full - z_zero)
        score = max_score * ratio
        return PauseAnalyzer._clip(score, 0.0, max_score)

    # ------------------------------------------------------------------
    # Baseline 기반 Pause 평가
    # ------------------------------------------------------------------

    def evaluate_pause_with_baseline(
        self,
        pause_sec: float,
        context: str,
        prev_phrase_duration_sec: float,
        words_since_last_pause: int,
        language_code: str = "ko-KR",
    ) -> Tuple[bool, float, float]:
        """
        Baseline 통계를 활용한 Pause 평가

        Returns:
            (is_good, pause_total_score, z_pause)
        """
        # mid_phrase (bad pause)는 평가하지 않음
        if context == 'mid_phrase':
            return False, 0.0, 0.0

        try:
            context_features = self._get_context_features(language_code, context)
        except ValueError:
            # baseline에 해당 context가 없으면 중립 평가
            return True, 5.0, 0.0

        # 1) pause_sec 평가
        pause_mean, pause_std = self._get_feature_stats(context_features, "pause_sec")
        z_pause = self._z_score(pause_sec, pause_mean, pause_std)
        pause_score = self._center_optimal_score(z_pause, max_score=10.0, z_zero=2.5, z_full=0.5)

        # 2) prev_phrase_duration_sec 평가 (선택적)
        if "prev_phrase_duration_sec" in context_features:
            phrase_mean, phrase_std = self._get_feature_stats(context_features, "prev_phrase_duration_sec")
            z_phrase = self._z_score(prev_phrase_duration_sec, phrase_mean, phrase_std)
            phrase_score = self._center_optimal_score(z_phrase, max_score=10.0, z_zero=2.5, z_full=0.5)
        else:
            phrase_score = 10.0

        # 3) words_since_last_pause 평가 (선택적)
        if "words_since_last_pause" in context_features:
            words_mean, words_std = self._get_feature_stats(context_features, "words_since_last_pause")
            z_words = self._z_score(float(words_since_last_pause), words_mean, words_std)
            words_score = self._center_optimal_score(z_words, max_score=10.0, z_zero=2.5, z_full=0.5)
        else:
            words_score = 10.0

        # 종합 점수 (가중 평균) - 개별 pause의 점수
        pause_total_score = (
            0.6 * pause_score +      # pause 길이가 가장 중요
            0.2 * phrase_score +     # 발화 길이
            0.2 * words_score        # 단어 수
        )

        is_good = self.is_good_pause(context)
        return is_good, pause_total_score, z_pause


    def analyze(
        self,
        wav_path: str,
        azure_data: Dict = None,
        reference_script: str = None,
        validation_result: Dict = None,
        language_code: str = "ko-KR",
        baseline_path: Path = DEFAULT_PAUSE_BASELINE_PATH,
        weight_fluency: float = 0.7,
        weight_position: float = 0.2,
        weight_length: float = 0.1
    ) -> Dict:
        """
        Pause 분석 수행

        Args:
            wav_path: WAV 파일 경로
            azure_data: Azure 분석 결과 (단어별 상세용)
            reference_script: 참조 스크립트
            validation_result: Validate 에이전트의 결과 (가중 평균 FluencyScore 포함)
            language_code: 언어 코드 (기본값: ko-KR)
            baseline_path: Baseline JSON 파일 경로

        Returns:
            분석 결과 딕셔너리
        """
        try:
            # Baseline 로드
            self._ensure_baseline_loaded(baseline_path)
            if not azure_data or 'NBest' not in azure_data or len(azure_data['NBest']) == 0:
                return {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["Azure 데이터 없음 - 분석 불가"],
                    "status": "error"
                }

            nbest = azure_data['NBest'][0]

            # 1차 평가: FluencyScore (Validate의 가중 평균 사용)
            if validation_result:
                # ✅ Validate에서 계산한 가중 평균 FluencyScore 사용 (전체 세그먼트 반영)
                fluency_score = validation_result.get('fluency_score', 0)
            else:
                # Fallback: azure_data 사용 (첫 세그먼트만 - 부정확)
                pron_assessment = nbest.get('PronunciationAssessment', {})
                fluency_score = pron_assessment.get('FluencyScore', 0)

            # 참조 스크립트가 없으면 기본 분석만 수행
            if not reference_script:
                return {
                    "score": round(fluency_score, 2),  # 100점 만점 그대로 사용
                    "max_score": 100,
                    "feedback": [
                        f"유창성 점수: {fluency_score:.1f} / 100.0"
                    ],
                    "status": "success",
                    "fluency_score": fluency_score
                }

            # 정답 스크립트의 문장부호 위치 추출
            punctuation_positions = self.extract_punctuation_positions(reference_script)
            reference_words = reference_script.split()
            total_reference_words = len(reference_words)

            # 사용자 발화 단어별 분석
            words = nbest.get('Words', [])
            recognized_text = nbest.get('Display', '')

            # Pause 데이터 수집
            pause_details = []
            good_pauses = 0
            bad_pauses = 0

            # 새로운 feature 추적 변수
            prev_phrase_start_time = 0.0  # 직전 pause 이후 시작 시간
            words_since_last_pause = 0    # 직전 pause 이후 단어 수

            # Baseline에서 최소 pause 임계값 가져오기
            min_pause_threshold = self._get_min_pause_threshold(language_code)

            # Baseline에서 mid_phrase_breath 판단 기준 가져오기
            min_breath_duration, min_breath_words = self._get_mid_phrase_breath_criteria(language_code)

            for i, word in enumerate(words):
                word_text = word.get('Word', '')
                offset = word.get('Offset', 0)
                duration = word.get('Duration', 0)

                start_time = offset / 1000000
                duration_sec = duration / 1000000
                end_time = start_time + duration_sec

                # 단어 카운트 증가
                words_since_last_pause += 1

                if i < len(words) - 1:
                    next_word = words[i + 1]
                    next_offset = next_word.get('Offset', 0)
                    next_start = next_offset / 1000000
                    pause_sec = next_start - end_time

                    if pause_sec >= min_pause_threshold:
                        # Feature 3: prev_phrase_duration_sec 계산
                        prev_phrase_duration_sec = end_time - prev_phrase_start_time

                        script_word_idx = min(i, total_reference_words - 1)
                        context = self.classify_pause_context(script_word_idx, punctuation_positions)

                        # context 세분화: mid_phrase_breath 판단 (baseline 기반)
                        if context == 'mid_phrase':
                            # baseline에서 가져온 임계값 사용
                            if min_breath_duration is not None and min_breath_words is not None:
                                if prev_phrase_duration_sec >= min_breath_duration or words_since_last_pause >= min_breath_words:
                                    context = 'mid_phrase_breath'
                            elif min_breath_duration is not None:
                                if prev_phrase_duration_sec >= min_breath_duration:
                                    context = 'mid_phrase_breath'
                            elif min_breath_words is not None:
                                if words_since_last_pause >= min_breath_words:
                                    context = 'mid_phrase_breath'

                        # Baseline 기반 평가
                        is_good, pause_total_score, z_pause = self.evaluate_pause_with_baseline(
                            pause_sec=pause_sec,
                            context=context,
                            prev_phrase_duration_sec=prev_phrase_duration_sec,
                            words_since_last_pause=words_since_last_pause,
                            language_code=language_code,
                        )

                        if is_good:
                            good_pauses += 1
                        else:
                            bad_pauses += 1

                        pause_details.append({
                            'word_index': i + 1,
                            'after_word': word_text,
                            'pause_sec': round(pause_sec, 3),
                            'context': context,
                            'prev_phrase_duration_sec': round(prev_phrase_duration_sec, 3),
                            'words_since_last_pause': words_since_last_pause,
                            'is_good': is_good,
                            'pause_total_score': round(pause_total_score, 2),
                            'z_pause': round(z_pause, 2)
                        })

                        # 다음 phrase를 위한 초기화
                        prev_phrase_start_time = next_start
                        words_since_last_pause = 0

            # 2차 평가: Pause 위치 점수 (z-score 기반)
            total_pauses = good_pauses + bad_pauses
            if total_pauses > 0:
                good_pause_ratio = good_pauses / total_pauses

                # Baseline에서 통계 가져오기
                ratio_mean, ratio_std = self._get_good_pause_ratio_stats(language_code)

                if ratio_mean is not None and ratio_std is not None:
                    # z-score 계산 및 점수 변환
                    z = self._z_score(good_pause_ratio, ratio_mean, ratio_std)
                    # 높을수록 좋은 지표이므로 higher_is_better 사용
                    position_score = self._higher_is_better_score(z, max_score=10.0, z_zero=-2.5, z_full=0.5)
                else:
                    # baseline 통계가 없으면 중립 점수
                    position_score = 5.0
            else:
                position_score = 10.0
                good_pause_ratio = 1.0
# ============================================================================================================
            # # 3차 평가: Pause 길이 점수 (good pause들의 pause_total_score 평균)
            # if total_pauses == 0:
            #     # pause가 아예 없는 경우 (매우 빠르게 말함)
            #     length_score = 5.0
            # elif good_pauses > 0:
            #     # good pause가 있는 경우: pause_total_score 평균 사용
            #     good_pause_scores = [p['pause_total_score'] for p in pause_details if p['is_good']]
            #     avg_pause_score = sum(good_pause_scores) / len(good_pause_scores)
            #     length_score = avg_pause_score / 2.0  # 0-5점 스케일
            # else:
            #     # total_pauses > 0이지만 good_pauses == 0 (모두 bad pause)
            #     length_score = 0.0
            
            # 3차 평가: Pause 길이 점수 (good pause들의 pause_total_score 평균, outlier 완화)
            if total_pauses == 0:
                # pause가 아예 없는 경우 (매우 빠르게 말함)
                length_score = 5.0
            elif good_pauses > 0:
                # good pause 중에서 outlier(너무 긴/짧은) 제거를 고려
                good_pauses_list = [p for p in pause_details if p['is_good']]

                # 1차 후보: |z_pause| <= 3.0 인 것만 사용 (baseline에서 3σ 안쪽)
                inlier_scores = [
                    p['pause_total_score']
                    for p in good_pauses_list
                    if abs(p.get('z_pause', 0.0)) <= 3.0
                ]

                # 만약 전부 outlier로 빠져서 비어버리면 → 전체 good pause로 다시 계산
                if not inlier_scores:
                    inlier_scores = [p['pause_total_score'] for p in good_pauses_list]

                avg_pause_score = sum(inlier_scores) / len(inlier_scores)
                length_score = avg_pause_score / 2.0  # 0-5점 스케일
            else:
                # total_pauses > 0이지만 good_pauses == 0 (모두 bad pause)
                length_score = 0.0
# ============================================================================================================

            # 총점 계산 (100점 만점)
            # fluency_score(0-100) + position_score(0-10) + length_score(0-5)를 100점 만점으로 통합
            total_score = (
                fluency_score * weight_fluency +           # 유창성
                position_score * 10 * weight_position +    # pause 위치 (10점 → 100점 스케일)
                length_score * 20 * weight_length          # pause 길이 (5점 → 100점 스케일)
            )

            # 피드백 생성
            feedback = [
                f"유창성: {fluency_score:.1f}/100.0점",
                f"Pause 위치: {position_score:.1f}/10.0점 (적절한 위치: {good_pauses}/{total_pauses})",
                f"Pause 길이: {length_score:.1f}/5.0점"
            ]

            if bad_pauses > 0:
                feedback.append(f"부적절한 위치 pause: {bad_pauses}개")

            return {
                "score": round(total_score, 2),
                "max_score": 100,
                "feedback": feedback,
                "status": "success",
                "fluency_score": fluency_score,
                "position_score": position_score,
                "length_score": length_score,
                "total_pauses": total_pauses,
                "good_pauses": good_pauses,
                "bad_pauses": bad_pauses,
                "pause_details": pause_details
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": [f"분석 중 오류 발생: {str(e)}"],
                "status": "error"
            }