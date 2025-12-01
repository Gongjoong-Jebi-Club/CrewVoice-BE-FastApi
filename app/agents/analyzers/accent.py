"""
Accent Analysis Agent
음성 파일의 강조(Accent) 분석을 수행하는 에이전트
"""
import os
import json
import librosa
import parselmouth
import numpy as np
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import azure.cognitiveservices.speech as speechsdk



class AccentAnalyzer:
    """강조(Accent) 분석기"""

    def __init__(self, baseline_dir: str = "app/agents/baselines"):
        # Baseline 지원
        self.baseline_dir = Path(baseline_dir)
        self.baseline_cache = {}

    def _get_timestamps_from_azure_stt(self, wav_path: str, language: str) -> Optional[List[Dict]]:
        """
        Azure의 일반 STT 모드를 사용하여 단어별 타임스탬프를 독립적으로 추출합니다.
        발음 평가 모드가 아닌, 일반 음성 인식 결과를 사용합니다.

        Args:
            wav_path: WAV 파일 경로
            language: 언어 코드 (e.g., 'ko-KR')

        Returns:
            단어와 시간 정보가 담긴 딕셔셔리 리스트, 또는 실패 시 None
        """
        try:
            speech_key = os.getenv("SPEECH_KEY") or os.getenv("AZURE_SPEECH_KEY")
            speech_region = os.getenv("SPEECH_REGION") or os.getenv("AZURE_SPEECH_REGION")
            if not speech_key or not speech_region:
                print("WARN: Azure 키/리전이 없어 AccentAnalyzer의 Azure STT를 건너뜁니다.")
                return None

            # 에너지 기반 묵음 제거를 위해 오디오 로드
            y, sr = librosa.load(wav_path, sr=16000, mono=True)
            trimmed_audio, _ = librosa.effects.trim(y, top_db=30)
            original_duration = len(y) / sr
            trimmed_duration = len(trimmed_audio) / sr
            print(f"Accent 전처리: 에너지 기반 묵음 제거. 원본 {original_duration:.2f}s -> 처리 후 {trimmed_duration:.2f}s")

            # 임시 파일에 처리된 오디오 저장
            import tempfile
            import soundfile as sf
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                sf.write(tmp.name, trimmed_audio, sr)
                trimmed_wav_path = tmp.name

                lang_code = f"{language}-KR" if language == "ko" else f"{language}-US"
                speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
                speech_config.speech_recognition_language = lang_code
                speech_config.request_word_level_timestamps()

                # 긴 오디오를 위한 설정
                speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "10000"
                )
                speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "10000"
                )

                audio_config = speechsdk.audio.AudioConfig(filename=trimmed_wav_path)
                recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

                # continuous recognition을 사용하여 전체 오디오 인식
                all_timestamps = []
                done = False

                def handle_recognized(evt):
                    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                        json_result = json.loads(evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
                        words = json_result.get('NBest', [{}])[0].get('Words', [])
                        for word_info in words:
                            confidence = word_info.get('Confidence', 0.0)
                            start_time = word_info.get('Offset', 0) / 10000000.0
                            end_time = (word_info.get('Offset', 0) + word_info.get('Duration', 0)) / 10000000.0
                            all_timestamps.append({
                                "word": word_info.get('Word'),
                                "start": start_time,
                                "end": end_time,
                                "confidence": confidence
                            })

                def handle_canceled(evt):
                    nonlocal done
                    cancellation_details = evt.result.cancellation_details
                    if cancellation_details.reason == speechsdk.CancellationReason.Error:
                        print(f"AccentAnalyzer: Azure STT 에러 - {cancellation_details.error_details}")
                    done = True

                def handle_stopped(evt):
                    nonlocal done
                    done = True

                recognizer.recognized.connect(handle_recognized)
                recognizer.canceled.connect(handle_canceled)
                recognizer.session_stopped.connect(handle_stopped)

                recognizer.start_continuous_recognition()

                # 인식 완료 대기
                import time
                while not done:
                    time.sleep(0.1)

                recognizer.stop_continuous_recognition()

                if all_timestamps:
                    return all_timestamps

                print("AccentAnalyzer: Azure STT가 음성을 인식하지 못했습니다.")
                return None
        except Exception as e:
            print(f"AccentAnalyzer: Azure STT 호출 중 오류 발생: {e}")
            return None

    def get_audio_features(self, wav_path: str, timestamps: Dict) -> Dict:
        """
        음향 특징 추출

        Args:
            wav_path: WAV 파일 경로
            timestamps: 단어별 타임스탬프

        Returns:
            단어별 음향 특징 딕셔너리
        """
        try:
            snd = parselmouth.Sound(wav_path)
            y, sr = librosa.load(wav_path, sr=None)

            # 1. 노이즈 감소 (선택적)
            # y = librosa.effects.preemphasis(y)

            # 2. 음량 정규화 (Loudness Normalization)
            y = librosa.util.normalize(y)
        except Exception as e:
            print(f"ERROR: 오디오 파일 로드 실패: {wav_path} | {e}")
            return None

        # 전체 평균 특징 계산
        pitch = snd.to_pitch()
        f0_values_all = pitch.selected_array['frequency']
        total_avg_pitch = np.mean(f0_values_all[f0_values_all > 0])
        total_std_pitch = np.std(f0_values_all[f0_values_all > 0])

        rms_all = librosa.feature.rms(y=y)[0]
        total_avg_energy = np.mean(rms_all)
        total_std_energy = np.std(rms_all)

        # 단어별 특징 계산 (리스트로 변경)
        all_words_features = []
        for item in timestamps:
            word = item["word"]
            start_time = item["start"]
            end_time = item["end"]

            try:
                # Energy 벡터 추출
                start_frame_rms = librosa.time_to_frames(start_time, sr=sr)
                end_frame_rms = librosa.time_to_frames(end_time, sr=sr)
                energy_vector = rms_all[start_frame_rms:end_frame_rms]
                # 단어 길이가 너무 짧아 벡터가 비는 경우 방지
                if len(energy_vector) == 0 and start_frame_rms < len(rms_all):
                    energy_vector = np.array([rms_all[start_frame_rms]])
                elif len(energy_vector) == 0:
                    energy_vector = np.array([total_avg_energy])

                # Pitch 벡터 추출
                start_frame_pitch = int(round(pitch.get_frame_number_from_time(start_time)))
                end_frame_pitch = int(round(pitch.get_frame_number_from_time(end_time)))
                pitch_vector = f0_values_all[start_frame_pitch:end_frame_pitch]
                pitch_vector_voiced = pitch_vector[pitch_vector > 0]
                if len(pitch_vector_voiced) == 0:
                    # 음높이가 없는 단어(무성음)는 전체 평균 음높이를 사용하도록 처리
                    # 이렇게 하면 0으로 인한 통계 왜곡을 줄일 수 있습니다.
                    pitch_vector_voiced = np.array([total_avg_pitch])

                def safe_ratio(numerator, denominator):
                    if denominator > 0 and not np.isnan(denominator) and not np.isinf(denominator):
                        return numerator / denominator
                    return 1.0 if numerator > 0 else 0.0

                all_words_features.append({
                    "word": word,
                    "start": start_time,
                    "end": end_time,
                    "features": {
                        "energy_mean_ratio": float(safe_ratio(np.mean(energy_vector), total_avg_energy)),
                        "energy_max_ratio": float(safe_ratio(np.max(energy_vector), total_avg_energy)),
                        "energy_std_ratio": float(safe_ratio(np.std(energy_vector), total_std_energy)),
                        "pitch_mean_ratio": float(safe_ratio(np.mean(pitch_vector_voiced), total_avg_pitch)),
                        "pitch_max_ratio": float(safe_ratio(np.max(pitch_vector_voiced), total_avg_pitch)),
                        "pitch_std_ratio": float(safe_ratio(np.std(pitch_vector_voiced), total_std_pitch))
                    }
                })

            except Exception as e:
                print(f"WARN: '{word}' 특징 추출 중 오류: {e}")
                # 오류 발생 시에도 형식 유지
                all_words_features.append({"word": word, "start": start_time, "end": end_time, "features": {}})

        return all_words_features

    def _get_pos_tags(self, words: List[str], language: str) -> Dict[str, str]:
        """ 단어의 품사 태깅 (언어에 따라 분기) """
        pos_tags = {}
        if language.lower().startswith('ko'): # 한국어
            try:
                from konlpy.tag import Okt
                okt = Okt()
                # 내용어 품사 태그 (명사, 동사, 형용사, 부사, 감탄사)
                content_pos = ['Noun', 'Verb', 'Adjective', 'Adverb', 'Exclamation']
                for word in words:
                    tags = okt.pos(word)
                    if tags and tags[0][1] in content_pos:
                        pos_tags[word] = 'Content'
                    else:
                        pos_tags[word] = 'Function'
                return pos_tags
            except ImportError:
                # konlpy가 없으면 모두 내용어로 처리
                return {word: 'Content' for word in words}

        elif language.lower().startswith('en'): # 영어
            try:
                import nltk
                # 내용어 품사 태그 (명사, 동사, 형용사, 부사)
                # NN*, VB*, JJ*, RB*
                content_pos_prefixes = ('NN', 'VB', 'JJ', 'RB')
                tagged_words = nltk.pos_tag(words)
                for word, tag in tagged_words:
                    if tag.startswith(content_pos_prefixes):
                        pos_tags[word] = 'Content'
                    else:
                        pos_tags[word] = 'Function'
                return pos_tags
            except ImportError:
                # nltk가 없으면 모두 내용어로 처리
                return {word: 'Content' for word in words}

        else: # 지원하지 않는 언어
            return {word: 'Content' for word in words}

    def _gaussian_score(self, x, mu, sigma):
        """ 가우시안 함수를 이용한 점수 계산 (0~1 사이 값) """
        return np.exp(-0.5 * ((x - mu) / sigma) ** 2)

    def calculate_emphasis_score(self, user_features: Dict, language: str = "ko", use_pos_tagging: bool = True) -> Tuple[int, List[str]]:
        """
        강조 점수 계산 (고도화된 방식)
        - 가우시안 점수 모델 적용
        - 품사 태깅을 통한 단어 가중치 부여 (선택적)
        - 다양한 음향 특징(mean, max) 활용

        Args:
            user_features: 사용자 음향 특징
            language: 언어 코드 ('ko', 'en' 등)
            use_pos_tagging: 품사 태깅 사용 여부

        Returns:
            (점수, 피드백 리스트) 튜플
        """
        if not user_features or len(user_features) < 2:
            return 70, ["분석할 단어가 부족하여 정확한 강조 평가가 어렵습니다."]

        words = [item['word'] for item in user_features]
        pos_tags = self._get_pos_tags(words, language) if use_pos_tagging else {word: 'Content' for word in words}

        # 가중치 설정 (내용어: 1.0, 기능어: 0.5)
        weights = np.array([1.0 if pos_tags.get(word) == 'Content' else 0.5 for word in words])

        # 특징 추출
        all_features = [item['features'] for item in user_features]
        features = {
            'energy_mean': np.array([feat.get("energy_mean_ratio", 1.0) for feat in all_features]),
            'energy_max': np.array([feat.get("energy_max_ratio", 1.0) for feat in all_features]),
            'pitch_mean': np.array([feat.get("pitch_mean_ratio", 1.0) for feat in all_features]),
            'pitch_max': np.array([feat.get("pitch_max_ratio", 1.0) for feat in all_features])
        }

        def weighted_std(values, weights):
            """ 가중 표준편차 계산 """
            average = np.average(values, weights=weights)
            variance = np.average((values - average) ** 2, weights=weights)
            return np.sqrt(variance)

        # 가중 표준편차 계산
        stds = {key: weighted_std(val, weights) for key, val in features.items()}

        # 가우시안 점수 모델 (mu: 이상적인 표준편차, sigma: 허용 범위)
        # 이 값들은 다양한 샘플을 통해 튜닝하면 좋습니다.
        score_models = {
            'energy_mean': {'mu': 0.4, 'sigma': 0.2, 'weight': 0.3},
            'energy_max':  {'mu': 0.6, 'sigma': 0.3, 'weight': 0.2},
            'pitch_mean':  {'mu': 0.15, 'sigma': 0.1, 'weight': 0.3},
            'pitch_max':   {'mu': 0.25, 'sigma': 0.15, 'weight': 0.2}
        }

        # 각 특징별 점수 계산
        scores = {}
        for key, model in score_models.items():
            scores[key] = self._gaussian_score(stds[key], model['mu'], model['sigma'])

        # 최종 점수 (가중 평균)
        total_score = sum(scores[key] * model['weight'] for key, model in score_models.items()) * 100

        # 피드백 생성
        feedback = []
        if stds['energy_mean'] < 0.2:
            feedback.append("전반적으로 목소리 크기 변화가 적어 단조롭게 들릴 수 있습니다. 중요한 단어는 조금 더 힘주어 말해보세요.")
        elif stds['energy_mean'] > 0.8:
            feedback.append("목소리 크기 변화가 다소 과도하여 부자연스럽게 들릴 수 있습니다. 일정한 톤을 유지하는 연습이 필요합니다.")
        else:
            feedback.append("적절한 에너지 변화로 표현력이 좋습니다.")

        if stds['pitch_mean'] < 0.08:
            feedback.append("음높이 변화가 거의 없어 로봇처럼 들릴 수 있습니다. 문장의 끝을 올리거나 내리는 등 억양에 변화를 줘보세요.")
        elif stds['pitch_mean'] > 0.4:
            feedback.append("음높이 변화가 심해 불안정하게 들릴 수 있습니다. 편안한 톤으로 말하는 연습을 해보세요.")
        else:
            feedback.append("자연스러운 음높이 변화를 잘 사용하고 있습니다.")

        final_score = max(50, int(total_score)) # 최소 점수 50점 보장

        # 디버깅을 위한 표준편차 정보 추가
        debug_info = f"Stds(E_mean:{stds['energy_mean']:.2f}, P_mean:{stds['pitch_mean']:.2f})"
        feedback.append(debug_info)

        return final_score, feedback

    def load_baseline(self, baseline_name: str = "default") -> Dict:
        """Baseline 로드"""
        if baseline_name in self.baseline_cache:
            return self.baseline_cache[baseline_name]

        baseline_file = self.baseline_dir / f"accent_{baseline_name}.json"
        if not baseline_file.exists():
            return None

        try:
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline = json.load(f)
            self.baseline_cache[baseline_name] = baseline
            return baseline
        except:
            return None

    def analyze(self, wav_path: str, language: str = "ko", **kwargs) -> Dict:
        """
        강조 분석 수행

        Args:
            wav_path: WAV 파일 경로
            language: 언어 코드 ('ko', 'en' 등)
            azure_data: Azure Speech API 데이터 (Pronunciation 에이전트로부터)

        Returns:
            분석 결과 딕셔너리
        """
        try:
            # Azure STT를 사용하여 타임스탬프 추출
            print("AccentAnalyzer: Azure STT로 타임스탬프 추출 시도...")
            user_timestamps = self._get_timestamps_from_azure_stt(wav_path, language)

            # [중요] 신뢰도 기반 필터링
            if user_timestamps:
                # --- 필터링 규칙 강화 ---
                confidence_threshold = 0.3  # 1. 신뢰도 임계값 완화 (30% 이상이면 일단 인정)
                min_word_length = 1         # 2. 최소 단어 길이 완화 (한 글자 단어도 포함)
                min_duration = 0.1          # 3. 최소 발음 시간 완화 (0.1초 이상이면 인정)

                original_count = len(user_timestamps)
                
                filtered_timestamps = []
                for item in user_timestamps:
                    word = item.get('word', '')
                    confidence = item.get('confidence', 0.0)
                    duration = item.get('end', 0.0) - item.get('start', 0.0)

                    if confidence >= confidence_threshold and len(word) >= min_word_length and duration >= min_duration:
                        filtered_timestamps.append(item)
                
                user_timestamps = filtered_timestamps
                filtered_count = original_count - len(user_timestamps)
                print(f"AccentAnalyzer: 필터링으로 {filtered_count}개의 단어 제외 (신뢰도>{confidence_threshold}, 길이>{min_word_length}, 시간>{min_duration}s)")

            # 타임스탬프 추출 실패 시
            if not user_timestamps:
                return {
                    "score": 0,
                    "max_score": 100,
                    "feedback": [
                        "음성에서 단어를 인식하지 못했습니다.",
                        "더 명확한 발음으로 녹음하거나, 소음이 없는 환경에서 다시 시도해주세요."
                    ],
                    "status": "warning",
                    "features": {}
                }

            # 사용자 음향 특징 추출
            user_features = self.get_audio_features(wav_path, user_timestamps)

            if not user_features:
                return {
                    "score": 0,
                    "max_score": 100,
                    "feedback": ["오디오 특징 추출에 실패했습니다."],
                    "status": "warning",
                    "features": {}
                }

            # 점수 계산
            score, feedback = self.calculate_emphasis_score(user_features, language=language, use_pos_tagging=True)

            return {
                "score": score,
                "max_score": 100,
                "feedback": feedback if feedback else ["완벽합니다!"],
                "status": "success",
                "features": user_features
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "feedback": [f"분석 중 오류 발생: {str(e)}"],
                "status": "warning",
                "features": {}
            }


if __name__ == "__main__":
    # 테스트 코드
    analyzer = AccentAnalyzer()
    result = analyzer.analyze("test.wav", language="ko")
    print(json.dumps(result, ensure_ascii=False, indent=2))