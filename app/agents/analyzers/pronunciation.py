"""
Pronunciation Analysis Agent
음성 파일의 발음(Pronunciation) 분석을 수행하는 에이전트
Validate 에이전트에서 생성한 Azure 데이터를 재사용합니다.
"""
import json
from typing import Dict


class PronunciationAnalyzer:
    """발음(Pronunciation) 분석기 - Validate 에이전트의 Azure 데이터 재사용"""

    def __init__(self):
        """초기화 - Azure API 직접 호출하지 않음"""
        pass

    def analyze(
        self,
        wav_path: str,
        reference_text: str = None,
        language_code: str = "ko-KR",
        azure_data: Dict = None
    ) -> Dict:
        """
        발음 분석 수행 (Validate 에이전트의 azure_data 재사용)

        Args:
            wav_path: WAV 파일 경로 (사용 안 함, 호환성 유지용)
            reference_text: 참조 텍스트 (사용 안 함, 호환성 유지용)
            language_code: 언어 코드 (사용 안 함, 호환성 유지용)
            azure_data: Validate 에이전트에서 생성한 Azure 데이터 (필수)

        Returns:
            분석 결과 딕셔너리
        """
        try:
            if not azure_data:
                return {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["Validate 에이전트에서 생성한 Azure 데이터가 필요합니다."],
                    "status": "error"
                }

            return self._analyze_from_azure_data(azure_data)

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": [f"분석 중 오류 발생: {str(e)}"],
                "status": "error"
            }

    def _analyze_from_azure_data(self, azure_data: Dict) -> Dict:
        """
        Validate 에이전트에서 생성한 azure_data로부터 발음 점수 계산

        Args:
            azure_data: Azure Pronunciation Assessment 결과

        Returns:
            발음 분석 결과
        """
        try:
            if not azure_data or 'NBest' not in azure_data:
                return {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["Azure 데이터가 유효하지 않습니다."],
                    "status": "error"
                }

            nbest = azure_data['NBest'][0]
            pron_assessment = nbest.get('PronunciationAssessment', {})

            # 점수 추출
            accuracy_score = pron_assessment.get('AccuracyScore', 0)
            fluency_score = pron_assessment.get('FluencyScore', 0)
            completeness_score = pron_assessment.get('CompletenessScore', 0)
            pron_score = pron_assessment.get('PronScore', 0)

            # 인식된 텍스트
            recognized_text = nbest.get('Display', '')

            # 단어별 상세 평가
            word_details = []
            for word_info in nbest.get('Words', []):
                word_assessment = word_info.get('PronunciationAssessment', {})
                word_details.append({
                    "word": word_info.get('Word', ''),
                    "accuracy_score": word_assessment.get('AccuracyScore', 0)
                })

            return {
                "score": round(pron_score, 2),
                "max_score": 100,
                "feedback": [
                    f"종합 발음 점수: {pron_score:.2f} / 100",
                    f"정확도: {accuracy_score:.2f} / 100",
                    f"유창성: {fluency_score:.2f} / 100",
                    f"완전성: {completeness_score:.2f} / 100"
                ],
                "status": "success",
                "recognized_text": recognized_text,
                "accuracy_score": round(accuracy_score, 2),
                "fluency_score": round(fluency_score, 2),
                "completeness_score": round(completeness_score, 2),
                "word_details": word_details,
                "azure_data": azure_data  # Pause 에이전트용으로 전달
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": [f"Azure 데이터 분석 중 오류: {str(e)}"],
                "status": "error"
            }


if __name__ == "__main__":
    # 테스트 코드
    analyzer = PronunciationAnalyzer()
    result = analyzer.analyze("test.wav", "안녕하세요 테스트입니다")
    print(json.dumps(result, ensure_ascii=False, indent=2))
