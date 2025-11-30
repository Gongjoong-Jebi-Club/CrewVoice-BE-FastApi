"""
Baseline Manager
다수의 샘플 음성 파일로부터 각 에이전트의 baseline을 생성하고 관리
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

# asr_module 경로 추가
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from asr_module.speed import SpeedAnalyzer
from asr_module.intonation import IntonationAnalyzer
from asr_module.tone import ToneAnalyzer
from asr_module.accent import AccentAnalyzer


class BaselineManager:
    """
    Baseline 생성 및 관리 매니저

    다수의 샘플 음성 파일로부터:
    1. Speed baseline: 평균 속도, 표준편차 계산
    2. Intonation baseline: 억양 특징 통계
    3. Tone baseline: 톤 특징 통계
    4. Accent baseline: 강조 특징 통계
    """

    def __init__(self, baseline_dir: str = "baselines"):
        """
        Args:
            baseline_dir: Baseline JSON 파일을 저장할 디렉토리
        """
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(exist_ok=True)

    def generate_speed_baseline(
        self,
        sample_files: List[str],
        baseline_name: str = "default"
    ) -> Dict[str, Any]:
        """
        Speed baseline 생성

        Args:
            sample_files: 샘플 WAV 파일 경로 리스트
            baseline_name: Baseline 이름

        Returns:
            Speed baseline 데이터
        """
        print(f"\n[Speed Baseline] {len(sample_files)}개 파일로 생성 중...")

        rates = []
        for wav_file in sample_files:
            try:
                # SpeedAnalyzer의 메서드를 직접 사용 (초기화 없이)
                analyzer = SpeedAnalyzer.__new__(SpeedAnalyzer)

                # 음절 검출
                total_syllables, _ = analyzer.detect_syllables_parselmouth(wav_file)

                # 음성 구간 검출
                speech_intervals = analyzer.detect_speech_segments(wav_file)

                # 발화 시간 계산
                total_speech_duration = sum([end - start for start, end in speech_intervals])

                # 속도 계산
                if total_speech_duration > 0:
                    rate = total_syllables / total_speech_duration
                    rates.append(rate)
                    print(f"  ✓ {Path(wav_file).name}: {rate:.2f} 음절/초")
            except Exception as e:
                print(f"  ✗ {Path(wav_file).name}: 분석 실패 - {e}")
                continue

        if not rates:
            raise ValueError("분석 가능한 파일이 없습니다.")

        # 통계 계산
        mean_rate = float(np.mean(rates))
        std_rate = float(np.std(rates))
        median_rate = float(np.median(rates))
        min_rate = float(np.min(rates))
        max_rate = float(np.max(rates))

        baseline_data = {
            "baseline_name": baseline_name,
            "sample_count": len(rates),
            "statistics": {
                "mean": mean_rate,
                "std": std_rate,
                "median": median_rate,
                "min": min_rate,
                "max": max_rate
            },
            "thresholds": {
                "optimal_min": round(mean_rate - std_rate, 2),
                "optimal_max": round(mean_rate + std_rate, 2),
                "slow_threshold": round(mean_rate - 1.5 * std_rate, 2),
                "fast_threshold": round(mean_rate + 1.5 * std_rate, 2)
            },
            "raw_rates": rates
        }

        # 저장
        output_file = self.baseline_dir / f"speed_{baseline_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Speed baseline 저장: {output_file}")
        print(f"  평균 속도: {mean_rate:.2f} 음절/초")
        print(f"  표준편차: {std_rate:.2f}")
        print(f"  최적 범위: {baseline_data['thresholds']['optimal_min']}-{baseline_data['thresholds']['optimal_max']} 음절/초")

        return baseline_data

    def generate_intonation_baseline(
        self,
        sample_files: List[str],
        baseline_name: str = "default",
        language_code: str = "ko-KR"
    ) -> Dict[str, Any]:
        """
        Intonation baseline 생성

        Args:
            sample_files: 샘플 WAV 파일 경로 리스트
            baseline_name: Baseline 이름
            language_code: 언어 코드

        Returns:
            Intonation baseline 데이터
        """
        print(f"\n[Intonation Baseline] {len(sample_files)}개 파일로 생성 중...")

        analyzer = IntonationAnalyzer()
        all_features = []

        for wav_file in sample_files:
            try:
                features = analyzer.extract_features(wav_file)
                all_features.append(features)
                print(f"  ✓ {Path(wav_file).name}: 특징 추출 완료")
            except Exception as e:
                print(f"  ✗ {Path(wav_file).name}: 분석 실패 - {e}")
                continue

        if not all_features:
            raise ValueError("분석 가능한 파일이 없습니다.")

        # 각 특징의 평균값 계산
        feature_keys = all_features[0].keys()
        reference_features = {}

        for key in feature_keys:
            if isinstance(all_features[0][key], (int, float)):
                values = [f[key] for f in all_features]
                reference_features[key] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "median": float(np.median(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values))
                }

        baseline_data = {
            "baseline_name": baseline_name,
            "language_code": language_code,
            "sample_count": len(all_features),
            "reference_features": reference_features
        }

        # 저장
        output_file = self.baseline_dir / f"intonation_{baseline_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Intonation baseline 저장: {output_file}")
        print(f"  샘플 수: {len(all_features)}개")
        print(f"  특징 수: {len(reference_features)}개")

        return baseline_data

    def generate_tone_baseline(
        self,
        sample_files: List[str],
        baseline_name: str = "default",
        language_code: str = "ko-KR",
        gender: str = "F"
    ) -> Dict[str, Any]:
        """
        Tone baseline 생성

        Args:
            sample_files: 샘플 WAV 파일 경로 리스트
            baseline_name: Baseline 이름
            language_code: 언어 코드
            gender: 성별

        Returns:
            Tone baseline 데이터
        """
        print(f"\n[Tone Baseline] {len(sample_files)}개 파일로 생성 중...")

        analyzer = ToneAnalyzer()
        all_features = []

        for wav_file in sample_files:
            try:
                y, sr = analyzer.load_audio_from_file(wav_file)
                features = analyzer.extract_tone_features(y, sr)
                all_features.append(features)
                print(f"  ✓ {Path(wav_file).name}: 특징 추출 완료")
            except Exception as e:
                print(f"  ✗ {Path(wav_file).name}: 분석 실패 - {e}")
                continue

        if not all_features:
            raise ValueError("분석 가능한 파일이 없습니다.")

        # 각 특징의 통계 계산
        feature_stats = {}
        for key in all_features[0].keys():
            values = [f[key] for f in all_features]
            feature_stats[key] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "median": float(np.median(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values))
            }

        baseline_data = {
            "baseline_name": baseline_name,
            "genders": {
                gender: {
                    "languages": {
                        language_code: {
                            "sample_count": len(all_features),
                            "features": feature_stats
                        }
                    }
                }
            }
        }

        # 저장
        output_file = self.baseline_dir / f"tone_{baseline_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Tone baseline 저장: {output_file}")
        print(f"  성별: {gender}")
        print(f"  언어: {language_code}")
        print(f"  샘플 수: {len(all_features)}개")

        return baseline_data

    def generate_accent_baseline(
        self,
        sample_files: List[str],
        baseline_name: str = "default"
    ) -> Dict[str, Any]:
        """
        Accent baseline 생성 (향후 확장 가능)

        Args:
            sample_files: 샘플 WAV 파일 경로 리스트
            baseline_name: Baseline 이름

        Returns:
            Accent baseline 데이터
        """
        print(f"\n[Accent Baseline] {len(sample_files)}개 파일로 생성 중...")

        # Accent는 현재 baseline 사용하지 않지만, 향후 확장을 위해 구조만 생성
        baseline_data = {
            "baseline_name": baseline_name,
            "sample_count": len(sample_files),
            "note": "Accent analyzer currently uses dynamic analysis without baseline"
        }

        # 저장
        output_file = self.baseline_dir / f"accent_{baseline_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)

        print(f"\n✓ Accent baseline 저장: {output_file}")
        print(f"  (현재 Accent는 동적 분석 사용)")

        return baseline_data

    def generate_all_baselines(
        self,
        sample_files: List[str],
        baseline_name: str = "default",
        language_code: str = "ko-KR",
        gender: str = "F"
    ) -> Dict[str, Any]:
        """
        모든 에이전트의 baseline을 한 번에 생성

        Args:
            sample_files: 샘플 WAV 파일 경로 리스트
            baseline_name: Baseline 이름
            language_code: 언어 코드
            gender: 성별

        Returns:
            생성된 모든 baseline 데이터
        """
        print(f"\n{'='*60}")
        print(f"Baseline 생성 시작")
        print(f"{'='*60}")
        print(f"샘플 파일 수: {len(sample_files)}개")
        print(f"Baseline 이름: {baseline_name}")
        print(f"언어: {language_code}, 성별: {gender}")

        results = {}

        try:
            # Speed baseline
            results["speed"] = self.generate_speed_baseline(sample_files, baseline_name)
        except Exception as e:
            print(f"\n✗ Speed baseline 생성 실패: {e}")
            results["speed"] = {"status": "failed", "error": str(e)}

        try:
            # Intonation baseline
            results["intonation"] = self.generate_intonation_baseline(
                sample_files, baseline_name, language_code
            )
        except Exception as e:
            print(f"\n✗ Intonation baseline 생성 실패: {e}")
            results["intonation"] = {"status": "failed", "error": str(e)}

        try:
            # Tone baseline
            results["tone"] = self.generate_tone_baseline(
                sample_files, baseline_name, language_code, gender
            )
        except Exception as e:
            print(f"\n✗ Tone baseline 생성 실패: {e}")
            results["tone"] = {"status": "failed", "error": str(e)}

        try:
            # Accent baseline (향후 확장용)
            results["accent"] = self.generate_accent_baseline(sample_files, baseline_name)
        except Exception as e:
            print(f"\n✗ Accent baseline 생성 실패: {e}")
            results["accent"] = {"status": "failed", "error": str(e)}

        print(f"\n{'='*60}")
        print(f"Baseline 생성 완료!")
        print(f"{'='*60}")

        return results

    def list_baselines(self) -> Dict[str, List[str]]:
        """
        생성된 baseline 목록 조회

        Returns:
            에이전트별 baseline 파일 목록
        """
        baselines = {
            "speed": [],
            "intonation": [],
            "tone": [],
            "accent": []
        }

        for agent in baselines.keys():
            pattern = f"{agent}_*.json"
            files = list(self.baseline_dir.glob(pattern))
            baselines[agent] = [f.stem.replace(f"{agent}_", "") for f in files]

        return baselines

    def delete_baseline(self, agent: str, baseline_name: str) -> bool:
        """
        Baseline 삭제

        Args:
            agent: 에이전트 이름 (speed, intonation, tone, accent)
            baseline_name: Baseline 이름

        Returns:
            삭제 성공 여부
        """
        baseline_file = self.baseline_dir / f"{agent}_{baseline_name}.json"

        if baseline_file.exists():
            baseline_file.unlink()
            print(f"✓ Baseline 삭제: {baseline_file}")
            return True
        else:
            print(f"✗ Baseline 없음: {baseline_file}")
            return False
