"""
Accent Analysis Agent
음성 파일의 강조(Accent) 분석을 수행하는 에이전트
논문 기반(Pitch Semitone & Energy dB) 평가 로직 적용
"""
import os
import json
import librosa
import parselmouth
import numpy as np
import azure.cognitiveservices.speech as speechsdk
from typing import Dict, List, Tuple, Optional
from pathlib import Path

class AccentAnalyzer:
    """강조(Accent) 분석기"""

    def __init__(self, baseline_dir: str = "baselines"):
        # Baseline 지원 (필요시 사용)
        self.baseline_dir = Path(baseline_dir)
        self.baseline_cache = {}

    def _get_timestamps_from_azure_stt(self, wav_path: str, language: str) -> Optional[List[Dict]]:
        """
        Azure STT를 사용하여 단어별 타임스탬프 추출
        """
        try:
            speech_key = os.getenv("SPEECH_KEY") or os.getenv("AZURE_SPEECH_KEY")
            speech_region = os.getenv("SPEECH_REGION") or os.getenv("AZURE_SPEECH_REGION")
            
            if not speech_key or not speech_region:
                print("WARN: Azure 키/리전이 없어 AccentAnalyzer의 Azure STT를 건너뜁니다.")
                return None

            # 에너지 기반 묵음 제거 (전처리)
            y, sr = librosa.load(wav_path, sr=16000, mono=True)
            trimmed_audio, _ = librosa.effects.trim(y, top_db=30)
            
            # 임시 파일 저장 (Windows 호환성 위해 delete=False 사용 후 수동 삭제)
            import tempfile
            import soundfile as sf
            
            # delete=False로 설정하여 파일을 닫아도 삭제되지 않게 함
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            trimmed_wav_path = tmp.name
            
            try:
                # 데이터를 쓰고 파일 핸들을 닫음 (Windows file lock 해제)
                sf.write(tmp.name, trimmed_audio, sr)
                tmp.close()

                # language는 "ko-KR" 또는 "en-US" 형식으로 통일
                lang_code = language
                speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=speech_region)
                speech_config.speech_recognition_language = lang_code
                speech_config.request_word_level_timestamps()
                
                # 타임아웃 설정
                speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_InitialSilenceTimeoutMs, "10000")
                speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "10000")

                audio_config = speechsdk.audio.AudioConfig(filename=trimmed_wav_path)
                recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

                all_timestamps = []
                done = False

                def handle_recognized(evt):
                    if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                        json_result = json.loads(evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult))
                        words = json_result.get('NBest', [{}])[0].get('Words', [])
                        for word_info in words:
                            # Azure STT 시간 단위: 1 tick = 100ns (1e-7 sec)
                            start_time = word_info.get('Offset', 0) / 10000000.0
                            duration = word_info.get('Duration', 0) / 10000000.0
                            end_time = start_time + duration
                            
                            all_timestamps.append({
                                "word": word_info.get('Word'),
                                "start": start_time,
                                "end": end_time,
                                "confidence": word_info.get('Confidence', 0.0)
                            })

                def handle_canceled(evt):
                    nonlocal done
                    # 취소/에러 로그
                    # print(f"Speech Canceled: {evt.result.cancellation_details}")
                    done = True

                def handle_stopped(evt):
                    nonlocal done
                    done = True

                recognizer.recognized.connect(handle_recognized)
                recognizer.canceled.connect(handle_canceled)
                recognizer.session_stopped.connect(handle_stopped)

                recognizer.start_continuous_recognition()
                
                # 대기
                import time
                while not done:
                    time.sleep(0.1)

                recognizer.stop_continuous_recognition()

                if all_timestamps:
                    return all_timestamps
                return None

            finally:
                # Azure SDK 객체 명시적 해제 (파일 핸들 반환 유도)
                # try 블록 내에서 생성된 변수들이라 존재 여부 확인 필요
                if 'recognizer' in locals(): del recognizer
                if 'audio_config' in locals(): del audio_config
                
                # 가비지 컬렉션 강제 수행 (선택사항, 안전장치)
                import gc
                gc.collect()

                # 작업 완료 후 수동 삭제 (재시도 로직 추가)
                if os.path.exists(trimmed_wav_path):
                    max_retries = 3
                    for i in range(max_retries):
                        try:
                            os.remove(trimmed_wav_path)
                            break
                        except PermissionError:
                            if i < max_retries - 1:
                                import time
                                time.sleep(0.5)  # 잠시 대기 후 재시도
                            else:
                                print(f"WARN: 임시 파일 삭제 실패 (최종): {trimmed_wav_path}")
                        except Exception as e:
                            print(f"WARN: 임시 파일 삭제 중 오류: {e}")
                            break

        except Exception as e:
            print(f"AccentAnalyzer: Azure STT 오류: {e}")
            return None

    def _hz_to_semitone(self, freq_hz):
        """
        Hz를 Semitone으로 변환
        - 기준 주파수(ref)를 100Hz로 설정하여 성별 차이 보정
        - 공식: 12 * log2(Hz / 100)
        """
        if freq_hz <= 0:
            return 0.0
        return 12 * np.log2(freq_hz / 100.0)

    def get_audio_features(self, wav_path: str, timestamps: Dict) -> Dict:
        """
        음향 특징 추출
        - 논문 근거: Pitch는 Semitone, Energy는 dB 단위로 변환
        """
        try:
            # Parselmouth(Praat) 로드
            snd = parselmouth.Sound(wav_path)
            # Librosa 로드
            y, sr = librosa.load(wav_path, sr=None)
            
            # 음량 정규화 (Normalization): 전체 볼륨 레벨을 맞춰 dB 계산의 일관성 확보
            y = librosa.util.normalize(y)
        except Exception as e:
            print(f"ERROR: 오디오 로드 실패: {wav_path} | {e}")
            return None

        # 1. Pitch 추출 (Parselmouth)
        pitch = snd.to_pitch()
        f0_values_all = pitch.selected_array['frequency']

        # 2. Energy(RMS) 추출 (Librosa) -> 추후 dB 변환
        rms_all = librosa.feature.rms(y=y)[0]

        all_words_features = []
        
        for item in timestamps:
            word = item["word"]
            start_time = item["start"]
            end_time = item["end"]

            try:
                # --- Energy (dB) 계산 ---
                start_frame_rms = librosa.time_to_frames(start_time, sr=sr)
                end_frame_rms = librosa.time_to_frames(end_time, sr=sr)
                
                # 인덱스 범위 보정
                if end_frame_rms > len(rms_all): end_frame_rms = len(rms_all)
                
                energy_vector = rms_all[start_frame_rms:end_frame_rms]
                
                # 데이터가 비어있을 경우 (너무 짧은 단어 등)
                if len(energy_vector) == 0:
                    if start_frame_rms < len(rms_all):
                        energy_vector = np.array([rms_all[start_frame_rms]])
                    else:
                        energy_vector = np.array([1e-6]) # 0 방지용 아주 작은 값

                # RMS -> dB 변환 (ref=1.0: 최대 진폭 기준)
                # 단어 구간의 평균 dB 계산
                energy_db_vector = librosa.amplitude_to_db(energy_vector, ref=1.0)
                word_energy_db = np.mean(energy_db_vector)

                # --- Pitch (Semitone) 계산 ---
                start_frame_pitch = int(round(pitch.get_frame_number_from_time(start_time)))
                end_frame_pitch = int(round(pitch.get_frame_number_from_time(end_time)))
                
                # 인덱스 범위 보정
                if end_frame_pitch > len(f0_values_all): end_frame_pitch = len(f0_values_all)

                pitch_vector = f0_values_all[start_frame_pitch:end_frame_pitch]
                
                # 유성음(Voiced, >0)만 필터링
                pitch_vector_voiced = pitch_vector[pitch_vector > 0]
                
                is_voiced = False
                word_pitch_st = 0.0
                
                if len(pitch_vector_voiced) > 0:
                    # Hz -> Semitone 변환
                    semitone_vector = np.array([self._hz_to_semitone(p) for p in pitch_vector_voiced])
                    word_pitch_st = np.mean(semitone_vector)
                    is_voiced = True

                all_words_features.append({
                    "word": word,
                    "start": start_time,
                    "end": end_time,
                    "features": {
                        # 절대값 지표 저장 (Ratio 아님)
                        "energy_db": float(word_energy_db),
                        "pitch_st": float(word_pitch_st),
                        "is_voiced": is_voiced
                    }
                })

            except Exception as e:
                print(f"WARN: '{word}' 특징 추출 중 오류: {e}")
                continue

        return all_words_features

    def _get_pos_tags(self, words: List[str], language: str) -> Dict[str, str]:
        """단어 품사 태깅 (내용어/기능어 구분)"""
        pos_tags = {}
        # 한국어 (KoNLPy)
        if language.lower().startswith('ko'):
            try:
                from konlpy.tag import Okt
                okt = Okt()
                content_pos = ['Noun', 'Verb', 'Adjective', 'Adverb', 'Exclamation']
                for word in words:
                    tags = okt.pos(word)
                    if tags and tags[0][1] in content_pos:
                        pos_tags[word] = 'Content'
                    else:
                        pos_tags[word] = 'Function'
                return pos_tags
            except ImportError:
                return {word: 'Content' for word in words} # 라이브러리 없으면 기본값

        # 영어 (NLTK)
        elif language.lower().startswith('en'):
            try:
                import nltk
                content_pos_prefixes = ('NN', 'VB', 'JJ', 'RB')
                # nltk 데이터 다운로드 필요할 수 있음: nltk.download('averaged_perceptron_tagger')
                try:
                    tagged_words = nltk.pos_tag(words)
                except LookupError:
                    nltk.download('averaged_perceptron_tagger')
                    tagged_words = nltk.pos_tag(words)

                for word, tag in tagged_words:
                    if tag.startswith(content_pos_prefixes):
                        pos_tags[word] = 'Content'
                    else:
                        pos_tags[word] = 'Function'
                return pos_tags
            except ImportError:
                return {word: 'Content' for word in words}
        
        else:
            return {word: 'Content' for word in words}

    def _gaussian_score(self, x, mu, sigma):
        """가우시안 점수 계산 (0~1.0)"""
        return np.exp(-0.5 * ((x - mu) / sigma) ** 2)

    def calculate_emphasis_score(self, user_features: Dict, language: str = "ko", use_pos_tagging: bool = True, weight_pitch: float = 0.6, weight_energy: float = 0.4) -> Tuple[int, Dict]:
        """
        강조 점수 계산 (학술적 근거 기반: Weighted Standard Deviation)
        Target: Pitch SD ~ 4.0st, Energy SD ~ 5.5dB
        """
        if not user_features or len(user_features) < 2:
            return 0, {"error": "분석할 단어가 부족하여 평가할 수 없습니다."}

        words = [item['word'] for item in user_features]
        pos_tags = self._get_pos_tags(words, language) if use_pos_tagging else {word: 'Content' for word in words}

        # --- 데이터 준비 ---
        # Pitch: 유성음(Voiced) 구간만 유효
        valid_pitch_indices = [i for i, item in enumerate(user_features) if item['features']['is_voiced']]
        if not valid_pitch_indices:
             return 0, {"error": "목소리의 높낮이가 감지되지 않습니다."}

        pitch_values = np.array([user_features[i]['features']['pitch_st'] for i in valid_pitch_indices])
        pitch_words = [words[i] for i in valid_pitch_indices]

        # Energy: 모든 단어 유효 (단, 너무 낮은 에너지는 노이즈/묵음으로 간주하여 제외)
        # 정규화된 오디오(0dB Max)에서 -50dB 미만은 거의 들리지 않는 수준이므로 통계 왜곡 방지
        raw_energy_values = np.array([item['features']['energy_db'] for item in user_features])

        valid_energy_mask = raw_energy_values > -50.0
        if np.sum(valid_energy_mask) > 2:
            energy_values = raw_energy_values[valid_energy_mask]
            energy_words = [words[i] for i in range(len(words)) if valid_energy_mask[i]]
        else:
            energy_values = raw_energy_values
            energy_words = words

        # --- 가중 표준편차(Weighted SD) 계산 함수 ---
        def calculate_weighted_std(values, word_list_for_weights):
            if len(values) < 2: return 0.0
            # 가중치: 내용어(1.0) vs 기능어(0.5)
            # 내용어(중요단어)의 변화가 클수록 점수에 더 많이 반영됨
            w = np.array([1.0 if pos_tags.get(wd) == 'Content' else 0.5 for wd in word_list_for_weights])

            average = np.average(values, weights=w)
            variance = np.average((values - average) ** 2, weights=w)
            return np.sqrt(variance)

        # 측정된 표준편차 (변화량)
        measured_pitch_sd = calculate_weighted_std(pitch_values, pitch_words)
        measured_energy_sd = calculate_weighted_std(energy_values, energy_words)

        # --- 점수 매핑 (Gaussian Scoring) ---
        # 논문/연구 기반 이상적인 낭독체의 SD 범위 중앙값
        target_pitch_sd = 4.0   # 3.0 ~ 5.0 Semitones
        target_energy_sd = 5.5  # 4.0 ~ 7.0 dB

        # Sigma: 점수 관대함 정도 (클수록 점수가 천천히 떨어짐)
        sigma_pitch = 2.0
        sigma_energy = 4.0  # 2.5 -> 4.0 (에너지 변동성 허용 범위 확대)

        score_pitch = self._gaussian_score(measured_pitch_sd, target_pitch_sd, sigma_pitch) * 100
        score_energy = self._gaussian_score(measured_energy_sd, target_energy_sd, sigma_energy) * 100

        # 최종 가중 합산
        final_score = (score_pitch * weight_pitch) + (score_energy * weight_energy)

        # [삭제됨] 최저점 방어 로직 (max 50) 제거 -> 0점 가능
        final_score = int(final_score)

        # 최종 점수 계산에 사용된 변수 반환
        metrics = {
            "score_pitch": round(float(score_pitch), 2),
            "score_energy": round(float(score_energy), 2)
        }

        return final_score, metrics

    def analyze(self, wav_path: str, language: str = "ko", weight_pitch: float = 0.6, weight_energy: float = 0.4, **kwargs) -> Dict:
        """
        메인 분석 함수
        """
        try:
            print("AccentAnalyzer: 분석 시작...")
            
            # 1. STT 및 타임스탬프 추출
            user_timestamps = self._get_timestamps_from_azure_stt(wav_path, language)

            # 2. 필터링 (신뢰도, 길이, 지속시간)
            if user_timestamps:
                confidence_threshold = 0.3
                min_word_length = 1
                min_duration = 0.1
                
                filtered = [
                    t for t in user_timestamps 
                    if t['confidence'] >= confidence_threshold 
                    and len(t['word']) >= min_word_length 
                    and (t['end'] - t['start']) >= min_duration
                ]
                
                # print(f"AccentAnalyzer: {len(user_timestamps)}개 단어 중 {len(filtered)}개 선별됨.")
                user_timestamps = filtered

            if not user_timestamps:
                return {
                    "score": 0,
                    "max_score": 100,
                    "status": "fail",
                    "error_message": "음성을 명확히 인식하지 못했습니다.",
                    "features": {}
                }

            # 3. 특징 추출 (dB, Semitone)
            user_features = self.get_audio_features(wav_path, user_timestamps)

            if not user_features:
                 return {
                    "score": 0,
                    "max_score": 100,
                    "status": "error",
                    "error_message": "오디오 파일 분석에 실패했습니다.",
                    "features": {}
                }

            # 4. 점수 계산
            score, metrics = self.calculate_emphasis_score(user_features, language=language, use_pos_tagging=True, weight_pitch=weight_pitch, weight_energy=weight_energy)

            # 에러가 있는 경우
            if "error" in metrics:
                return {
                    "score": 0,
                    "max_score": 100,
                    "status": "error",
                    "error_message": metrics["error"],
                    "features": {}
                }

            return {
                "score": score,
                "max_score": 100,
                "status": "success",
                "score_pitch": metrics["score_pitch"],
                "score_energy": metrics["score_energy"],
                "features": user_features,
                "timestamps": user_timestamps  # Intonation 재사용용 원본 타임스탬프 (word, confidence 포함)
            }

        except Exception as e:
            return {
                "score": 0,
                "max_score": 100,
                "status": "error",
                "error_message": str(e),
                "features": {}
            }