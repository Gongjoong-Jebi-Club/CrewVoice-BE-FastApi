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
from app.agents.analyzers import (
    ValidateAnalyzer,
    AccentAnalyzer,
    PronunciationAnalyzer,
    PauseAnalyzer,
    IntonationAnalyzer,
    SpeedAnalyzer,
    ToneAnalyzer
)


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
                # Accent: language_code, 가중치 파라미터 전달
                language_code = kwargs.get("language_code", "ko-KR")
                result = agent.analyze(
                    wav_path,
                    language=language_code,
                    weight_pitch=kwargs.get("weight_pitch", 0.6),
                    weight_energy=kwargs.get("weight_energy", 0.4)
                )

            elif agent_name == "pronunciation":
                # Pronunciation: Validate의 가중 평균 점수 사용
                azure_data = kwargs.get("azure_data")
                validation_result = kwargs.get("validation_result")
                result = agent.analyze(
                    wav_path,
                    reference_text=kwargs.get("reference_text"),
                    language_code=kwargs.get("language_code", "ko-KR"),
                    azure_data=azure_data,  # 단어별 상세용
                    validation_result=validation_result  # 가중 평균 점수용
                )

            elif agent_name == "pause":
                # Pause: Validate의 가중 평균 FluencyScore 사용, 가중치 파라미터 전달
                azure_data = kwargs.get("azure_data")
                validation_result = kwargs.get("validation_result")
                reference_script = kwargs.get("reference_text") or kwargs.get("reference_script")
                result = agent.analyze(
                    wav_path,
                    azure_data=azure_data,
                    reference_script=reference_script,
                    validation_result=validation_result,  # 가중 평균 FluencyScore용
                    language_code=kwargs.get("language_code", "ko-KR"),
                    weight_fluency=kwargs.get("weight_fluency", 0.7),
                    weight_position=kwargs.get("weight_position", 0.2),
                    weight_length=kwargs.get("weight_length", 0.1)
                )

            elif agent_name == "intonation":
                # Azure API 호출 없이 음향 특징만 분석 (language_code, 가중치 파라미터 전달)
                result = agent.analyze(
                    wav_path,
                    reference_text=kwargs.get("reference_text"),
                    baseline_name=kwargs.get("baseline_name", "default"),
                    language_code=kwargs.get("language_code", "ko-KR"),
                    weight_baseline=kwargs.get("weight_baseline", 0.7),
                    weight_iso=kwargs.get("weight_iso", 0.3)
                )

            elif agent_name == "speed":
                # Speed: max_deduction 파라미터 전달
                result = agent.analyze(
                    wav_path,
                    max_deduction=kwargs.get("max_deduction", 5.0)
                )

            elif agent_name == "tone":
                # Tone: language_code, gender, 가중치 파라미터 전달
                result = agent.analyze(
                    wav_path,
                    language_code=kwargs.get("language_code", "ko-KR"),
                    gender=kwargs.get("gender", "F"),
                    weight_clarity=kwargs.get("weight_clarity", 0.4),
                    weight_stability=kwargs.get("weight_stability", 0.3),
                    weight_brightness=kwargs.get("weight_brightness", 0.2),
                    weight_pitch_position=kwargs.get("weight_pitch_position", 0.1)
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
            kwargs["validation_result"] = validate_result["result"]  # Pronunciation용 가중 평균 점수

            # 2단계: Accent 먼저 실행 (Intonation이 재사용할 데이터 생성)
            self.logger.info("[ACCENT] 먼저 실행 - Intonation에서 재사용할 Azure STT 데이터 생성")
            accent_result = self._run_agent("accent", wav_path, **kwargs)
            results["accent"] = accent_result["result"]

            # Accent의 타임스탬프 데이터를 Intonation에 전달
            accent_timestamps = accent_result["result"].get("timestamps", [])
            if accent_timestamps:
                # Accent의 원본 타임스탬프 데이터 (word, confidence 포함)를 Intonation에 전달
                kwargs["accent_timestamps"] = accent_timestamps
                self.logger.info(f"[ACCENT] {len(accent_timestamps)}개 단어의 타임스탬프 데이터를 Intonation에 공유")
            else:
                self.logger.warning("[ACCENT] 타임스탬프 데이터가 없어 Intonation이 직접 Azure API 호출")

            # 3단계: 나머지 에이전트 병렬 실행
            # Pronunciation, Pause는 Validate의 가중 평균 점수 사용
            # Intonation은 Accent의 타임스탬프 데이터 사용
            other_agents = ["pronunciation", "pause", "intonation", "speed", "tone"]

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

        # 총점 계산 (Validate 에이전트 제외 - 점수 에이전트만 계산)
        scoring_agents = {k: v for k, v in results.items() if k != "validate"}
        total_score = sum(result.get("score", 0) for result in scoring_agents.values())
        max_total_score = sum(result.get("max_score", 100) for result in scoring_agents.values())
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

        각 에이전트가 실제로 반환하는 데이터를 기준으로 추출하여
        comment_generator에 전달합니다.

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
                "score_pitch": accent_data.get("score_pitch", 0),
                "score_energy": accent_data.get("score_energy", 0)
            }

        # Pronunciation
        if "pronunciation" in detailed_results:
            pron_data = detailed_results["pronunciation"]
            outputs["pronunciation"] = {
                "score": pron_data.get("score", 0),
                "accuracy_score": pron_data.get("accuracy_score", 0),
                "fluency_score": pron_data.get("fluency_score", 0),
                "completeness_score": pron_data.get("completeness_score", 0),
                "recognized_text": pron_data.get("recognized_text", "")
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
            # asr_metrics에서 recognized_text 추출 (transcript 대용)
            asr_metrics = inton_data.get("asr_metrics", {})

            outputs["intonation"] = {
                "score": inton_data.get("score", 0),
                "language": inton_data.get("language", ""),
                "rhythm_type": inton_data.get("rhythm_type", ""),
                "ending_type": inton_data.get("ending_type", ""),
                "transcript": asr_metrics.get("recognized_text", "")  # asr_metrics에서 추출
            }

        # Speed
        if "speed" in detailed_results:
            speed_data = detailed_results["speed"]
            outputs["speed"] = {
                "score": speed_data.get("score", 0),
                "overall_rate": speed_data.get("overall_rate", 0),
                "total_syllables": speed_data.get("total_syllables", 0),
                "total_speech_duration": speed_data.get("total_speech_duration", 0),
                "optimal_range": speed_data.get("optimal_range", "")
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
                "pitch_position_score": axis_scores.get("pitch_position", 0)
            }

        return outputs