"""
Pause Analysis Agent
음성 파일의 휴지(Pause) 분석을 수행하는 에이전트
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Azure는 pronunciation 에이전트에서 이미 호출되므로 여기서는 직접 분석


class PauseAnalyzer:
    """휴지(Pause) 분석기"""

    # Pause 임계값 (초)
    MIN_PAUSE_THRESHOLD = 0.15

    # 권장 Pause 길이 (초)
    RECOMMENDED_PAUSE = {
        'after_period': {
            'min': 0.5,
            'max': 4.0,
            'optimal': 0.8
        },
        'after_comma': {
            'min': 0.2,
            'max': 0.9,
            'optimal': 0.4
        },
        'after_question': {
            'min': 0.5,
            'max': 4.0,
            'optimal': 0.7
        },
        'after_exclamation': {
            'min': 0.5,
            'max': 4.0,
            'optimal': 0.7
        }
    }

    def __init__(self):
        pass

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
            elif '?' in word or '?' in word:
                positions['question'].append(i)
            elif '!' in word or '!' in word:
                positions['exclamation'].append(i)
            elif ',' in word or ',' in word:
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
        return context in ['after_period', 'after_comma', 'after_question', 'after_exclamation']

    def evaluate_pause_length(self, pause_sec: float, context: str) -> Tuple[bool, str, str]:
        """Pause 길이 적절성 평가"""
        if context not in self.RECOMMENDED_PAUSE:
            return True, 'neutral', "문장 중간 (평가 안 함)"

        rec = self.RECOMMENDED_PAUSE[context]
        optimal = rec['optimal']
        min_val = rec['min']
        max_val = rec['max']

        diff = abs(pause_sec - optimal)
        diff_percent = diff / optimal

        # 범위 내
        if min_val <= pause_sec <= max_val:
            if diff_percent <= 0.15:
                return True, 'perfect', f"완벽 (최적: {optimal}초)"
            elif diff_percent <= 0.25:
                return True, 'acceptable', f"양호 (최적: {optimal}초)"
            elif pause_sec < optimal * 0.7:
                return True, 'major', f"범위 내지만 너무 짧음 (권장: {min_val}-{max_val}초)"
            else:
                return True, 'minor', f"허용 범위 내 (권장: {min_val}-{max_val}초)"

        # 범위 벗어남
        if pause_sec < min_val:
            shortage = min_val - pause_sec
            if shortage <= 0.05:
                return False, 'minor', f"약간 짧음 (권장: {min_val}-{max_val}초)"
            else:
                return False, 'major', f"너무 짧음 (권장: {min_val}-{max_val}초)"
        else:
            excess = pause_sec - max_val
            if excess <= 0.3:
                return False, 'minor', f"약간 김 (권장: {min_val}-{max_val}초)"
            elif excess <= 1.0:
                return False, 'major', f"너무 김 (권장: {min_val}-{max_val}초)"
            else:
                return False, 'critical', f"심각하게 김 (권장: {min_val}-{max_val}초)"

    def evaluate_fluency_score(self, fluency_score: float) -> Tuple[float, List[str], str]:
        """FluencyScore → 10점 환산"""
        issues = []
        level = ""

        if fluency_score >= 95:
            score = 10.0
            level = "완벽"
        elif fluency_score >= 90:
            score = 9.0
            level = "우수"
            issues.append("미세한 유창성 개선 가능")
        elif fluency_score >= 85:
            score = 8.0
            level = "양호"
            issues.append("일부 끊어읽기 또는 망설임 발견")
        elif fluency_score >= 80:
            score = 7.0
            level = "보통"
            issues.append("부자연스러운 끊어읽기 주의 필요")
        elif fluency_score >= 75:
            score = 5.0
            level = "미흡"
            issues.append("전반적인 유창성 개선 필요")
        elif fluency_score >= 70:
            score = 3.0
            level = "불량"
            issues.append("어절 단위 읽기 또는 반복 다수 발견")
        else:
            score = 1.0
            level = "매우 불량"
            issues.append("기내방송 수준 미달 - 전면 재연습 필요")

        return score, issues, level

    def analyze(self, wav_path: str, azure_data: Dict = None, reference_script: str = None) -> Dict:
        """
        Pause 분석 수행

        Args:
            wav_path: WAV 파일 경로
            azure_data: Azure 분석 결과 (Pronunciation 에이전트에서 받음)
            reference_script: 참조 스크립트

        Returns:
            분석 결과 딕셔너리
        """
        try:
            if not azure_data or 'NBest' not in azure_data or len(azure_data['NBest']) == 0:
                return {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["Azure 데이터 없음 - 분석 불가"],
                    "status": "error"
                }

            nbest = azure_data['NBest'][0]

            # 1차 평가: FluencyScore
            pron_assessment = nbest.get('PronunciationAssessment', {})
            fluency_score = pron_assessment.get('FluencyScore', 0)
            fluency_converted, fluency_issues, fluency_level = self.evaluate_fluency_score(fluency_score)

            # 참조 스크립트가 없으면 기본 분석만 수행
            if not reference_script:
                return {
                    "score": fluency_converted * 10,  # 100점 만점으로 환산
                    "max_score": 100,
                    "feedback": [
                        f"유창성 점수: {fluency_converted:.1f} / 10.0",
                        f"수준: {fluency_level}"
                    ] + fluency_issues,
                    "status": "success",
                    "fluency_score": fluency_converted,
                    "fluency_level": fluency_level
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
            perfect_pauses = 0
            acceptable_pauses = 0
            minor_issues = 0
            major_issues = 0
            critical_issues = 0

            for i, word in enumerate(words):
                word_text = word.get('Word', '')
                offset = word.get('Offset', 0)
                duration = word.get('Duration', 0)

                start_time = offset / 1000000
                duration_sec = duration / 1000000
                end_time = start_time + duration_sec

                if i < len(words) - 1:
                    next_word = words[i + 1]
                    next_offset = next_word.get('Offset', 0)
                    next_start = next_offset / 1000000
                    pause_sec = next_start - end_time

                    if pause_sec >= self.MIN_PAUSE_THRESHOLD:
                        script_word_idx = min(i, total_reference_words - 1)
                        context = self.classify_pause_context(script_word_idx, punctuation_positions)
                        is_good = self.is_good_pause(context)
                        length_appropriate, severity, length_comment = self.evaluate_pause_length(pause_sec, context)

                        if is_good:
                            good_pauses += 1
                            if severity == 'perfect':
                                perfect_pauses += 1
                            elif severity == 'acceptable':
                                acceptable_pauses += 1
                            elif severity == 'minor':
                                minor_issues += 1
                            elif severity == 'major':
                                major_issues += 1
                        else:
                            bad_pauses += 1
                            if pause_sec > 0.5:
                                critical_issues += 1
                            else:
                                major_issues += 1

                        pause_details.append({
                            'word_index': i + 1,
                            'after_word': word_text,
                            'pause_sec': round(pause_sec, 3),
                            'context': context,
                            'is_good': is_good,
                            'severity': severity,
                            'comment': length_comment if is_good else "[X] 부적절한 위치"
                        })

            # 2차 평가: Pause 위치 점수
            total_pauses = good_pauses + bad_pauses
            if total_pauses > 0:
                good_pause_ratio = good_pauses / total_pauses
                if good_pause_ratio >= 0.95:
                    position_score = 5.0
                elif good_pause_ratio >= 0.90:
                    position_score = 4.5
                elif good_pause_ratio >= 0.85:
                    position_score = 4.0
                elif good_pause_ratio >= 0.80:
                    position_score = 3.5
                elif good_pause_ratio >= 0.75:
                    position_score = 3.0
                else:
                    position_score = 2.0
            else:
                position_score = 5.0
                good_pause_ratio = 1.0

            # Pause 길이 점수
            if good_pauses > 0:
                perfect_ratio = perfect_pauses / good_pauses
                good_ratio = (perfect_pauses + acceptable_pauses + minor_issues) / good_pauses

                if perfect_ratio >= 0.80:
                    length_score = 5.0
                elif perfect_ratio >= 0.60:
                    length_score = 4.5
                elif good_ratio >= 0.90:
                    length_score = 4.0
                elif good_ratio >= 0.80:
                    length_score = 3.5
                else:
                    length_score = 3.0

                major_ratio = major_issues / good_pauses if good_pauses > 0 else 0
                if critical_issues >= good_pauses * 0.3:
                    length_score = max(1.0, length_score - 2.0)
                elif critical_issues > 0:
                    length_score = max(1.0, length_score - 1.0)

                if major_ratio >= 0.30:
                    length_score = max(1.0, length_score - 1.5)
                elif major_ratio >= 0.10:
                    length_score = max(1.0, length_score - 1.0)
            else:
                length_score = 5.0

            # 총점 계산 (20점 만점)
            total_score = fluency_converted + position_score + length_score

            # 피드백 생성
            feedback = [
                f"유창성: {fluency_converted:.1f}/10.0점 ({fluency_level})",
                f"Pause 위치: {position_score:.1f}/5.0점 (적절한 위치: {good_pauses}/{total_pauses})",
                f"Pause 길이: {length_score:.1f}/5.0점"
            ]

            if bad_pauses > 0:
                feedback.append(f"부적절한 위치 pause: {bad_pauses}개")
            if major_issues > 0:
                feedback.append(f"주요 문제: {major_issues}개")
            if critical_issues > 0:
                feedback.append(f"심각한 문제: {critical_issues}개")

            # 20점을 100점 만점으로 환산
            normalized_score = (total_score / 20) * 100

            return {
                "score": round(normalized_score, 2),
                "max_score": 100,
                "feedback": feedback,
                "status": "success",
                "fluency_score": fluency_converted,
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


if __name__ == "__main__":
    # 테스트 코드
    analyzer = PauseAnalyzer()
    result = analyzer.analyze("test.wav")
    print(json.dumps(result, ensure_ascii=False, indent=2))
