"""
Agent Manager
음성 분석 모듈들을 AI Agent 구조로 orchestrate하는 매니저
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

# asr_module을 import하기 위한 경로 추가
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from asr_module.accent import AccentAnalyzer
from asr_module.intonation import IntonationAnalyzer
from asr_module.pause import PauseAnalyzer
from asr_module.pronunciation import PronunciationAnalyzer
from asr_module.speed import SpeedAnalyzer
from asr_module.tone import ToneAnalyzer


class AgentManager:
    """
    음성 분석 AI Agent Manager

    6개의 분석 에이전트를 관리하고 조율합니다:
    - Pronunciation (발음)
    - Accent (강조)
    - Intonation (억양)
    - Pause (휴지)
    - Speed (속도)
    - Tone (톤)
    """

    def __init__(self):
        """에이전트 초기화"""
        self.pronunciation_agent = None
        self.accent_agent = AccentAnalyzer()
        self.intonation_agent = IntonationAnalyzer()
        self.pause_agent = PauseAnalyzer()
        self.speed_agent = None
        self.tone_agent = ToneAnalyzer()

        # ThreadPoolExecutor for async operations
        self.executor = ThreadPoolExecutor(max_workers=6)

    def _initialize_pronunciation_agent(self):
        """Pronunciation Agent 지연 초기화 (Azure 키 필요)"""
        if self.pronunciation_agent is None:
            try:
                self.pronunciation_agent = PronunciationAnalyzer()
            except ValueError as e:
                print(f"Warning: PronunciationAnalyzer 초기화 실패 - {e}")
                self.pronunciation_agent = None

    def _initialize_speed_agent(self):
        """Speed Agent 지연 초기화 (baseline 계산 필요)"""
        if self.speed_agent is None:
            try:
                self.speed_agent = SpeedAnalyzer()
            except Exception as e:
                print(f"Warning: SpeedAnalyzer 초기화 실패 - {e}")
                self.speed_agent = None

    async def analyze_all(
        self,
        wav_path: str,
        reference_text: Optional[str] = None,
        language_code: str = "ko-KR",
        gender: str = "F",
    ) -> Dict[str, Any]:
        """
        모든 에이전트를 실행하여 종합 분석 수행

        Args:
            wav_path: WAV 파일 경로
            reference_text: 참조 텍스트 (선택사항)
            language_code: 언어 코드 (ko-KR, en-US 등)
            gender: 성별 (F, M)

        Returns:
            통합된 분석 결과 딕셔너리
        """
        # 지연 초기화
        self._initialize_pronunciation_agent()
        self._initialize_speed_agent()

        # 각 에이전트의 분석 결과를 저장할 딕셔너리
        results = {}

        # 1. Pronunciation 분석 (Azure 기반 - 다른 에이전트에 데이터 제공)
        azure_data = None
        if self.pronunciation_agent:
            try:
                pron_result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: self.pronunciation_agent.analyze(
                        wav_path,
                        reference_text,
                        language_code
                    )
                )
                results["pronunciation"] = pron_result
                azure_data = pron_result.get("azure_data")
            except Exception as e:
                results["pronunciation"] = {
                    "score": 0,
                    "max_score": 100,
                    "feedback": [f"발음 분석 실패: {str(e)}"],
                    "status": "error"
                }
        else:
            results["pronunciation"] = {
                "score": 0,
                "max_score": 100,
                "feedback": ["발음 분석기 초기화 실패"],
                "status": "error"
            }

        # 2. 병렬 실행 가능한 에이전트들
        tasks = []

        # Accent 분석
        tasks.append(
            asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: ("accent", self.accent_agent.analyze(
                    wav_path,
                    language=language_code.split("-")[0] if "-" in language_code else language_code
                ))
            )
        )

        # Intonation 분석
        tasks.append(
            asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: ("intonation", self.intonation_agent.analyze(
                    wav_path,
                    reference_text=reference_text,
                    language_code=language_code
                ))
            )
        )

        # Pause 분석 (Azure 데이터 활용)
        tasks.append(
            asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: ("pause", self.pause_agent.analyze(
                    wav_path,
                    azure_data=azure_data,
                    reference_script=reference_text
                ))
            )
        )

        # Speed 분석
        if self.speed_agent:
            tasks.append(
                asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: ("speed", self.speed_agent.analyze(wav_path))
                )
            )
        else:
            results["speed"] = {
                "score": 0,
                "max_score": 100,
                "feedback": ["속도 분석기 초기화 실패"],
                "status": "error"
            }

        # Tone 분석
        tasks.append(
            asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: ("tone", self.tone_agent.analyze(
                    wav_path,
                    language_code=language_code,
                    gender=gender
                ))
            )
        )

        # 병렬 실행 결과 수집
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 통합
        for result in parallel_results:
            if isinstance(result, Exception):
                print(f"에이전트 실행 중 오류 발생: {result}")
                continue

            agent_name, agent_result = result
            results[agent_name] = agent_result

        # 3. 종합 결과 생성
        return self._build_integrated_response(results)

    def _build_integrated_response(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        각 에이전트의 결과를 통합하여 최종 응답 생성

        Args:
            results: 각 에이전트의 분석 결과

        Returns:
            통합된 응답 딕셔너리 (100점 만점 점수 포함)
        """
        # 각 에이전트별 점수 추출 (100점 만점)
        scores = {}
        for agent_name, result in results.items():
            if isinstance(result, dict):
                scores[agent_name] = {
                    "score": result.get("score", 0),
                    "max_score": result.get("max_score", 100),
                    "feedback": result.get("feedback", []),
                    "status": result.get("status", "unknown")
                }

        # 전체 평균 점수 계산
        valid_scores = [
            s["score"] for s in scores.values()
            if s["status"] == "success"
        ]

        overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0

        # 통합 응답 구성
        integrated_response = {
            "overall_score": round(overall_score, 2),
            "max_score": 100,
            "scores": scores,
            "detailed_results": results,
            "analysis_summary": self._generate_summary(scores, overall_score)
        }

        return integrated_response

    def _generate_summary(self, scores: Dict[str, Any], overall_score: float) -> str:
        """
        분석 결과 요약 생성

        Args:
            scores: 각 에이전트별 점수
            overall_score: 전체 평균 점수

        Returns:
            요약 문자열
        """
        summary_parts = [f"전체 점수: {overall_score:.2f}/100"]

        for agent_name, score_info in scores.items():
            if score_info["status"] == "success":
                summary_parts.append(
                    f"{agent_name.capitalize()}: {score_info['score']:.2f}/100"
                )

        return " | ".join(summary_parts)

    def __del__(self):
        """리소스 정리"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
