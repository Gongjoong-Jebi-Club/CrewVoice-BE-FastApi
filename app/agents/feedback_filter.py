"""
Feedback Filter
음성학적 임계값을 기반으로 개선이 필요한 항목만 필터링
"""
from typing import Dict, Any, List


class FeedbackFilter:
    """
    음성 분석 결과에서 개선이 필요한 항목만 추출하는 필터

    임계값 기준 (음성학적 기준):
    - 우수 (90~100점): 피드백 불필요
    - 양호 (80~89점): 경미한 개선 사항만 표시
    - 보통 (70~79점): 개선 사항 표시
    - 미흡 (60~69점): 상세한 개선 사항 표시
    - 불량 (60점 미만): 매우 상세한 개선 사항 표시
    """

    # 음성학적 임계값 설정
    EXCELLENT_THRESHOLD = 90  # 우수: 피드백 불필요
    GOOD_THRESHOLD = 80       # 양호: 간단한 피드백
    FAIR_THRESHOLD = 70       # 보통: 개선 필요
    POOR_THRESHOLD = 60       # 미흡: 상세 개선 필요

    @staticmethod
    def _get_performance_level(score: float) -> str:
        """점수를 기반으로 성능 레벨 판단"""
        if score >= FeedbackFilter.EXCELLENT_THRESHOLD:
            return "excellent"
        elif score >= FeedbackFilter.GOOD_THRESHOLD:
            return "good"
        elif score >= FeedbackFilter.FAIR_THRESHOLD:
            return "fair"
        elif score >= FeedbackFilter.POOR_THRESHOLD:
            return "poor"
        else:
            return "very_poor"

    @staticmethod
    def _should_show_feedback(score: float) -> bool:
        """피드백을 표시할지 여부 결정"""
        # 80점 미만만 피드백 표시
        return score < FeedbackFilter.GOOD_THRESHOLD

    @staticmethod
    def _filter_agent_feedback(
        agent_name: str,
        score: float,
        feedback: List[str],
        status: str
    ) -> List[str]:
        """
        에이전트별 피드백 필터링

        Args:
            agent_name: 에이전트 이름
            score: 점수
            feedback: 원본 피드백 리스트
            status: 분석 상태

        Returns:
            필터링된 피드백 리스트
        """
        # 에러 상태면 피드백 그대로 반환
        if status != "success":
            return feedback

        # 우수한 경우 피드백 제거
        if not FeedbackFilter._should_show_feedback(score):
            return []

        # 점수 관련 피드백은 제외하고 개선 사항만 추출
        filtered_feedback = []

        # 에이전트별 필터링 규칙
        if agent_name == "pronunciation":
            # "종합", "정확도", "유창성" 등 점수 관련 피드백 제외
            for fb in feedback:
                if not any(keyword in fb for keyword in ["점수:", "/", "Pronunciation"]):
                    filtered_feedback.append(fb)

        elif agent_name == "accent":
            # 긍정적인 피드백 제외
            negative_keywords = ["부족", "개선", "필요", "너무", "적어", "많아", "과도", "단조", "불안정"]
            for fb in feedback:
                # "Stds" 같은 디버그 정보 제외
                if "Stds(" in fb:
                    continue
                # 긍정적인 피드백 제외
                if any(pos in fb for pos in ["좋습니다", "잘 사용", "적절한", "자연스러운"]):
                    continue
                # 개선 필요 사항만 포함
                if any(neg in fb for neg in negative_keywords):
                    filtered_feedback.append(fb)

        elif agent_name == "intonation":
            # 언어, 리듬 타입, 문장 종결 패턴 정보는 제외하고 개선 사항만
            for fb in feedback:
                if any(keyword in fb for keyword in ["개선", "부족", "필요", "부자연", "C등급", "D등급"]):
                    filtered_feedback.append(fb)

        elif agent_name == "pause":
            # 점수 표시 제외, 문제점만
            for fb in feedback:
                if any(keyword in fb for keyword in ["부적절", "문제", "필요", "미흡", "불량"]):
                    filtered_feedback.append(fb)

        elif agent_name == "speed":
            # 평가 제외, 조언만
            for fb in feedback:
                if "💡 조언:" in fb or "개선 필요" in fb:
                    filtered_feedback.append(fb)

        elif agent_name == "tone":
            # Tone은 원본 피드백이 거의 없으므로 그대로 반환
            filtered_feedback = feedback

        return filtered_feedback

    @staticmethod
    def filter_response(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        분석 결과에서 개선이 필요한 항목만 필터링

        Args:
            analysis_result: AgentManager의 분석 결과

        Returns:
            필터링된 응답 (improvements 필드 추가)
        """
        scores = analysis_result.get("scores", {})

        # 개선이 필요한 항목 수집
        improvements = []

        for agent_name, score_info in scores.items():
            score = score_info.get("score", 0)
            feedback = score_info.get("feedback", [])
            status = score_info.get("status", "unknown")

            # 개선이 필요한 경우에만 추가
            if FeedbackFilter._should_show_feedback(score):
                # 피드백 필터링
                filtered_feedback = FeedbackFilter._filter_agent_feedback(
                    agent_name,
                    score,
                    feedback,
                    status
                )

                # 개선 사항이 있는 경우에만 추가
                if filtered_feedback:
                    performance_level = FeedbackFilter._get_performance_level(score)

                    # 한글 에이전트 이름 매핑
                    agent_name_kr = {
                        "pronunciation": "발음",
                        "accent": "강조",
                        "intonation": "억양",
                        "pause": "휴지",
                        "speed": "속도",
                        "tone": "톤"
                    }.get(agent_name, agent_name)

                    improvement_item = {
                        "category": agent_name,
                        "category_kr": agent_name_kr,
                        "score": score,
                        "performance_level": performance_level,
                        "feedback": filtered_feedback
                    }

                    improvements.append(improvement_item)

        # 점수 낮은 순으로 정렬 (가장 개선이 필요한 항목 우선)
        improvements.sort(key=lambda x: x["score"])

        # 기존 응답에 improvements 필드 추가
        filtered_response = {
            "overall_score": analysis_result.get("overall_score", 0),
            "max_score": analysis_result.get("max_score", 100),
            "improvements": improvements,  # 개선 필요 항목만
            "scores": scores,  # 전체 점수는 유지
            "analysis_summary": analysis_result.get("analysis_summary", "")
        }

        # detailed_results는 제외 (너무 길어서)
        # 필요시 옵션으로 제공 가능

        return filtered_response

    @staticmethod
    def get_compact_response(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        가장 간결한 응답 (개선 사항과 전체 점수만)

        Args:
            analysis_result: AgentManager의 분석 결과

        Returns:
            초간결 응답
        """
        filtered = FeedbackFilter.filter_response(analysis_result)

        return {
            "overall_score": filtered["overall_score"],
            "max_score": filtered["max_score"],
            "improvements": filtered["improvements"],
            "summary": filtered["analysis_summary"]
        }
