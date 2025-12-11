# 🔴 Pause와 Accent 0점 문제 분석

## 📊 현재 상황

```json
{
  "score_pronunciation": 95.25,  // ✅ 정상
  "score_pause": 0,               // ❌ 0점
  "score_intonation": 61.48,      // ✅ 정상
  "score_tone": 49.56,            // ✅ 정상
  "score_speed": 95,              // ✅ 정상
  "score_accent": 0,              // ❌ 0점
  "overall_score": 50.21
}
```

---

## 🔍 원인 분석

### 1️⃣ **Pause Analyzer: 0점 원인**

#### 문제: **필수 Baseline 파일 누락**

**파일**: [app/agents/analyzers/pause.py](../../agents/analyzers/pause.py#L16)

```python
# Line 16: Baseline 파일 경로 정의
DEFAULT_PAUSE_BASELINE_PATH = BASE_DIR / "agents" / "baselines" / "pause_default.json"

# Line 346: Baseline 파일 로딩 시도
self._ensure_baseline_loaded(baseline_path)

# Line 78-79: 파일이 없으면 예외 발생
with open(baseline_path, "r", encoding="utf-8") as f:
    self._baseline = json.load(f)
```

#### 현재 상태

```bash
# 존재하는 baseline 파일들:
app/agents/baselines/
├── intonation_default.json  ✅
├── speed_default.json        ✅
├── tone_default.json         ✅
├── pause_reference/          ✅ (폴더만 존재)
└── pause_default.json        ❌ 없음!
```

#### 에러 발생 지점

1. **PauseAnalyzer.analyze()** 호출 ([pause.py:318-559](../../agents/analyzers/pause.py#L318-L559))
2. **Line 346**: `self._ensure_baseline_loaded(baseline_path)` 호출
3. **Line 78**: `with open(baseline_path, "r", encoding="utf-8") as f:` → **FileNotFoundError 발생**
4. **Exception 처리** (Line 562-567):
   ```python
   except Exception as e:
       return {
           "score": 0,
           "max_score": 100,
           "feedback": [f"분석 중 오류 발생: {str(e)}"],
           "status": "error"
       }
   ```
5. **결과**: `score: 0` 반환

---

### 2️⃣ **Accent Analyzer: 0점 원인 (추정)**

#### 문제 1: **Azure Speech API 호출 실패**

**파일**: [app/agents/analyzers/accent.py](../../agents/analyzers/accent.py#L23-108)

```python
# Line 28-33: Azure 키 확인
speech_key = os.getenv("SPEECH_KEY") or os.getenv("AZURE_SPEECH_KEY")
speech_region = os.getenv("SPEECH_REGION") or os.getenv("AZURE_SPEECH_REGION")

if not speech_key or not speech_region:
    print("WARN: Azure 키/리전이 없어 AccentAnalyzer의 Azure STT를 건너뜁니다.")
    return None  # ← 여기서 None 반환
```

#### Azure 키 확인

**.env 파일 확인 결과**:
```env
AZURE_SPEECH_KEY=16Ddw09jmDISjmf4dXZs8fYN7AWOn9cGZxObAkxKd0SsGFEHMdiEJQQJ99BLACNns7RXJ3w3AAAYACOGYQ4k
AZURE_SPEECH_REGION=koreacentral
```

✅ **Azure 키는 정상적으로 설정됨**

#### 문제 2: **타임스탬프 추출 실패 시 0점 처리**

```python
# Line 331: Azure STT 호출
user_timestamps = self._get_timestamps_from_azure_stt(wav_path, language)

# Line 349-356: timestamps가 None이거나 비어있으면 0점
if not user_timestamps:
    return {
        "score": 0,
        "max_score": 100,
        "status": "fail",
        "error_message": "음성을 명확히 인식하지 못했습니다.",
        "features": {}
    }
```

#### 가능한 원인

1. **Azure API 호출 실패**:
   - 네트워크 문제
   - API 할당량 초과
   - 음성 파일 형식 문제 (전처리 실패)

2. **필터링으로 모든 단어 제거**:
   ```python
   # Line 339-344: 신뢰도/길이/지속시간 필터링
   filtered = [
       t for t in user_timestamps
       if t['confidence'] >= 0.3       # 신뢰도 30% 이상
       and len(t['word']) >= 1         # 단어 길이 1 이상
       and (t['end'] - t['start']) >= 0.1  # 지속시간 0.1초 이상
   ]
   ```
   - 음성 품질이 낮아서 모든 단어가 신뢰도 30% 미만

3. **음성에 유성음(Voiced) 구간이 없음**:
   ```python
   # Line 273-274: 유성음이 없으면 0점
   if not valid_pitch_indices:
       return 0, {"error": "목소리의 높낮이가 감지되지 않습니다."}
   ```

---

## 📂 분석 시 실행되는 파일 목록

### ✅ API 호출 플로우

```
1. [router_evaluate.py] POST /api/v1/evaluate
   ↓
2. [analyzer_manager.py] SpeechAnalysisManager.analyze_parallel()
   ↓
3. [7개 Analyzer 병렬 실행]
   ├─ [validate.py] ValidateAnalyzer
   ├─ [pronunciation.py] PronunciationAnalyzer
   ├─ [pause.py] PauseAnalyzer ← ❌ 0점
   ├─ [intonation.py] IntonationAnalyzer
   ├─ [speed.py] SpeedAnalyzer
   ├─ [tone.py] ToneAnalyzer
   └─ [accent.py] AccentAnalyzer ← ❌ 0점
   ↓
4. [comment_generator.py] AICommentGenerator.generate_comment()
   ↓
5. [router_evaluate.py] EvaluationResponse 반환
```

### 📄 실행 파일 전체 목록 (실행 순서)

#### **1단계: API 엔드포인트**
| 파일 | 경로 | 역할 |
|------|------|------|
| **router_evaluate.py** | [app/apis/v1/router_evaluate.py](router_evaluate.py) | `/evaluate` 엔드포인트 정의 |

#### **2단계: 매니저**
| 파일 | 경로 | 역할 |
|------|------|------|
| **analyzer_manager.py** | [app/agents/managers/analyzer_manager.py](../../agents/managers/analyzer_manager.py) | 7개 에이전트 병렬 실행 (ThreadPoolExecutor) |
| **baseline_manager.py** | [app/agents/managers/baseline_manager.py](../../agents/managers/baseline_manager.py) | Baseline 생성 지원 (분석 시 직접 사용 안 함) |

#### **3단계: 7개 Analyzer 에이전트**
| 파일 | 경로 | 역할 | 상태 |
|------|------|------|------|
| **validate.py** | [app/agents/analyzers/validate.py](../../agents/analyzers/validate.py) | 스크립트 정확도 검증 (Azure) | ✅ 정상 |
| **pronunciation.py** | [app/agents/analyzers/pronunciation.py](../../agents/analyzers/pronunciation.py) | 발음 평가 (Azure) | ✅ 정상 |
| **pause.py** | [app/agents/analyzers/pause.py](../../agents/analyzers/pause.py) | 휴지 분석 (Azure + Baseline) | ❌ **0점** |
| **intonation.py** | [app/agents/analyzers/intonation.py](../../agents/analyzers/intonation.py) | 억양 분석 (Parselmouth + Baseline) | ✅ 정상 |
| **speed.py** | [app/agents/analyzers/speed.py](../../agents/analyzers/speed.py) | 속도 분석 (Azure + Baseline) | ✅ 정상 |
| **tone.py** | [app/agents/analyzers/tone.py](../../agents/analyzers/tone.py) | 톤 분석 (Parselmouth + Baseline) | ✅ 정상 |
| **accent.py** | [app/agents/analyzers/accent.py](../../agents/analyzers/accent.py) | 강조 분석 (Azure + Parselmouth) | ❌ **0점** |

#### **4단계: AI 코멘트 생성**
| 파일 | 경로 | 역할 |
|------|------|------|
| **comment_generator.py** | [app/agents/utils/comment_generator.py](../../agents/utils/comment_generator.py) | OpenAI API로 종합 피드백 생성 |

#### **5단계: 스키마 (응답 형식)**
| 파일 | 경로 | 역할 |
|------|------|------|
| **evaluation.py** | [app/schemas/evaluation.py](../../schemas/evaluation.py) | EvaluationResponse 정의 |

#### **필수 의존 파일**
| 파일 | 경로 | 역할 | 상태 |
|------|------|------|------|
| **pause_default.json** | `app/agents/baselines/pause_default.json` | Pause 분석 기준 통계 | ❌ **없음** |
| **intonation_default.json** | [app/agents/baselines/intonation_default.json](../../agents/baselines/intonation_default.json) | Intonation 분석 기준 | ✅ 있음 |
| **speed_default.json** | [app/agents/baselines/speed_default.json](../../agents/baselines/speed_default.json) | Speed 분석 기준 | ✅ 있음 |
| **tone_default.json** | [app/agents/baselines/tone_default.json](../../agents/baselines/tone_default.json) | Tone 분석 기준 | ✅ 있음 |
| **.env** | [.env](../../../.env) | Azure/OpenAI API 키 | ✅ 설정됨 |

---

## 🛠️ 해결 방법

### ✅ 1. Pause Analyzer 수정 (필수)

**옵션 A: pause_default.json 파일 생성**

baseline을 생성하려면 다음 단계를 따르세요:

1. **샘플 음성 파일 준비**:
   ```
   app/agents/baselines/pause_reference/
   ├── ko-KR/
   │   ├── sample1.txt
   │   ├── sample1.wav
   │   ├── sample2.txt
   │   └── sample2.wav
   └── en-US/
       ├── sample1.txt
       ├── sample1.wav
       └── ...
   ```

2. **Baseline 생성 스크립트 실행**:
   ```bash
   python -m app.agents.managers.baseline_manager generate-pause-baseline \
       --reference-dir app/agents/baselines/pause_reference \
       --output app/agents/baselines/pause_default.json
   ```

**옵션 B: pause_default.json 템플릿 사용 (임시)**

최소한의 baseline 파일을 생성하여 에러를 방지:

```json
{
  "languages": {
    "ko-KR": {
      "min_pause_threshold": 0.15,
      "contexts": {
        "after_period": {
          "features": {
            "pause_sec": {"mean": 0.75, "std": 0.22},
            "prev_phrase_duration_sec": {"mean": 4.2, "std": 1.1},
            "words_since_last_pause": {"mean": 12.5, "std": 3.2}
          }
        },
        "after_comma": {
          "features": {
            "pause_sec": {"mean": 0.45, "std": 0.15},
            "prev_phrase_duration_sec": {"mean": 3.5, "std": 0.9},
            "words_since_last_pause": {"mean": 8.0, "std": 2.5}
          }
        },
        "after_question": {
          "features": {
            "pause_sec": {"mean": 0.8, "std": 0.25}
          }
        },
        "after_exclamation": {
          "features": {
            "pause_sec": {"mean": 0.7, "std": 0.2}
          }
        },
        "mid_phrase_breath": {
          "features": {
            "pause_sec": {"mean": 0.35, "std": 0.12}
          }
        }
      },
      "mid_phrase_breath_criteria": {
        "min_prev_phrase_duration_sec": 5.0,
        "min_words_since_last_pause": 15
      },
      "good_pause_ratio": {
        "mean": 0.85,
        "std": 0.12
      }
    }
  }
}
```

파일 저장 위치: `app/agents/baselines/pause_default.json`

---

### ✅ 2. Accent Analyzer 디버깅 (권장)

#### **로그 활성화하여 정확한 원인 파악**

[accent.py](../../agents/analyzers/accent.py#L32-33)의 WARN 메시지가 출력되는지 확인:

```python
# Line 32-33
if not speech_key or not speech_region:
    print("WARN: Azure 키/리전이 없어 AccentAnalyzer의 Azure STT를 건너뜁니다.")
    return None
```

**확인 방법**:
1. 서버 실행 시 콘솔 출력 확인
2. `log/analysis_*.log` 파일 확인

#### **Azure API 호출 성공 여부 확인**

[accent.py:106-108](../../agents/analyzers/accent.py#L106-108)의 예외 로그 확인:

```python
except Exception as e:
    print(f"AccentAnalyzer: Azure STT 오류: {e}")
    return None
```

#### **필터링 문제 확인**

[accent.py:346](../../agents/analyzers/accent.py#L346)의 로그 활성화:

```python
# 현재 주석 처리된 로그 (Line 346)
# print(f"AccentAnalyzer: {len(user_timestamps)}개 단어 중 {len(filtered)}개 선별됨.")
```

이 주석을 해제하면 필터링 결과를 확인할 수 있습니다.

---

## 🎯 권장 조치 순서

### 1단계: Pause 문제 해결 (즉시)

```bash
# 임시 baseline 파일 생성 (위의 JSON 템플릿 사용)
# 파일: app/agents/baselines/pause_default.json
```

### 2단계: 서버 재시작 및 테스트

```bash
# 서버 재시작
uvicorn app.main:app --reload

# 테스트 실행
curl -X POST "http://localhost:8000/api/v1/evaluate" \
  -F "audio_file=@test.wav" \
  -F "script_id=1" \
  -F "user_id=test_user" \
  -F "reference_text=안녕하세요. 오늘은 날씨가 좋습니다."
```

### 3단계: Accent 로그 확인

```bash
# 콘솔 출력 또는 로그 파일에서 다음 메시지 확인:
# 1. "WARN: Azure 키/리전이 없어..." → .env 문제
# 2. "AccentAnalyzer: Azure STT 오류: ..." → API 호출 문제
# 3. "{N}개 단어 중 {M}개 선별됨" → 필터링 문제 (M=0이면 문제)
```

### 4단계: Baseline 정식 생성 (장기)

```bash
# pause_reference 폴더에 샘플 음성 추가 후
python -m app.agents.managers.baseline_manager generate-pause-baseline \
    --reference-dir app/agents/baselines/pause_reference \
    --output app/agents/baselines/pause_default.json
```

---

## 📋 요약

| 항목 | 문제 | 원인 | 해결책 |
|------|------|------|--------|
| **Pause** | 0점 | `pause_default.json` 파일 없음 | ✅ 템플릿 JSON 파일 생성 |
| **Accent** | 0점 (추정) | Azure STT 실패 또는 필터링 문제 | 🔍 로그 확인 필요 |

**즉시 조치**: `pause_default.json` 파일을 생성하면 Pause 점수는 정상화됩니다.

**Accent 디버깅**: 서버 재시작 후 콘솔/로그를 확인하여 정확한 원인을 파악해야 합니다.
