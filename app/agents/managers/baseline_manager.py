"""
Baseline Manager
샘플 음성 파일을 분석하여 baseline(기준)을 생성하고 관리
Intonation과 Tone 에이전트만 baseline을 사용함
"""
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import logging
from app.agents.analyzers import (
    IntonationAnalyzer,
    ToneAnalyzer,
    SpeedAnalyzer,
    PauseAnalyzer
)

class BaselineManager:
    """Baseline 관리자"""

    def __init__(self, baseline_dir: str = "baselines"):
        """
        Args:
            baseline_dir: Baseline 저장 디렉토리
        """
        # 현재 파일(app/agents/managers/baseline_manager.py) 기준으로
        # app/agents/baselines 설정
        self.baseline_dir = Path(__file__).parent.parent / "baselines"
        self.baseline_dir.mkdir(exist_ok=True, parents=True)

        # 샘플 음성 디렉토리: app/agents/sample
        self.sample_dir = Path(__file__).parent.parent / "sample"
        self.sample_dir.mkdir(exist_ok=True, parents=True)

        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger("BaselineManager")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger

    def find_sample_audio_files(self) -> List[Path]:
        """
        샘플 음성 파일 찾기

        Returns:
            샘플 음성 파일 경로 리스트
        """
        if not self.sample_dir.exists():
            self.logger.warning(f"샘플 디렉토리를 찾을 수 없습니다: {self.sample_dir}")
            return []

        # WAV 파일 찾기
        wav_files = list(self.sample_dir.rglob("*.wav"))

        # MP3 파일도 찾기
        mp3_files = list(self.sample_dir.rglob("*.mp3"))

        all_files = wav_files + mp3_files
        self.logger.info(f"{len(all_files)}개 샘플 파일 발견")

        return all_files

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

    def save_baseline(self, agent_name: str, baseline: Dict[str, Any], baseline_name: str = "default"):
        """
        Baseline 저장

        Args:
            agent_name: 에이전트 이름
            baseline: Baseline 데이터
            baseline_name: Baseline 이름
        """
        baseline_file = self.baseline_dir / f"{agent_name}_{baseline_name}.json"

        try:
            # numpy 타입 변환
            converted_baseline = self._convert_to_python_types(baseline)

            with open(baseline_file, 'w', encoding='utf-8') as f:
                json.dump(converted_baseline, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ Baseline 저장: {baseline_file}")
        except Exception as e:
            self.logger.error(f"❌ Baseline 저장 실패: {str(e)}")

    def load_baseline(self, agent_name: str, baseline_name: str = "default") -> Dict[str, Any]:
        """
        Baseline 로드

        Args:
            agent_name: 에이전트 이름
            baseline_name: Baseline 이름

        Returns:
            Baseline 데이터 또는 None
        """
        baseline_file = self.baseline_dir / f"{agent_name}_{baseline_name}.json"

        if not baseline_file.exists():
            self.logger.warning(f"Baseline 파일 없음: {baseline_file}")
            return None

        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline = json.load(f)
            self.logger.info(f"✅ Baseline 로드: {baseline_file}")
            return baseline
        except Exception as e:
            self.logger.error(f"❌ Baseline 로드 실패: {str(e)}")
            return None

    def list_baselines(self, agent_name: str = None) -> List[Dict[str, Any]]:
        """
        저장된 Baseline 목록 조회

        Args:
            agent_name: 특정 에이전트만 조회 (None이면 전체)

        Returns:
            Baseline 정보 리스트
        """
        pattern = f"{agent_name}_*.json" if agent_name else "*.json"
        baseline_files = list(self.baseline_dir.glob(pattern))

        baselines = []
        for bf in baseline_files:
            try:
                with open(bf, 'r', encoding='utf-8') as f:
                    baseline = json.load(f)
                baselines.append({
                    "file": bf.name,
                    "agent": baseline.get("agent", "unknown"),
                    "created_at": baseline.get("created_at", ""),
                    "sample_file": baseline.get("sample_file", "")
                })
            except:
                pass

        return baselines

    def _parse_gender_language_from_filename(self, path: Path) -> (str, str):
        """
        샘플 파일 이름에서 gender, language를 추출한다.

        기대 패턴 (예시):
          F_ko-KR_001.wav
          M_en-US_sample01.wav

        - 앞 2토큰을 gender / language로 사용
        - 인식 실패 시 기본값: gender="F", language="ko-KR"
        """
        stem = path.stem  # 확장자(.wav) 제거한 파일명
        parts = stem.split("_")

        gender = "F"
        language = "ko-KR"

        if len(parts) >= 2:
            g_candidate = parts[0]
            l_candidate = parts[1]

            if g_candidate in ("F", "M"):
                gender = g_candidate
            else:
                self.logger.warning(
                    f"파일명에서 gender 파싱 실패, 기본값 F 사용: {path.name}"
                )

            if l_candidate in ("ko-KR", "en-US"):
                language = l_candidate
            else:
                self.logger.warning(
                    f"파일명에서 language 파싱 실패, 기본값 ko-KR 사용: {path.name}"
                )
        else:
            self.logger.warning(
                f"파일명 패턴이 예상과 다름, 기본 gender/language 사용: {path.name}"
            )

        return gender, language

    def generate_tone_baseline_from_samples(
        self,
        sample_dir: Path | None = None,
        output_filename: str = "tone_default.json",
    ) -> Dict[str, Any]:
        """
        tone 에이전트용 baseline(tone_default.json)을 생성한다.

        - sample_dir 아래의 wav/mp3 파일을 전부 스캔
        - 파일명에서 gender / language를 추출
        - 각 (gender, language) 그룹별로 6개 feature의 mean/std 계산
        - tone.py에서 사용하는 스키마로 JSON 저장
        """
        # 1) 샘플 디렉토리 결정
        if sample_dir is None:
            sample_dir = self.sample_dir

        if not sample_dir.exists():
            self.logger.error(f"tone 샘플 디렉토리를 찾을 수 없습니다: {sample_dir}")
            return {}

        # 2) 오디오 파일 수집 (정렬하여 순서 일정화)
        wav_files = sorted(list(sample_dir.rglob("*.wav")))
        mp3_files = sorted(list(sample_dir.rglob("*.mp3")))
        audio_files = wav_files + mp3_files

        if not audio_files:
            self.logger.error(f"tone 샘플 오디오 파일이 없습니다: {sample_dir}")
            return {}

        self.logger.info(f"tone: {len(audio_files)}개 샘플 파일에서 baseline 생성 시작")

        # 3) (gender, language) 그룹별 feature 집계용 구조
        #    grouped_feats[(gender, language)][feature_name] = [값1, 값2, ...]
        grouped_feats: Dict[tuple, Dict[str, List[float]]] = {}

        analyzer = ToneAnalyzer()

        for audio_path in audio_files:
            try:
                gender, language = self._parse_gender_language_from_filename(audio_path)

                y, sr = analyzer.load_audio_from_file(str(audio_path))
                feats = analyzer.extract_tone_features(y, sr)

                key = (gender, language)
                if key not in grouped_feats:
                    grouped_feats[key] = {fn: [] for fn in feats.keys()}

                for fn, val in feats.items():
                    grouped_feats[key][fn].append(float(val))

                self.logger.info(
                    f"[tone] {audio_path.name} → gender={gender}, lang={language}, feats={feats}"
                )

            except Exception as e:
                self.logger.error(f"[tone] 샘플 처리 중 오류 ({audio_path}): {e}")

        # 4) mean/std 계산해서 최종 baseline 구조 만들기
        baseline: Dict[str, Any] = {
            "agent": "tone",
            "created_at": datetime.now().isoformat(),
            "genders": {}
        }

        for (gender, language), feat_dict in grouped_feats.items():
            gender_block = baseline["genders"].setdefault(gender, {"languages": {}})
            lang_block = gender_block["languages"].setdefault(language, {"features": {}})
            features_block = lang_block["features"]

            for feat_name, values in feat_dict.items():
                arr = np.array(values, dtype=float)
                mean_val = float(arr.mean())
                std_val = float(arr.std(ddof=0))  # 모집단 표준편차

                features_block[feat_name] = {
                    "mean": mean_val,
                    "std": std_val,
                }

        # 5) 파일로 저장
        output_path = self.baseline_dir / output_filename

        try:
            converted = self._convert_to_python_types(baseline)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ tone baseline 생성 완료: {output_path}")
        except Exception as e:
            self.logger.error(f"❌ tone baseline 저장 실패: {e}")

        return baseline

    def generate_speed_baseline_from_samples(
        self,
        sample_dir: Path | None = None,
        output_filename: str = "speed_default.json",
    ) -> Dict[str, Any]:
        """
        speed 에이전트용 baseline(speed_default.json)을 생성한다.

        - sample_dir 아래의 wav/mp3 파일을 전부 스캔
        - 각 파일의 발화 속도 계산
        - 평균, 표준편차 등 통계 계산
        - speed.py에서 사용하는 스키마로 JSON 저장
        """
        import librosa
        import parselmouth
        from scipy.signal import find_peaks

        # 1) 샘플 디렉토리 결정
        if sample_dir is None:
            sample_dir = self.sample_dir

        if not sample_dir.exists():
            self.logger.error(f"speed 샘플 디렉토리를 찾을 수 없습니다: {sample_dir}")
            return {}

        # 2) 오디오 파일 수집 (정렬하여 순서 일정화)
        wav_files = sorted(list(sample_dir.rglob("*.wav")))
        mp3_files = sorted(list(sample_dir.rglob("*.mp3")))
        audio_files = wav_files + mp3_files

        if not audio_files:
            self.logger.error(f"speed 샘플 오디오 파일이 없습니다: {sample_dir}")
            return {}

        self.logger.info(f"speed: {len(audio_files)}개 샘플 파일에서 baseline 생성 시작")

        # 3) 각 파일의 속도 계산
        rates = []
        for audio_path in audio_files:
            try:
                # 음절 검출 (Parselmouth)
                sound = parselmouth.Sound(str(audio_path))
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

                # 음성 구간 검출 (librosa)
                y, sr = librosa.load(str(audio_path), sr=None)
                intervals = librosa.effects.split(y, top_db=40, frame_length=2048, hop_length=512)

                time_intervals = []
                for start_sample, end_sample in intervals:
                    start_t = start_sample / sr
                    end_t = end_sample / sr
                    duration = end_t - start_t
                    if duration >= 0.1:
                        time_intervals.append((start_t, end_t))

                # 가까운 구간 병합
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

                # 발화 시간 계산
                total_speech_duration = sum([end - start for start, end in merged_intervals])

                # 속도 계산
                if total_speech_duration > 0:
                    rate = total_syllables / total_speech_duration
                    rates.append(rate)
                    self.logger.info(f"  {audio_path.name}: {rate:.2f} 음절/초")

            except Exception as e:
                self.logger.error(f"[speed] 샘플 처리 중 오류 ({audio_path}): {e}")

        if not rates:
            self.logger.error("speed baseline: 분석 가능한 파일이 없습니다.")
            return {}

        # 4) 통계 계산
        mean_rate = float(np.mean(rates))
        std_rate = float(np.std(rates))

        baseline: Dict[str, Any] = {
            "agent": "speed",
            "created_at": datetime.now().isoformat(),
            "statistics": {
                "mean_rate": mean_rate,
                "std_rate": std_rate,
                "optimal_min": round(mean_rate - std_rate, 2),
                "optimal_max": round(mean_rate + std_rate, 2),
                "slow_threshold": round(mean_rate - 1.5 * std_rate, 2),
                "fast_threshold": round(mean_rate + 1.5 * std_rate, 2),
            },
            "sample_count": len(rates),
            "sample_rates": [round(r, 2) for r in rates],
        }

        # 5) 파일로 저장
        output_path = self.baseline_dir / output_filename

        try:
            converted = self._convert_to_python_types(baseline)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ speed baseline 생성 완료: {output_path}")
        except Exception as e:
            self.logger.error(f"❌ speed baseline 저장 실패: {e}")

        return baseline

    def preprocess_samples_for_pause(
        self,
        sample_dir: Path | None = None,
        pause_reference_dir: Path | None = None,
    ) -> int:
        """
        샘플 음성 파일에 대한 Azure 분석 결과 생성
        Pause baseline 생성을 위한 전처리

        Args:
            sample_dir: 샘플 WAV 파일 디렉토리
            pause_reference_dir: TXT 스크립트와 JSON 결과를 함께 저장하는 디렉토리

        Returns:
            처리된 파일 수
        """
        import os
        import azure.cognitiveservices.speech as speechsdk
        from dotenv import load_dotenv

        # 환경변수 로드
        load_dotenv()

        # Azure 설정
        AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
        AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

        if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
            self.logger.error("Azure Speech credentials not found. Check .env file.")
            return 0

        # 디렉토리 설정
        if sample_dir is None:
            sample_dir = self.sample_dir
        if pause_reference_dir is None:
            # 기본값: baselines/pause_reference
            pause_reference_dir = self.baseline_dir / "pause_reference"

        pause_reference_dir.mkdir(exist_ok=True)

        # WAV 파일 수집
        wav_files = sorted(sample_dir.glob("*.wav"))
        if not wav_files:
            self.logger.error(f"{sample_dir}에 WAV 파일이 없습니다.")
            return 0

        self.logger.info(f"🎤 {len(wav_files)}개 샘플 파일 전처리 시작")
        self.logger.info(f"📁 출력 디렉토리: {pause_reference_dir}")

        success_count = 0
        skip_count = 0
        error_count = 0

        for wav_path in wav_files:
            try:
                # 출력 파일 경로 (pause_reference 폴더에 JSON과 TXT 함께 저장)
                json_path = pause_reference_dir / f"{wav_path.stem}.json"
                txt_path = pause_reference_dir / f"{wav_path.stem}.txt"

                # 이미 처리된 파일은 건너뛰기 (JSON만 확인, TXT는 이미 있음)
                if json_path.exists():
                    self.logger.info(f"⏭️  건너뜀: {wav_path.name}")
                    skip_count += 1
                    continue

                self.logger.info(f"처리 중: {wav_path.name}")

                # 파일명에서 언어 추출
                _, language = self._parse_gender_language_from_filename(wav_path)
                self.logger.info(f"  언어: {language}")

                # Azure Speech Config 설정
                speech_config = speechsdk.SpeechConfig(
                    subscription=AZURE_SPEECH_KEY,
                    region=AZURE_SPEECH_REGION
                )
                speech_config.speech_recognition_language = language

                # 오디오 설정
                audio_config = speechsdk.audio.AudioConfig(filename=str(wav_path))

                # Pronunciation Assessment 설정
                pronunciation_config = speechsdk.PronunciationAssessmentConfig(
                    reference_text="",
                    grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                    granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                    enable_miscue=False
                )
                pronunciation_config.enable_prosody_assessment()

                # Speech Recognizer 생성
                speech_recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )
                pronunciation_config.apply_to(speech_recognizer)

                # 인식 수행
                self.logger.info("  Azure API 호출 중...")
                result = speech_recognizer.recognize_once()

                if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    # JSON 결과 파싱
                    result_json = json.loads(result.json)

                    # JSON 저장
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(result_json, f, ensure_ascii=False, indent=2)
                    self.logger.info(f"  💾 JSON 저장: {json_path.name}")

                    # Reference script 확인 (같은 폴더에 이미 TXT 있어야 함)
                    if txt_path.exists():
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            reference_text = f.read().strip()
                        self.logger.info(f"  📄 원본 스크립트 확인: {txt_path.name}")
                        self.logger.info(f"  ✅ 인식 성공: {reference_text}")
                    else:
                        self.logger.warning(f"  ⚠️  원본 스크립트 없음: {txt_path.name}")
                        self.logger.warning(f"  baseline 생성 시 context 분류가 부정확할 수 있습니다.")

                    success_count += 1

                elif result.reason == speechsdk.ResultReason.NoMatch:
                    self.logger.error(f"  ❌ 음성 인식 실패")
                    error_count += 1

                elif result.reason == speechsdk.ResultReason.Canceled:
                    cancellation = result.cancellation_details
                    self.logger.error(f"  ❌ 취소됨: {cancellation.reason}")
                    if cancellation.reason == speechsdk.CancellationReason.Error:
                        self.logger.error(f"  오류 상세: {cancellation.error_details}")
                    error_count += 1

            except Exception as e:
                self.logger.error(f"  ❌ 오류 발생: {e}")
                error_count += 1

        self.logger.info("\n" + "=" * 80)
        self.logger.info("📊 전처리 완료")
        self.logger.info(f"  ✅ 성공: {success_count}개")
        self.logger.info(f"  ⏭️  건너뜀: {skip_count}개")
        self.logger.info(f"  ❌ 실패: {error_count}개")

        return success_count

    def generate_pause_baseline_from_samples(
        self,
        sample_dir: Path | None = None,
        pause_reference_dir: Path | None = None,
        output_filename: str = "pause_default.json",
        auto_preprocess: bool = True,
    ) -> Dict[str, Any]:
        """
        pause 에이전트용 baseline(pause_default.json)을 생성한다.

        - pause_reference_dir 아래의 JSON 파일과 TXT 파일을 스캔
        - Azure 분석 결과에서 pause 데이터 추출
        - 언어별, context별로 feature의 mean/std 계산
        - min_pause_threshold는 전체 pause_sec의 하위 5% 퍼센타일로 설정

        Args:
            sample_dir: 샘플 WAV 파일 디렉토리
            pause_reference_dir: TXT 스크립트와 JSON 결과를 함께 저장하는 디렉토리
            output_filename: 출력 baseline 파일명
            auto_preprocess: JSON 파일이 없으면 자동으로 전처리 수행 (기본값: True)
        """
        # 1) pause_reference 디렉토리 결정
        if pause_reference_dir is None:
            # 기본값: baselines/pause_reference
            pause_reference_dir = self.baseline_dir / "pause_reference"

        # 2) JSON 파일 수집
        json_files = list(pause_reference_dir.glob("*.json")) if pause_reference_dir.exists() else []

        # 3) JSON 파일이 없으면 전처리 수행
        if not json_files and auto_preprocess:
            self.logger.info("pause_reference 디렉토리에 JSON 파일이 없습니다. 자동 전처리를 시작합니다...")
            processed_count = self.preprocess_samples_for_pause(sample_dir, pause_reference_dir)

            if processed_count == 0:
                self.logger.error("전처리 실패: JSON 파일을 생성할 수 없습니다.")
                return {}

            # 전처리 후 다시 JSON 파일 수집
            json_files = list(pause_reference_dir.glob("*.json"))

        if not json_files:
            self.logger.error(f"pause_reference 디렉토리에 JSON 파일이 없습니다: {pause_reference_dir}")
            self.logger.info("샘플 전처리를 먼저 수행하세요: manager.preprocess_samples_for_pause()")
            return {}

        self.logger.info(f"pause: {len(json_files)}개 JSON 파일에서 baseline 생성 시작")

        # 3) 언어별, context별 feature 집계용 구조
        # grouped_data[language][context][feature_name] = [값1, 값2, ...]
        grouped_data: Dict[str, Dict[str, Dict[str, List[float]]]] = {}
        all_pause_secs: Dict[str, List[float]] = {}  # 언어별 모든 pause_sec 값

        # mid_phrase_breath criteria 계산용 (mid_phrase 중에서 breath로 판단된 케이스)
        mid_phrase_breath_candidates: Dict[str, Dict[str, List[float]]] = {}

        # good_pause_ratio 계산용 (파일별 good pause 비율)
        good_pause_ratios: Dict[str, List[float]] = {}

        for json_path in json_files:
            try:
                # Reference script 파일 경로
                txt_path = json_path.with_suffix('.txt')
                if not txt_path.exists():
                    self.logger.warning(f"Reference script 없음: {txt_path.name}")
                    # txt 파일 없이도 진행 가능 (context 분류가 부정확할 뿐)

                # JSON 데이터 로드
                with open(json_path, 'r', encoding='utf-8') as f:
                    azure_data = json.load(f)

                # Reference script 로드 (있으면)
                reference_script = None
                if txt_path.exists():
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        reference_script = f.read().strip()

                # 파일명에서 언어 추출
                _, language = self._parse_gender_language_from_filename(json_path)

                # pause 데이터 추출 (Azure NBest[0].Words 사용)
                if 'NBest' not in azure_data or len(azure_data['NBest']) == 0:
                    self.logger.warning(f"Azure 데이터 없음: {json_path.name}")
                    continue

                words = azure_data['NBest'][0].get('Words', [])

                # Reference script에서 문장부호 위치 추출 (있으면)
                punctuation_positions = None
                if reference_script:
                    analyzer = PauseAnalyzer()
                    punctuation_positions = analyzer.extract_punctuation_positions(reference_script)

                # Pause 분석 (pause.py의 로직 재사용)
                prev_phrase_start_time = 0.0
                words_since_last_pause = 0

                # 파일별 good/bad pause 카운트
                file_good_pauses = 0
                file_bad_pauses = 0

                for i, word in enumerate(words):
                    offset = word.get('Offset', 0)
                    duration = word.get('Duration', 0)

                    start_time = offset / 1000000
                    duration_sec = duration / 1000000
                    end_time = start_time + duration_sec

                    words_since_last_pause += 1

                    if i < len(words) - 1:
                        next_word = words[i + 1]
                        next_offset = next_word.get('Offset', 0)
                        next_start = next_offset / 1000000
                        pause_sec = next_start - end_time

                        if pause_sec >= 0.05:  # 임시 최소값 (나중에 baseline으로 대체됨)
                            prev_phrase_duration_sec = end_time - prev_phrase_start_time

                            # Context 분류
                            if punctuation_positions:
                                # Reference script 있으면 정확한 분류
                                analyzer = PauseAnalyzer()
                                context = analyzer.classify_pause_context(i, punctuation_positions)

                                # mid_phrase인 경우 breath 여부 판단
                                if context == 'mid_phrase':
                                    if prev_phrase_duration_sec >= 3.0 or words_since_last_pause >= 10:
                                        context = 'mid_phrase_breath'
                            else:
                                # Reference script 없으면 추정
                                if pause_sec >= 0.4:
                                    context = 'after_period'
                                elif pause_sec >= 0.2:
                                    context = 'after_comma'
                                elif prev_phrase_duration_sec >= 3.0 or words_since_last_pause >= 10:
                                    context = 'mid_phrase_breath'
                                else:
                                    context = 'mid_phrase'

                            # good/bad pause 카운트 (mid_phrase는 bad, 나머지는 good)
                            if context == 'mid_phrase':
                                file_bad_pauses += 1
                            else:
                                file_good_pauses += 1

                            # 언어별 데이터 구조 초기화
                            if language not in grouped_data:
                                grouped_data[language] = {}
                                all_pause_secs[language] = []

                            if context not in grouped_data[language]:
                                grouped_data[language][context] = {
                                    'pause_sec': [],
                                    'prev_phrase_duration_sec': [],
                                    'words_since_last_pause': []
                                }

                            # 데이터 추가
                            grouped_data[language][context]['pause_sec'].append(pause_sec)
                            grouped_data[language][context]['prev_phrase_duration_sec'].append(prev_phrase_duration_sec)
                            grouped_data[language][context]['words_since_last_pause'].append(float(words_since_last_pause))

                            # 전체 pause_sec도 저장 (min_pause_threshold 계산용)
                            all_pause_secs[language].append(pause_sec)

                            # mid_phrase_breath로 분류된 케이스 수집 (criteria 계산용)
                            if context == 'mid_phrase_breath':
                                if language not in mid_phrase_breath_candidates:
                                    mid_phrase_breath_candidates[language] = {
                                        'prev_phrase_duration_sec': [],
                                        'words_since_last_pause': []
                                    }
                                mid_phrase_breath_candidates[language]['prev_phrase_duration_sec'].append(prev_phrase_duration_sec)
                                mid_phrase_breath_candidates[language]['words_since_last_pause'].append(float(words_since_last_pause))

                            # 다음 phrase 초기화
                            prev_phrase_start_time = next_start
                            words_since_last_pause = 0

                # 파일별 good_pause_ratio 계산 및 저장
                total_pauses = file_good_pauses + file_bad_pauses
                if total_pauses > 0:
                    ratio = file_good_pauses / total_pauses
                    if language not in good_pause_ratios:
                        good_pause_ratios[language] = []
                    good_pause_ratios[language].append(ratio)
                    self.logger.info(f"[pause] {json_path.name} → language={language}, good_ratio={ratio:.2f}")
                else:
                    self.logger.info(f"[pause] {json_path.name} → language={language}, good_ratio=0.00 (no pauses)")

            except Exception as e:
                self.logger.error(f"[pause] JSON 처리 중 오류 ({json_path.name}): {e}")

        # 4) mean/std 계산 및 baseline 구조 생성
        baseline: Dict[str, Any] = {
            "agent": "pause",
            "created_at": datetime.now().isoformat(),
            "languages": {}
        }

        for language, contexts in grouped_data.items():
            # min_pause_threshold 계산 (하위 5% 퍼센타일)
            if language in all_pause_secs and len(all_pause_secs[language]) > 0:
                min_threshold = float(np.percentile(all_pause_secs[language], 5))
            else:
                min_threshold = 0.15  # Fallback

            # mid_phrase_breath_criteria 계산 (25th percentile)
            # mid_phrase_breath로 분류된 케이스들의 하위 25% 값을 임계값으로 사용
            breath_criteria = {}
            if language in mid_phrase_breath_candidates:
                candidates = mid_phrase_breath_candidates[language]

                if len(candidates['prev_phrase_duration_sec']) > 0:
                    min_duration = float(np.percentile(candidates['prev_phrase_duration_sec'], 25))
                    breath_criteria['min_prev_phrase_duration_sec'] = round(min_duration, 3)

                if len(candidates['words_since_last_pause']) > 0:
                    min_words = float(np.percentile(candidates['words_since_last_pause'], 25))
                    breath_criteria['min_words_since_last_pause'] = int(round(min_words))

            # good_pause_ratio 통계 계산 (mean/std)
            good_ratio_stats = {}
            if language in good_pause_ratios and len(good_pause_ratios[language]) > 0:
                ratios = np.array(good_pause_ratios[language], dtype=float)
                good_ratio_stats = {
                    "mean": round(float(ratios.mean()), 3),
                    "std": round(float(ratios.std(ddof=0)), 3)
                }

            lang_block = {
                "min_pause_threshold": round(min_threshold, 3),
                "mid_phrase_breath_criteria": breath_criteria if breath_criteria else None,
                "good_pause_ratio": good_ratio_stats if good_ratio_stats else None,
                "contexts": {}
            }

            for context, features in contexts.items():
                context_block = {"features": {}}

                for feature_name, values in features.items():
                    if len(values) > 0:
                        arr = np.array(values, dtype=float)
                        mean_val = float(arr.mean())
                        std_val = float(arr.std(ddof=0))  # 모집단 표준편차

                        context_block["features"][feature_name] = {
                            "mean": round(mean_val, 3),
                            "std": round(std_val, 3),
                        }

                lang_block["contexts"][context] = context_block

            baseline["languages"][language] = lang_block

        # 5) 파일로 저장
        output_path = self.baseline_dir / output_filename

        try:
            converted = self._convert_to_python_types(baseline)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ pause baseline 생성 완료: {output_path}")
        except Exception as e:
            self.logger.error(f"❌ pause baseline 저장 실패: {e}")

        return baseline


    def generate_all_baselines_from_samples(self):
        """
        샘플 음성으로부터 baseline 생성 (Intonation, Tone, Speed)
        """
        sample_files = self.find_sample_audio_files()

        if not sample_files:
            self.logger.error("샘플 파일을 찾을 수 없습니다.")
            return

        # Intonation baseline 생성
        self.logger.info(f"\n{'='*80}")
        self.logger.info("INTONATION Baseline 생성 중...")
        self.logger.info(f"{'='*80}")

        try:
            sample_file = sample_files[0]
            self.logger.info(f"샘플 파일: {sample_file}")

            analyzer = IntonationAnalyzer()
            features = analyzer.extract_features(str(sample_file))
            baseline_data = {
                "agent": "intonation",
                "sample_file": str(sample_file),
                "created_at": datetime.now().isoformat(),
                "reference_features": features,
                "metadata": {
                    "file_size": sample_file.stat().st_size,
                    "file_name": sample_file.name
                }
            }
            self.save_baseline("intonation", baseline_data)
            self.logger.info("✅ Intonation baseline 생성 완료")

        except Exception as e:
            self.logger.error(f"Intonation baseline 생성 중 오류: {str(e)}")

        # Tone baseline 생성
        self.logger.info(f"\n{'='*80}")
        self.logger.info("TONE Baseline 생성 중...")
        self.logger.info(f"{'='*80}")

        try:
            self.generate_tone_baseline_from_samples(
                sample_dir=self.sample_dir,
                output_filename="tone_default.json",
            )
            self.logger.info("✅ Tone baseline 생성 완료")

        except Exception as e:
            self.logger.error(f"Tone baseline 생성 중 오류: {str(e)}")

        # Speed baseline 생성
        self.logger.info(f"\n{'='*80}")
        self.logger.info("SPEED Baseline 생성 중...")
        self.logger.info(f"{'='*80}")

        try:
            self.generate_speed_baseline_from_samples(
                sample_dir=self.sample_dir,
                output_filename="speed_default.json",
            )
            self.logger.info("✅ Speed baseline 생성 완료")

        except Exception as e:
            self.logger.error(f"Speed baseline 생성 중 오류: {str(e)}")

        # Pause baseline 생성
        self.logger.info(f"\n{'='*80}")
        self.logger.info("PAUSE Baseline 생성 중...")
        self.logger.info(f"{'='*80}")

        try:
            self.generate_pause_baseline_from_samples(
                sample_dir=self.sample_dir,
                pause_reference_dir=self.baseline_dir / "pause_reference",
                output_filename="pause_default.json",
            )
            self.logger.info("✅ Pause baseline 생성 완료")

        except Exception as e:
            self.logger.error(f"Pause baseline 생성 중 오류: {str(e)}")
