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


class BaselineManager:
    """Baseline 관리자"""

    def __init__(self, baseline_dir: str = "app/agents/baselines"):
        """
        Args:
            baseline_dir: Baseline 저장 디렉토리
        """
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(exist_ok=True)

        # 샘플 음성 디렉토리
        self.sample_dir = Path("app/agents/sample")

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
        from app.agents.analyzers.tone import ToneAnalyzer  # 순환 import 방지용 지연 import

        # 1) 샘플 디렉토리 결정
        if sample_dir is None:
            sample_dir = self.sample_dir

        if not sample_dir.exists():
            self.logger.error(f"tone 샘플 디렉토리를 찾을 수 없습니다: {sample_dir}")
            return {}

        # 2) 오디오 파일 수집
        wav_files = list(sample_dir.rglob("*.wav"))
        mp3_files = list(sample_dir.rglob("*.mp3"))
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

        # 5) 파일로 저장 (tone.py가 읽는 경로와 동일한 baselines 디렉토리)
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

        # 2) 오디오 파일 수집
        wav_files = list(sample_dir.rglob("*.wav"))
        mp3_files = list(sample_dir.rglob("*.mp3"))
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


    def generate_all_baselines_from_samples(self):
        """
        샘플 음성으로부터 baseline 생성 (Intonation, Tone, Speed)
        """
        from app.agents.analyzers.intonation import IntonationAnalyzer

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


if __name__ == "__main__":
    # Baseline 관리자 테스트
    manager = BaselineManager()

    # 샘플 파일 찾기
    print("\n=== 샘플 파일 검색 ===")
    files = manager.find_sample_audio_files()
    print(f"총 {len(files)}개 파일")

    # 모든 Baseline 생성
    print("\n=== 모든 Baseline 생성 ===")
    manager.generate_all_baselines_from_samples()

    # Baseline 목록 조회
    print("\n=== 생성된 Baseline ===")
    baselines = manager.list_baselines()
    for bl in baselines:
        print(f"- {bl['file']}: {bl['agent']} ({bl['created_at']})")