"""
Speech Analysis Manager
6개의 에이전트를 병렬로 실행하고 결과를 통합하는 매니저
"""
import json
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.agents.analyzers.validate import ValidateAnalyzer
from app.agents.analyzers.accent import AccentAnalyzer
from app.agents.analyzers.pronunciation import PronunciationAnalyzer
from app.agents.analyzers.pause import PauseAnalyzer
from app.agents.analyzers.intonation import IntonationAnalyzer
from app.agents.analyzers.speed import SpeedAnalyzer
from app.agents.analyzers.tone import ToneAnalyzer


class SpeechAnalysisManager:
    """음성 분석 매니저"""

    def __init__(self, log_dir: str = "log"):
        """
        Args:
            log_dir: 로그 디렉토리 경로
        """
        # .env 로딩 (에이전트 초기화 전에 먼저 실행)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # logger가 아직 초기화되지 않음

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # 로거 설정
        self.logger = self._setup_logger()

        # .env 로딩 실패 경고 (logger 초기화 후)
        try:
            import dotenv
        except ImportError:
            self.logger.warning("python-dotenv가 설치되어 있지 않습니다.")

        # 에이전트 초기화
        self.agents = {
            "validate": ValidateAnalyzer(),
            "accent": AccentAnalyzer(),
            "pronunciation": PronunciationAnalyzer(),
            "pause": PauseAnalyzer(),
            "intonation": IntonationAnalyzer(),
            "speed": SpeedAnalyzer(),
            "tone": ToneAnalyzer()
        }

        self.logger.info("음성 분석 매니저 초기화 완료")

    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger("SpeechAnalysisManager")
        logger.setLevel(logging.INFO)

        # 기존 핸들러 제거
        logger.handlers.clear()

        # 파일 핸들러
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self.log_dir / f"analysis_{timestamp}.log"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _run_agent(self, agent_name: str, wav_path: str, **kwargs) -> Dict[str, Any]:
        """
        개별 에이전트 실행

        Args:
            agent_name: 에이전트 이름
            wav_path: WAV 파일 경로
            **kwargs: 에이전트별 추가 인자

        Returns:
            에이전트 분석 결과
        """
        try:
            self.logger.info(f"[{agent_name.upper()}] 분석 시작...")
            agent = self.agents[agent_name]

            # 에이전트별 특수 처리
            if agent_name == "validate":
                # Validate: 스크립트와 음성 정확성 검사 + Azure 데이터 생성
                result = agent.analyze(
                    wav_path,
                    reference_text=kwargs.get("reference_text"),
                    language_code=kwargs.get("language_code", "ko-KR")
                )

            elif agent_name == "accent":
                # Accent: language_code를 "ko"/"en" 형태로 변환
                language_code = kwargs.get("language_code", "ko-KR")
                language = language_code.split('-')[0]  # 'ko-KR' -> 'ko'
                # AccentAnalyzer는 Azure/Whisper를 내부에서 독립적으로 호출
                result = agent.analyze(wav_path, language=language)

            elif agent_name == "pronunciation":
                # Pronunciation: Validate의 azure_data 재사용
                azure_data = kwargs.get("azure_data")
                result = agent.analyze(
                    wav_path,
                    reference_text=kwargs.get("reference_text"),
                    language_code=kwargs.get("language_code", "ko-KR"),
                    azure_data=azure_data  # ← azure_data 전달
                )

            elif agent_name == "pause":
                # Pause: Validate의 azure_data 재사용
                azure_data = kwargs.get("azure_data")
                reference_script = kwargs.get("reference_text") or kwargs.get("reference_script")
                result = agent.analyze(wav_path, azure_data=azure_data, reference_script=reference_script)

            elif agent_name == "intonation":
                # Azure API 호출 없이 음향 특징만 분석 (language_code만 전달)
                result = agent.analyze(
                    wav_path,
                    reference_text=kwargs.get("reference_text"),
                    baseline_name=kwargs.get("baseline_name", "default"),
                    language_code=kwargs.get("language_code", "ko-KR")
                )

            elif agent_name == "speed":
                result = agent.analyze(wav_path)

            elif agent_name == "tone":
                # Tone: language_code와 gender 파라미터 전달
                result = agent.analyze(
                    wav_path,
                    language_code=kwargs.get("language_code", "ko-KR"),
                    gender=kwargs.get("gender", "F")
                )

            else:
                result = {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["Unknown agent"],
                    "status": "error"
                }

            # Validate는 점수가 없으므로 별도 처리
            if agent_name == "validate":
                self.logger.info(
                    f"[{agent_name.upper()}] 검증 완료 - is_valid: {result.get('is_valid', False)}"
                )
            else:
                self.logger.info(
                    f"[{agent_name.upper()}] 분석 완료 - 점수: "
                    f"{result.get('score', 0)}/{result.get('max_score', 100)}"
                )

            return {
                "agent": agent_name,
                "result": result,
                "status": "success"
            }

        except Exception as e:
            self.logger.error(f"[{agent_name.upper()}] 분석 중 오류 발생: {str(e)}")
            return {
                "agent": agent_name,
                "result": {
                    "score": 0,
                    "max_score": 100,
                    "feedback": [f"오류 발생: {str(e)}"],
                    "status": "error"
                },
                "status": "error"
            }

    def analyze_parallel(self, wav_path: str, **kwargs) -> Dict[str, Any]:
        """
        병렬로 6개 에이전트 실행 (Validate 에이전트 먼저 실행)

        Args:
            wav_path: WAV 파일 경로
            **kwargs: 에이전트별 추가 인자
                - reference_text: Validate/Pronunciation/Pause 에이전트용
                - language_code: Pronunciation/Tone/Accent/Intonation 에이전트용 (예: 'ko-KR')
                - reference_script: Pause 에이전트용
                - baseline_name: Intonation 에이전트용 (기본값: 'default')
                - gender: Tone 에이전트용 (기본값: 'F')

        Returns:
            통합 분석 결과
        """
        self.logger.info("=" * 80)
        self.logger.info(f"음성 분석 시작: {wav_path}")
        self.logger.info("=" * 80)

        start_time = datetime.now()
        results: Dict[str, Any] = {}

        # 1단계: Validate 에이전트 먼저 실행 (Azure Pronunciation Assessment 데이터 생성)
        validate_result = self._run_agent("validate", wav_path, **kwargs)
        results["validate"] = validate_result["result"]

        # Validate 결과에서 Azure 데이터 추출 (Pronunciation/Pause 에이전트용)
        azure_data = validate_result["result"].get("azure_data")
        validation_passed = validate_result["result"].get("is_valid", True)

        # Validate 검증 실패 시 처리
        if not validation_passed:
            self.logger.warning(f"[VALIDATE] 검증 실패: {validate_result['result'].get('feedback', [])}")
            for warning in validate_result["result"].get("warnings", []):
                self.logger.warning(f"  - {warning}")

            # 나머지 에이전트 실행 생략 - 모두 0점 처리
            self.logger.info("[POLICY] 검증 실패로 인해 나머지 6개 에이전트 분석을 생략합니다.")
            other_agents = ["pronunciation", "accent", "pause", "intonation", "speed", "tone"]

            for agent_name in other_agents:
                results[agent_name] = {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["스크립트 검증 실패로 분석하지 않음"],
                    "status": "skipped"
                }
                self.logger.info(f"[{agent_name.upper()}] 분석 생략 - 점수: 0/100 (검증 실패)")

        else:
            # Validate 검증 통과 - 정상적으로 나머지 에이전트 실행
            self.logger.info("[VALIDATE] 검증 통과 - 나머지 에이전트 분석을 진행합니다.")
            kwargs["azure_data"] = azure_data

            # 2단계: 나머지 에이전트 병렬 실행
            # Pronunciation은 이제 azure_data 재사용
            other_agents = ["pronunciation", "accent", "pause", "intonation", "speed", "tone"]

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_agent = {
                    executor.submit(self._run_agent, agent_name, wav_path, **kwargs): agent_name
                    for agent_name in other_agents
                }

                for future in as_completed(future_to_agent):
                    agent_name = future_to_agent[future]
                    try:
                        agent_result = future.result()
                        results[agent_name] = agent_result["result"]
                    except Exception as e:
                        self.logger.error(f"[{agent_name.upper()}] 병렬 실행 중 오류: {str(e)}")
                        results[agent_name] = {
                            "score": 0,
                            "max_score": 100,
                            "feedback": [f"실행 오류: {str(e)}"],
                            "status": "error"
                        }

        # 총점 계산
        total_score = sum(result.get("score", 0) for result in results.values())
        max_total_score = sum(result.get("max_score", 100) for result in results.values())
        average_score = (total_score / max_total_score * 100) if max_total_score > 0 else 0

        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()

        # 통합 결과
        final_result = {
            "file_path": wav_path,
            "timestamp": datetime.now().isoformat(),
            "elapsed_time": round(elapsed_time, 2),
            "summary": {
                "total_score": round(total_score, 2),
                "max_total_score": max_total_score,
                "average_score": round(average_score, 2),
                "individual_scores": {
                    agent: result.get("score", 0)
                    for agent, result in results.items()
                }
            },
            "detailed_results": results
        }

        self.logger.info("=" * 80)
        self.logger.info(
            f"분석 완료 - 총점: {total_score:.2f}/{max_total_score} ({average_score:.2f}%)"
        )
        self.logger.info(f"소요 시간: {elapsed_time:.2f}초")
        self.logger.info("=" * 80)

        # 로그 파일로 저장
        self._save_result(final_result)

        return final_result

    def _convert_to_python_types(self, obj):
        """numpy 타입을 Python 기본 타입으로 변환"""
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_to_python_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_python_types(item) for item in obj]
        else:
            return obj

    def _save_result(self, result: Dict[str, Any]):
        """결과를 JSON 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.log_dir / f"result_{timestamp}.json"

        try:
            # numpy 타입 변환
            converted_result = self._convert_to_python_types(result)

            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(converted_result, f, ensure_ascii=False, indent=2)
            self.logger.info(f"결과 저장 완료: {result_file}")
        except Exception as e:
            self.logger.error(f"결과 저장 실패: {str(e)}")

    def get_agent_outputs(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        각 에이전트의 부가적인 output 추출

        Args:
            results: analyze_parallel 결과

        Returns:
            에이전트별 주요 output 딕셔너리
        """
        detailed_results = results.get("detailed_results", {})

        outputs: Dict[str, Any] = {}

        # Accent
        if "accent" in detailed_results:
            accent_data = detailed_results["accent"]
            outputs["accent"] = {
                "score": accent_data.get("score", 0),
                "feedback": accent_data.get("feedback", []),
                "features": accent_data.get("features", {})
            }

        # Pronunciation
        if "pronunciation" in detailed_results:
            pron_data = detailed_results["pronunciation"]
            outputs["pronunciation"] = {
                "score": pron_data.get("score", 0),
                "accuracy_score": pron_data.get("accuracy_score", 0),
                "fluency_score": pron_data.get("fluency_score", 0),
                "completeness_score": pron_data.get("completeness_score", 0),
                "recognized_text": pron_data.get("recognized_text", ""),
                "word_details": pron_data.get("word_details", [])
            }

        # Pause
        if "pause" in detailed_results:
            pause_data = detailed_results["pause"]
            outputs["pause"] = {
                "score": pause_data.get("score", 0),
                "fluency_score": pause_data.get("fluency_score", 0),
                "position_score": pause_data.get("position_score", 0),
                "length_score": pause_data.get("length_score", 0),
                "total_pauses": pause_data.get("total_pauses", 0),
                "good_pauses": pause_data.get("good_pauses", 0),
                "bad_pauses": pause_data.get("bad_pauses", 0)
            }

        # Intonation
        if "intonation" in detailed_results:
            inton_data = detailed_results["intonation"]
            outputs["intonation"] = {
                "score": inton_data.get("score", 0),
                "language": inton_data.get("language", ""),
                "rhythm_type": inton_data.get("rhythm_type", ""),
                "ending_type": inton_data.get("ending_type", ""),
                "features": inton_data.get("features", {})
            }

        # Speed
        if "speed" in detailed_results:
            speed_data = detailed_results["speed"]
            outputs["speed"] = {
                "score": speed_data.get("score", 0),
                "overall_rate": speed_data.get("overall_rate", 0),
                "total_syllables": speed_data.get("total_syllables", 0),
                "total_speech_duration": speed_data.get("total_speech_duration", 0),
                "evaluation": speed_data.get("evaluation", "")
            }

        # Tone
        if "tone" in detailed_results:
            tone_data = detailed_results["tone"]
            axis_scores = tone_data.get("axis_scores", {}) or {}

            outputs["tone"] = {
                "score": tone_data.get("score", 0),
                # axis_scores 내부를 풀어서 제공
                "clarity_score": axis_scores.get("clarity", 0),
                "stability_score": axis_scores.get("stability", 0),
                "brightness_score": axis_scores.get("brightness", 0),
                "pitch_position_score": axis_scores.get("pitch_position", 0),
            }

        return outputs


if __name__ == "__main__":
    # 테스트 코드
    manager = SpeechAnalysisManager()

    # 샘플 파일로 테스트
    test_file = "app/agents/sample/F_ko-KR_track1.wav"
    test_text = """
    트랙 1 손님 여러분 도쿄까지 가는 저희 대한항공 701편에 탑승하신 것을 환영합니다. 안전한 여행을 위해 갖고 계신 짐은 앞 좌석 아래나 선반 속에 보관해 주시길 바랍니다. 감사합니다.
    """

    print(f"\n=== 음성 분석 테스트 ===")
    print(f"파일: {test_file}")
    print(f"기대 텍스트: {test_text.strip()}\n")

    result = manager.analyze_parallel(
        test_file,
        reference_text=test_text.strip(),
        language_code="ko-KR",
        gender="F"
    )

    # print("\n=== 분석 결과 ===")
    # # numpy 타입을 JSON 직렬화 가능한 타입으로 변환
    # serializable_result = manager._convert_to_python_types(result)
    # print(json.dumps(serializable_result, ensure_ascii=False, indent=2))
